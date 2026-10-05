"""Stage 6a: the Obsidian vault, from entities, threads and notes. No model.

out/<book>/<title>/ is a standalone vault:
  00 Обзор.md            the entry page, linking graph.html beside it
  Главы/                 one note per chapter; every event is a list item
                         with a block id (^ch005-02-e03), so other notes link
                         straight to it
  Персонажи/ Места/ Группы/ Сюжетные линии/
Entities too minor for a note of their own appear as plain text.
"""

import collections
import json
import re
import shutil
from pathlib import Path

from .resolve import entity_id, key
from .store import ROOT, read_json, work_dir

FOLDERS = {"chapters": "Главы", "characters": "Персонажи", "places": "Места",
           "groups": "Группы", "storylines": "Сюжетные линии"}
TYPES = {"chapters": "глава", "characters": "персонаж", "places": "место",
         "groups": "группа", "storylines": "сюжетная линия"}
COLORS = {"chapters": 0x8A8F98, "characters": 0xD9822B, "places": 0x2E9E6B,
          "groups": 0x7B61D9, "storylines": 0x2F80ED}


def safe(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|#^\[\]]', " ", name)
    return re.sub(r"\s+", " ", name).strip(" .") or "без имени"


def yaml_list(items) -> str:
    return "[" + ", ".join(json.dumps(i, ensure_ascii=False) for i in items) + "]"


class Vault:
    def __init__(self, book: str) -> None:
        wd = work_dir(book)
        self.wd = wd
        self.meta = read_json(wd / "chapters.json")
        threads = read_json(wd / "threads.json")
        present = {e["chapter"] for e in threads["events"]}
        # Before the whole book is extracted, only the chapters done so far.
        self.meta["chapters"] = [c for c in self.meta["chapters"] if c["id"] in present]
        self.entities = read_json(wd / "entities.json")
        self.storylines = threads["storylines"]
        self.events = threads["events"]
        # Extraction and the link pass can join the same two events; keep one
        # link per pair, the one that says why.
        pairs: dict[tuple[str, str], dict] = {}
        for edge in threads["edges"]:
            k = (edge["src"], edge["dst"])
            if k not in pairs or (edge["why"] and not pairs[k]["why"]):
                pairs[k] = edge
        self.edges = list(pairs.values())
        self.by_event = {e["id"]: e for e in self.events}
        self.notes = {}
        for kind in FOLDERS:
            for path in (wd / "notes" / kind).glob("*.json"):
                self.notes[path.stem] = read_json(path)
        overview = wd / "notes" / "overview.json"
        self.overview = read_json(overview) if overview.exists() else None
        # Note file name, without .md, for every item that has a note.
        self.files: dict[str, str] = {}
        self.titles: dict[str, str] = {}
        used: set[str] = set()
        for ch in self.meta["chapters"]:
            self.files[ch["id"]] = f"{FOLDERS['chapters']}/{safe(ch['title'])}"
            self.titles[ch["id"]] = ch["title"]
        for kind in ("characters", "places", "groups"):
            for e in self.entities[kind]:
                self.titles[e["id"]] = e["name"]
                if e["id"] in self.notes:
                    name = safe(e["name"])
                    while name.lower() in used:
                        name += " (2)"
                    used.add(name.lower())
                    self.files[e["id"]] = f"{FOLDERS[kind]}/{name}"
        self.unordered = {}
        for k, eid in self.entities["index"].items():
            kind, _, name = k.partition(":")
            self.unordered.setdefault((kind, " ".join(sorted(name.split()))), eid)
        for s in self.storylines:
            self.files[s["id"]] = f"{FOLDERS['storylines']}/{safe(s['name'])}"
            self.titles[s["id"]] = s["name"]

    def link(self, item: str, label: str | None = None) -> str:
        title = label or self.titles.get(item, item)
        if item not in self.files:
            return title
        name = self.files[item].split("/")[-1]
        return f"[[{name}]]" if title == name else f"[[{name}|{title}]]"

    def event_link(self, eid: str) -> str:
        e = self.by_event[eid]
        name = self.files[e["chapter"]].split("/")[-1]
        return f"[[{name}#^{eid}|{e['title']}]]"

    def name_link(self, kind: str, name: str) -> str:
        eid = entity_id(self.entities, kind, name)
        if not eid:
            # The model may write "Ноэда Нодами" for the entity "Нодами Ноэда".
            eid = self.unordered.get((kind, " ".join(sorted(key(name).split()))))
        return self.link(eid) if eid else name

    # Pages.

    def chapter(self, i: int, ch: dict) -> str:
        note = self.notes.get(ch["id"], {})
        evs = [e for e in self.events if e["chapter"] == ch["id"]]
        lines_ = sorted({s for e in evs for s in e["storylines"]})
        people = collections.Counter(w for e in evs for w in e["who"])
        incoming = collections.defaultdict(list)
        for edge in self.edges:
            if edge["dst"] in {e["id"] for e in evs}:
                incoming[edge["dst"]].append(edge)
        out = ["---", f"type: {TYPES['chapters']}", f"order: {ch['n']}",
               f"storylines: {yaml_list(self.titles[s] for s in lines_)}",
               f"characters: {yaml_list(self.titles[p] for p, _ in people.most_common(15))}",
               "---", f"# {ch['title']}", ""]
        chapters = self.meta["chapters"]
        nav = []
        if i > 0:
            nav.append(f"← {self.link(chapters[i - 1]['id'])}")
        if i + 1 < len(chapters):
            nav.append(f"{self.link(chapters[i + 1]['id'])} →")
        out += [" · ".join(nav), ""]
        if note:
            out += [f"> {note['oneline']}", "", "## Кратко", "", note["summary"], ""]
            out += ["## Ключевые моменты", ""] + [f"- {k}" for k in note["key_points"]] + [""]
        out += ["## События", ""]
        for e in evs:
            mark = {3: "🔺 ", 2: "", 1: ""}[e["importance"]]
            title = f"**{e['title']}**" if e["importance"] >= 2 else e["title"]
            meta = []
            if e["who"]:
                meta.append(", ".join(self.link(w) for w in e["who"]))
            if e["where"] or e["where_text"]:
                meta.append(self.link(e["where"]) if e["where"] else e["where_text"])
            if e["storylines"]:
                meta.append(" ".join(self.link(s) for s in e["storylines"]))
            out.append(f"- {mark}{title} — {e['what']} ^{e['id']}")
            if meta:
                out.append(f"\t- {' · '.join(meta)}")
            for edge in incoming[e["id"]]:
                if edge["src"] in self.by_event:
                    why = f" ({edge['why']})" if edge["why"] else ""
                    out.append(f"\t- ← {edge['type']}: {self.event_link(edge['src'])}{why}")
        if people:
            out += ["", "## Персонажи", "",
                    ", ".join(self.link(p) for p, _ in people.most_common())]
        return "\n".join(out) + "\n"

    def appearances(self, ent: dict, events: list[dict]) -> list[str]:
        out = ["## Появления", ""]
        by_chapter = collections.defaultdict(list)
        for e in events:
            by_chapter[e["chapter"]].append(e)
        chapters = list(dict.fromkeys(c.split("-")[0] for c in ent["chunks"]))
        for ch in chapters:
            notable = [e for e in by_chapter.get(ch, []) if e["importance"] >= 2]
            tail = (": " + "; ".join(self.event_link(e["id"]) for e in notable[:6])) if notable else ""
            out.append(f"- {self.link(ch)}{tail}")
        return out

    def character(self, ent: dict) -> str:
        note = self.notes[ent["id"]]
        evs = [e for e in self.events if ent["id"] in e["who"]]
        lines_ = collections.Counter(s for e in evs for s in e["storylines"])
        first = ent["chunks"][0].split("-")[0]
        out = ["---", f"type: {TYPES['characters']}", f"aliases: {yaml_list(ent['aliases'][:30])}",
               f"mentions: {ent['mentions']}", f"first: \"[[{self.files[first].split('/')[-1]}]]\"",
               f"storylines: {yaml_list(self.titles[s] for s, _ in lines_.most_common(8))}",
               "---", f"# {ent['name']}", "", note["summary"], ""]
        if note["traits"]:
            out += ["## Черты", ""] + [f"- {t}" for t in note["traits"]] + [""]
        if note["arc"]:
            out += ["## Арка", ""]
            titles = {c["title"]: c["id"] for c in self.meta["chapters"]}
            for step in note["arc"]:
                ch = titles.get(step["chapter"].strip())
                out.append(f"- {self.link(ch) if ch else step['chapter']} — {step['change']}")
            out.append("")
        if note["relationships"]:
            out += ["## Отношения", ""]
            out += [f"- {self.name_link('characters', b['other'])} — {b['description']}"
                    for b in note["relationships"]] + [""]
        if lines_:
            out += ["## Сюжетные линии", "", ", ".join(self.link(s) for s, _ in lines_.most_common()), ""]
        return "\n".join(out + self.appearances(ent, evs)) + "\n"

    def entity(self, kind: str, ent: dict) -> str:
        note = self.notes[ent["id"]]
        evs = [e for e in self.events if e["where"] == ent["id"]] if kind == "places" else []
        out = ["---", f"type: {TYPES[kind]}", f"aliases: {yaml_list(ent['aliases'][:20])}",
               f"mentions: {ent['mentions']}", "---", f"# {ent['name']}", "", note["summary"], ""]
        return "\n".join(out + self.appearances(ent, evs)) + "\n"

    def storyline(self, s: dict) -> str:
        note = self.notes.get(s["id"])
        evs = [e for e in self.events if s["id"] in e["storylines"]]
        people = collections.Counter(w for e in evs for w in e["who"])
        out = ["---", f"type: {TYPES['storylines']}", f"events: {len(evs)}",
               f"characters: {yaml_list(self.titles[p] for p, _ in people.most_common(10))}",
               "---", f"# {s['name']}", "", f"*{s['description']}*", ""]
        if note:
            out += [note["summary"], "", "## Этапы", ""]
            for ph in note["phases"]:
                out += [f"### {ph['title']}", f"*{ph['chapters']}*", "", ph["text"], ""]
            out += ["## Итог", "", note["outcome"], ""]
        if people:
            out += ["## Персонажи", "", ", ".join(self.link(p) for p, _ in people.most_common(15)), ""]
        out += ["## События", ""]
        for ch in dict.fromkeys(e["chapter"] for e in evs):
            items = [e for e in evs if e["chapter"] == ch and e["importance"] >= 2] or \
                    [e for e in evs if e["chapter"] == ch][:2]
            out.append(f"- {self.link(ch)}: " + "; ".join(self.event_link(e["id"]) for e in items))
        return "\n".join(out) + "\n"

    def index(self) -> str:
        m = self.meta
        out = ["---", "type: обзор", "---", f"# {m['title']}", "", f"*{m['author']}*", ""]
        if m.get("annotation"):
            out += [f"> {m['annotation']}", ""]
        out += ["Интерактивный граф: [graph.html](graph.html) (откроется в браузере)", ""]
        if self.overview:
            o = self.overview
            out += ["## О книге", "", o["summary"], "", "## Устройство сюжета", "", o["structure"], ""]
            out += ["## Темы", ""] + [f"- {t}" for t in o["themes"]] + [""]
        out += ["## Сюжетные линии", ""]
        for s in self.storylines:
            n = sum(1 for e in self.events if s["id"] in e["storylines"])
            out.append(f"- {self.link(s['id'])} — {s['description']} ({n} событий)")
        out += ["", "## Главные персонажи", ""]
        for e in self.entities["characters"][:30]:
            if e["id"] in self.files:
                out.append(f"- {self.link(e['id'])} — {e['mentions']} фрагментов")
        out += ["", "## Главы", ""]
        for ch in m["chapters"]:
            note = self.notes.get(ch["id"])
            out.append(f"- {self.link(ch['id'])}" + (f" — {note['oneline']}" if note else ""))
        return "\n".join(out) + "\n"

    def write(self, root: Path) -> None:
        if root.exists():
            shutil.rmtree(root)
        for folder in FOLDERS.values():
            (root / folder).mkdir(parents=True)
        pages = {"00 Обзор": self.index()}
        for i, ch in enumerate(self.meta["chapters"]):
            pages[self.files[ch["id"]]] = self.chapter(i, ch)
        for ent in self.entities["characters"]:
            if ent["id"] in self.notes:
                pages[self.files[ent["id"]]] = self.character(ent)
        for kind in ("places", "groups"):
            for ent in self.entities[kind]:
                if ent["id"] in self.notes:
                    pages[self.files[ent["id"]]] = self.entity(kind, ent)
        for s in self.storylines:
            pages[self.files[s["id"]]] = self.storyline(s)
        for name, text in pages.items():
            (root / f"{name}.md").write_text(text, encoding="utf-8")
        # Colour the graph view by folder.
        (root / ".obsidian").mkdir()
        groups = [{"query": f'path:"{FOLDERS[k]}"', "color": {"a": 1, "rgb": COLORS[k]}} for k in FOLDERS]
        (root / ".obsidian" / "graph.json").write_text(
            json.dumps({"colorGroups": groups}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"vault: {len(pages)} notes in {root}")


def out_dir(book: str) -> Path:
    return ROOT / "out" / book


def run(book: str) -> Path:
    vault = Vault(book)
    root = out_dir(book) / safe(vault.meta["title"])
    vault.write(root)
    return root
