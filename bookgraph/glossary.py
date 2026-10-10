"""The author's glossary of a book: who is who, by the book's own author.

  bookgraph glossary build NAME FILE   the glossary's FB2 into work/NAME/glossary.json
  bookgraph glossary who NAME QUERY    the entries a name may be, best first

The glossary is a separate FB2 («Сломанный Справочник» for «Сломанный
Меч»): sections of lines «Имя (прозвище) (годы) — описание», under short
headings that end with a colon (a city, a clan, a generation). It is a
prior for resolve and a reference while annotating, never evidence for
extraction or summaries: its biographies run ahead of the text.

Entries from «Эхо Горького Сна», the book inside the book, get world
"echo": the author hides which main characters they are, so they are never
matched to main-world names.
"""

import re
from pathlib import Path

from .parse import NS, paragraphs, read_fb2, text_of
from .store import read_json, work_dir, write_json

import xml.etree.ElementTree as ET

ECHO = "Эхо Горького Сна"
TITLES = ("Генерал", "Профессор", "Доктор", "Мисс", "Миссис", "Мистер", "Старейшина",
          "Король", "Принцесса", "Комиссар", "Святой", "Святая", "Старина", "Госпожа",
          "Лже-Император", "Император", "Братья-Близнецы")
RUNES = re.compile(r"[ᚠ-᛿]")
YEARS = re.compile(r"\d|\?\?")
CHAPTERS = re.compile(r"^(\d+)(?:\s*-\s*(\d+))?\s+Глав")


def norm(s: str) -> str:
    s = s.lower().replace("ё", "е").replace("’", "'")
    return re.sub(r"\s+", " ", re.sub(r"[«»\"“”.]", "", s)).strip()


def era(years: str) -> str | None:
    if "Э.К" in years:
        return "ЭК"
    if "Э.В" in years:
        return "ЭВ"
    return None


def split_head(head: str) -> tuple[list[str], list[str], str]:
    """«Хейли Арк (Последний Дюрфор) (786 год Э.К.)» -> names, epithets, years."""
    years, epithets = "", []
    for part in re.findall(r"\(([^)]*)\)", head):
        if YEARS.search(part):
            years = part.strip()
        elif part.strip() and not part.startswith("проект") and not RUNES.search(part):
            epithets += [p.strip() for p in part.split(",") if p.strip()]
    base = re.sub(r"\([^)]*\)", "", head).strip(" «»\"")
    names = [n.strip(" «»\"") for n in base.split("/") if n.strip()]
    return names, epithets, years


def people(name: str) -> list[str]:
    """«Майра и Николь Арк» is two people; so is «Лок Джу и Гао Линь»."""
    parts = name.split(" и ")
    if len(parts) != 2:
        return [name]
    a, b = parts
    if len(a.split()) == 1 and len(b.split()) >= 2:
        a = f"{a} {b.split()[-1]}"
    return [a, b]


def forms(names: list[str], epithets: list[str]) -> list[str]:
    """Every way the entry may be written: names, epithets, «Жон Пьяница»,
    and names without a title («Профессор Сандор» -> «Сандор»)."""
    out = list(names) + epithets
    first = names[0].split()[0] if names else ""
    for e in epithets:
        out += [f"{first} {e}", f"{names[0]} {e}"]
    for n in names:
        for t in TITLES:
            if n.startswith(t + " ") and len(n.split()) > len(t.split()):
                out.append(n[len(t) + 1:])
    return list(dict.fromkeys(f for f in out if f and not RUNES.search(f)))


