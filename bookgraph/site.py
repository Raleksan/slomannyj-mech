"""Stage 6c: out/<book>/site/, a static website from the vault. No model.

The same notes as the Obsidian vault, turned into plain HTML pages that
GitHub Pages (or any static host, or a browser opening index.html) can
serve as they are:
  index.html             the overview
  <Папка>/index.html     a list of the folder's notes
  <Папка>/<note>.html    one page per note, with the pages that link to it
  graph.html             the storyline graph, its links leading to the pages
  search.js              titles, aliases and events for the search box
Every link is relative, so the site works under any path.
"""

import collections
import html
import json
import re
import shutil
from pathlib import Path
from urllib.parse import quote

from . import graph
from .vault import FOLDERS, Vault, out_dir

INDEX = "00 Обзор"
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#\^([\w-]+))?(?:\|([^\]]+))?\]\]")
MDLINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
BLOCK_ID = re.compile(r"\s\^([\w-]+)$")
KIND_LABELS = {"chapters": "глава", "characters": "персонаж", "places": "место",
               "groups": "группа", "storylines": "сюжетная линия"}


def url(path: str, depth: int, block: str | None = None) -> str:
    """Link from a page `depth` folders down to the note at vault path `path`."""
    target = "index.html" if path == INDEX else quote(path) + ".html"
    return "../" * depth + target + (f"#{block}" if block else "")


class Site:
    def __init__(self, book: str) -> None:
        self.book = book
        self.v = Vault(book)
        self.pages = self.v.pages()
        self.chapter_order = {self.v.files[c["id"]]: i for i, c in enumerate(self.v.meta["chapters"])}
        # Wikilinks name a note by its file name alone.
        self.by_name = {path.split("/")[-1]: path for path in self.pages}
        self.backlinks: dict[str, set[str]] = collections.defaultdict(set)
        for path, text in self.pages.items():
            for m in WIKILINK.finditer(text):
                target = self.by_name.get(m.group(1))
                if target and target != path:
                    self.backlinks[target].add(path)
        self.page_titles = {path: self.title_of(text, path) for path, text in self.pages.items()}

    @staticmethod
    def title_of(text: str, path: str) -> str:
        m = re.search(r"^# (.+)$", text, re.M)
        return m.group(1) if m else path.split("/")[-1]

    # Markdown, only as much of it as vault.py writes.

    def inline(self, text: str, depth: int) -> str:
        # Links become placeholders first, so emphasis can wrap them.
        links: list[str] = []

        def link(m: re.Match) -> str:
            if m.group(1) is not None:
                name, block, label = m.group(1), m.group(2), m.group(3) or m.group(1)
                path = self.by_name.get(name)
                label = html.escape(label, quote=False)
                links.append(f'<a href="{url(path, depth, block)}">{label}</a>' if path else label)
            else:
                links.append(f'<a href="{html.escape(m.group(5))}">{html.escape(m.group(4), quote=False)}</a>')
            return f"\x00{len(links) - 1}\x00"

        text = re.sub(f"{WIKILINK.pattern}|{MDLINK.pattern}", link, text)
        text = html.escape(text, quote=False)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
        return re.sub("\x00(\\d+)\x00", lambda m: links[int(m.group(1))], text)

    def body(self, text: str, depth: int) -> str:
        lines = text.split("\n")
        if lines and lines[0] == "---":
            lines = lines[lines.index("---", 1) + 1:]
        out: list[str] = []
        para: list[str] = []
        open_lists = 0  # nesting depth of the <ul> now open

        def close_para():
            if para:
                out.append(f"<p>{self.inline(' '.join(para), depth)}</p>")
                para.clear()

        def close_lists(to: int = 0):
            nonlocal open_lists
            while open_lists > to:
                out.append("</li></ul>")
                open_lists -= 1

        for line in lines:
            item = re.match(r"^(\t*)- (.*)$", line)
            if item:
                close_para()
                level = len(item.group(1)) + 1
                content = item.group(2)
                block = BLOCK_ID.search(content)
                attr = ""
                if block:
                    content = content[:block.start()]
                    attr = f' id="{block.group(1)}"'
                if level > open_lists:
                    while open_lists < level:
                        out.append("<ul>")
                        open_lists += 1
                else:
                    close_lists(level)
                    out.append("</li>")
                out.append(f"<li{attr}>{self.inline(content, depth)}")
                continue
            close_lists()
            if not line.strip():
                close_para()
            elif m := re.match(r"^(#{1,3}) (.*)$", line):
                close_para()
                n = len(m.group(1))
                out.append(f"<h{n}>{self.inline(m.group(2), depth)}</h{n}>")
            elif line.startswith("> "):
                close_para()
                out.append(f"<blockquote>{self.inline(line[2:], depth)}</blockquote>")
            elif line.startswith("Интерактивный граф:"):
                close_para()
                out.append(f'<p><a class="button" href="{"../" * depth}graph.html">'
                           "Интерактивный граф сюжета →</a></p>")
            else:
                para.append(line)
        close_para()
        close_lists()
        return "\n".join(out)

    # Pages.

    def layout(self, title: str, content: str, depth: int, current: str = "") -> str:
        up = "../" * depth
        nav = [f'<a href="{up}index.html"{" aria-current=page" if current == INDEX else ""}>Обзор</a>',
               f'<a href="{up}graph.html">Граф</a>']
        for folder in FOLDERS.values():
            mark = " aria-current=page" if current == folder else ""
            nav.append(f'<a href="{up}{quote(folder)}/index.html"{mark}>{folder}</a>')
        book = html.escape(self.v.meta["title"])
        head_title = book if title == self.v.meta["title"] else f"{html.escape(title)} — {book}"
        return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{head_title}</title>