def parse_lines(sections: list[tuple[str, list[str]]]) -> dict:
    entries: list[dict] = []
    chronology: list[dict] = []

    def add(names, epithets, years, desc, section, group, kind=None) -> dict:
        names = [n for n in names if not RUNES.search(n)]
        e = {"id": f"g{len(entries) + 1:04d}", "name": names[0], "forms": forms(names, epithets),
             "epithets": epithets, "years": years, "era": era(years), "section": section,
             "group": group, "world": "echo" if section == ECHO else "main",
             "kind": kind, "text": RUNES.sub("", desc).strip(" ()!")}
        entries.append(e)
        return e

    for section, lines in sections:
        group, team, member, last = None, None, None, None
        # A line starting with a dash continues the one before it.
        joined: list[str] = []
        for line in (re.sub(r"\s+", " ", l).strip() for l in lines):
            if not line:
                continue
            if line.startswith("— ") and joined:
                joined[-1] += " " + line
            else:
                joined.append(line)
        for line in joined:
            if line.startswith("(") and line.endswith(")"):
                # A picture's caption: «(Эмблема Арков)»; «(Современный герб
                # Вейла)» starts another kingdom, so the heading before it ends.
                if "герб" in line:
                    group, team, member = None, None, None
                continue
            m = CHAPTERS.match(line)
            if m and " — " in line:
                lo, hi = int(m[1]), int(m[2] or m[1])
                chronology.append({"from": lo, "to": hi, "when": line.split(" — ", 1)[1].strip()})
                continue
            if line.endswith(":"):
                head = line[:-1].strip()
                team = None
                if head.startswith("Команда") or re.match(r"^[A-Z]{3,4}\b", head):
                    names, epithets, _ = split_head(head)
                    team = add([names[0]], epithets, "", "", section, group, "team")
                    team["members"] = []
                else:
                    group = head
                member = last = None
                continue
            if line.startswith("Команда ") and ":" in line and " — " not in line:
                # «Команда ASRB: Аш Сильвер, Гарнет Стронг, …»
                head, rest = line.split(":", 1)
                line = f"{head} — {rest.strip()}"
            if line.startswith("[") and " — " in line:
                head, desc = line.strip("[]").split(" — ", 1)
                names, epithets, years = split_head(head)
                last = add(names, epithets, years, desc, section, group, "unit")
                # The people under a unit serve in it: «Железноногий» after «[Фульмита …]».
                group, member = last["name"], None
                continue
            if " — " not in line:
                if "Курс" in line:
                    group, team, member, last = line.rstrip("."), None, None, None
                    continue
                short = len(re.sub(r"\(.*?\)", "", line).split()) <= 4
                if team is not None and (short or "," in line):
                    # Members: «Жон Арк (лидер).» or «Коко Адель, Фокс Алистер, …»
                    names = [n.strip(" .") for n in re.sub(r"\(.*?\)", "", line).split(",")]
                    for n in filter(None, names):
                        member = add([n], [], "", "", section, group, None)
                        member["team"] = team["name"]
                        team["members"].append(n)
                    if len(names) > 1:
                        member = None
                    continue
                if member is not None:
                    member["text"] = (member["text"] + " " + line).strip()
                continue  # an author's note
            head, desc = line.split(" — ", 1)
            if len(re.sub(r"\(.*?\)", "", head).split()) > 8:
                continue  # an author's note with a dash in it
            if member is not None:
                # Under a student: the Semblance, «Слабые Точки/Победа — …».
                member["semblance"] = f"{head.strip()} — {desc.strip()}"
                continue
            if head.startswith("Команда "):
                names, epithets, _ = split_head(head)
                t = add([names[0]], epithets, "", "", section, group, "team")
                t["members"] = [n.strip(" .") for n in desc.split(",") if n.strip(" .")]
                for n in t["members"]:
                    add([n], [], "", "", section, group)["team"] = t["name"]
                continue
            names, epithets, years = split_head(head)
            if not names:
                continue
            for person in people(names[0]):
                last = add([person] + names[1:], epithets, years, desc, section, group)
    return {"entries": merge_members(entries), "chronology": chronology}


def merge_members(entries: list[dict]) -> list[dict]:
    """A team lists «Жон Арк», who has his own entry under the Arcs: when
    exactly one present-day main-world entry has the name, the team and the
    Semblance go to it and the member's line is dropped."""
    out = []
    for e in entries:
        if "team" in e and not e["text"]:
            same = [x for x in entries if x is not e and "team" not in x and x["world"] == "main"
                    and x["era"] != "ЭК" and norm(x["name"]) == norm(e["name"])]
            if len(same) == 1:
                same[0]["team"] = e["team"]
                if e.get("semblance"):
                    same[0]["semblance"] = e["semblance"]
                continue
        out.append(e)
    for n, e in enumerate(out, 1):
        e["id"] = f"g{n:04d}"
    return out


def read_sections(path: Path) -> list[tuple[str, list[str]]]:
    root = ET.fromstring(read_fb2(path))
    out = []
    for body in root.findall(NS + "body"):
        if body.get("name"):
            continue
        for sec in body.findall(NS + "section"):
            title = sec.find(NS + "title")
            name = text_of(title) if title is not None else ""
            out.append((name.split(": ", 1)[-1], list(paragraphs(sec))))
    return out


def build(book: str, path: Path) -> dict:
    data = parse_lines(read_sections(path))
    data["source"] = path.name
    write_json(work_dir(book) / "glossary.json", data)
    return data


def load(book: str) -> dict | None:
    path = work_dir(book) / "glossary.json"
    return read_json(path) if path.exists() else None


# --- lookup --------------------------------------------------------------------

def same_word(q: str, f: str) -> bool:
    """One word, allowing for case endings and a respelt ending:
    «Озпина» ~ «Озпин», «Арком» ~ «Арк», «Хейль» ~ «Хейли»; not «Бранвен» ~ «Бранан»."""
    if q == f:
        return True
    n = 0
    for a, b in zip(q, f):
        if a != b:
            break
        n += 1
    tails = (len(q) - n, len(f) - n)
    return n >= 3 and max(tails) <= 2 and (min(tails) == 0 or n >= 4)


def score(query: str, form: str, inside: bool = False) -> int:
    """3 the same form, 2 every word of the query in it (or, with inside,
    every word of it in the query), 1 some longer word, 0 none."""
    q, f = norm(query), norm(form)
    if q == f:
        return 3
    qw, fw = q.split(), f.split()
    hits = [any(same_word(a, b) for b in fw) for a in qw]
    if all(hits) and len(qw) == len(fw):
        return 3 if len(qw) > 1 else 2
    if all(hits):
        return 2
    if inside and all(any(same_word(a, b) for a in qw) for b in fw) and len(f) >= 4:
        return 2  # «Аяме Ноэда» has «Аяме», of «Старейшина Аяме»
    if any(h for a, h in zip(qw, hits) if len(a) >= 4):
        return 1
    return 0


def lookup(glossary: dict, query: str, least: int = 1) -> list[tuple[int, dict]]:
    found = []
    for e in glossary["entries"]:
        s = max((score(query, f, f not in e["epithets"]) for f in e["forms"]), default=0)
        if s >= least:
            found.append((s, e))
    found.sort(key=lambda se: -se[0])
    return found


def line(e: dict, width: int = 0) -> str:
    bits = [e["name"]]
    if e["epithets"]:
        bits[0] += f" ({', '.join(e['epithets'])})"
    meta = [m for m in (e["years"], e["section"], e["group"], e.get("team")) if m]
    if e["world"] == "echo":
        meta.insert(0, "ЭХО")
    head = f"{bits[0]} · {' · '.join(meta)}"
    text = e["text"]
    if e.get("semblance"):
        text = (text + " Подобие: " + e["semblance"]).strip()
    if e.get("members"):
        text = (text + " Состав: " + ", ".join(e["members"])).strip()
    if width and len(text) > width:
        text = text[:width].rsplit(" ", 1)[0] + "…"
    return f"{head}\n    {text}" if text else head


def who(book: str, query: str, full: bool = False, limit: int = 8) -> None:
    glossary = load(book)
    if glossary is None:
        raise SystemExit(f"no work/{book}/glossary.json: run bookgraph glossary build {book} FILE")
    found = lookup(glossary, query)
    if not found:
        print(f"«{query}»: not in the glossary")
        return
    best = found[0][0]
    shown = [e for s, e in found if s == best or s >= 2][:limit]
    for e in shown:
        print(line(e, 0 if full else 220))
    if len(found) > len(shown):
        print(f"(and {len(found) - len(shown)} weaker matches)")