<link rel="stylesheet" href="{up}style.css">
</head>
<body>
<header>
  <a class="book" href="{up}index.html">{book}</a>
  <nav>{"".join(nav)}</nav>
  <div class="search">
    <input id="q" type="search" placeholder="Поиск: персонаж, место, событие…" autocomplete="off"
           aria-label="Поиск по сайту">
    <ol id="hits" hidden></ol>
  </div>
</header>
<main>
{content}
</main>
<script>const ROOT = "{up}";</script>
<script src="{up}site.js"></script>
</body>
</html>
"""

    def note(self, path: str) -> str:
        depth = path.count("/")
        content = self.body(self.pages[path], depth)
        refs = sorted(self.backlinks.get(path, ()), key=lambda p: (p.split("/")[0], self.chapter_order.get(p, 0), p))
        if refs and path != INDEX:
            groups = collections.defaultdict(list)
            for ref in refs:
                groups[ref.split("/")[0] if "/" in ref else ""].append(ref)
            content += "\n<section class=\"backlinks\"><h2>Ссылаются сюда</h2>"
            for folder, items in groups.items():
                links = ", ".join(f'<a href="{url(r, depth)}">{html.escape(self.page_titles[r])}</a>'
                                  for r in items)
                content += f"<p><span class=\"muted\">{html.escape(folder or 'Обзор')}:</span> {links}</p>"
            content += "</section>"
        current = path.split("/")[0] if "/" in path else INDEX
        return self.layout(self.page_titles[path], content, depth, current)

    def folder_index(self, kind: str) -> str:
        v = self.v
        folder = FOLDERS[kind]
        rows = []
        if kind == "chapters":
            for c in v.meta["chapters"]:
                rows.append((c["id"], v.notes.get(c["id"], {}).get("oneline", "")))
        elif kind == "storylines":
            sizes = collections.Counter(s for e in v.events for s in e["storylines"])
            for s in sorted(v.storylines, key=lambda s: -sizes[s["id"]]):
                rows.append((s["id"], f"{s['description']} ({sizes[s['id']]} событий)"))
        else:
            for e in v.entities[kind]:
                if e["id"] in v.files:
                    summary = v.notes[e["id"]].get("summary", "")
                    first = re.split(r"(?<=[.!?])\s", summary, maxsplit=1)[0]
                    rows.append((e["id"], first))
        items = "\n".join(
            f'<li><a href="{quote(v.files[i].split("/")[-1])}.html">{html.escape(v.titles[i])}</a>'
            + (f' <span class="muted">— {html.escape(text)}</span>' if text else "") + "</li>"
            for i, text in rows)
        note = " По числу упоминаний." if kind in ("characters", "places", "groups") else ""
        content = (f"<h1>{folder}</h1><p class=\"muted\">{len(rows)}.{note}</p>\n"
                   f"<ul class=\"index\">\n{items}\n</ul>")
        return self.layout(folder, content, 1, folder)

    def search_index(self) -> list[dict]:
        v = self.v
        entries = [{"t": v.meta["title"], "k": "обзор", "u": "index.html"}]
        for c in v.meta["chapters"]:
            entries.append({"t": c["title"], "k": KIND_LABELS["chapters"], "u": url(v.files[c["id"]], 0)})
        for kind in ("characters", "places", "groups"):
            for e in v.entities[kind]:
                if e["id"] in v.files:
                    aliases = [a for a in e["aliases"] if a.lower() != e["name"].lower()][:20]
                    entries.append({"t": e["name"], "k": KIND_LABELS[kind], "u": url(v.files[e["id"]], 0),
                                    "a": " · ".join(aliases)})
        for s in v.storylines:
            entries.append({"t": s["name"], "k": KIND_LABELS["storylines"], "u": url(v.files[s["id"]], 0)})
        for e in v.events:
            if e["chapter"] in v.files:
                entries.append({"t": e["title"], "k": "событие · " + v.titles[e["chapter"]],
                                "u": url(v.files[e["chapter"]], 0, e["id"]), "a": e["what"]})
        return entries

    def write(self, root: Path) -> int:
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        for folder in FOLDERS.values():
            (root / folder).mkdir()
        for path in self.pages:
            target = root / ("index.html" if path == INDEX else f"{path}.html")
            target.write_text(self.note(path), encoding="utf-8")
        for kind, folder in FOLDERS.items():
            (root / folder / "index.html").write_text(self.folder_index(kind), encoding="utf-8")
        data = graph.build(self.book, link=lambda v, item, block=None: url(v.files[item], 0, block))
        home = '<a class="home" href="index.html">← Сайт</a>'
        (root / "graph.html").write_text(graph.page(data, "Открыть страницу →", "перейти на её страницу", home), encoding="utf-8")
        assets = Path(__file__).resolve().parent.parent / "templates" / "site"
        for name in ("style.css", "site.js"):
            shutil.copy(assets / name, root / name)
        payload = json.dumps(self.search_index(), ensure_ascii=False, separators=(",", ":"))
        (root / "search.js").write_text(f"window.SEARCH = {payload};\n", encoding="utf-8")
        # GitHub Pages: serve the files as they are, without Jekyll.
        (root / ".nojekyll").write_text("")
        return len(self.pages) + len(FOLDERS) + 1


def run(book: str, root: Path | None = None) -> Path:
    site = Site(book)
    root = root or out_dir(book) / "site"
    n = site.write(root)
    print(f"site: {n} pages in {root}")
    return root
