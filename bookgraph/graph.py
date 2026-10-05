"""Stage 6b: out/<book>/graph.html, one self-contained page. No model.

Two views over the same data: the plot (events on storyline rows, in book
order, with cause and continuation arrows) and the cast (characters linked
by the events they share). Clicking anything shows its details and opens
the matching Obsidian note. The data and Cytoscape.js are inlined, so the
page works offline.
"""

import collections
import json
from pathlib import Path
from urllib.parse import quote

from .store import ROOT, read_json, work_dir
from .vault import Vault, out_dir, safe

TEMPLATES = ROOT / "templates"
# Storylines past this many share one gray: eight categorical hues is the
# most that stay apart, and the row label carries identity anyway. The lines
# the page opens with get theirs first, then the biggest.
COLORED = 8
CAST = 80


def obsidian_uri(v: Vault, item: str, block: str | None = None) -> str:
    file = v.files[item] + (f"#^{block}" if block else "")
    return f"obsidian://open?vault={quote(safe(v.meta['title']))}&file={quote(file)}"


def build(book: str, link=obsidian_uri) -> dict:
    """link(vault, item, block) is where clicking an item leads; the site passes its own."""
    v = Vault(book)
    chapter_index = {c["id"]: i for i, c in enumerate(v.meta["chapters"])}

    def uri(item: str, block: str | None = None) -> str | None:
        return link(v, item, block) if item in v.files else None

    sizes = collections.Counter(s for e in v.events for s in e["storylines"])
    lines = sorted(v.storylines, key=lambda s: -sizes[s["id"]])
    shown = default_lines(book, v)
    by_claim = shown + [s["id"] for s in lines if s["id"] not in shown]
    slots = {sid: i + 1 for i, sid in enumerate(by_claim[:COLORED])}
    cast = [e for e in v.entities["characters"] if e["mentions"] >= 2][:CAST]
    cast_ids = {e["id"] for e in cast}
    return {
        "title": v.meta["title"], "author": v.meta["author"],
        "chapters": [{"id": c["id"], "title": c["title"], "uri": uri(c["id"]),
                      "oneline": v.notes.get(c["id"], {}).get("oneline", "")}
                     for c in v.meta["chapters"]],
        "storylines": [{"id": s["id"], "name": s["name"], "description": s["description"],
                        "slot": slots.get(s["id"], 0), "events": sizes[s["id"]],
                        "uri": uri(s["id"])} for s in lines],
        "events": [{"id": e["id"], "ch": chapter_index[e["chapter"]], "title": e["title"],
                    "what": e["what"], "imp": e["importance"], "kind": e["kind"],
                    "who": e["who"], "where": v.titles.get(e["where"], e["where_text"]) if e["where"] else e["where_text"],
                    "sl": e["storylines"],
                    "uri": uri(e["chapter"], e["id"])}
                   for e in v.events],
        "characters": [{"id": e["id"], "name": e["name"], "mentions": e["mentions"],
                        "about": v.notes.get(e["id"], {}).get("summary") or (e["about"] or [""])[0],
                        "uri": uri(e["id"])} for e in cast],
        "names": {e["id"]: e["name"] for e in v.entities["characters"]},
        "edges": [{"s": x["src"], "t": x["dst"], "type": x["type"], "why": x["why"]}
                  for x in v.edges if x["src"] in v.by_event and x["dst"] in v.by_event],
        "cast": sorted(cast_ids),
        "default_lines": shown,
        # 1 every event, 2 notable ones, 3 turning points only.
        "default_importance": view_settings(book).get("importance", 2),
    }


def view_settings(book: str) -> dict:
    """How the page opens, from work/<book>/graph.json:
    {"lines": [storyline names], "importance": 1-3}."""
    path = work_dir(book) / "graph.json"
    return read_json(path) if path.exists() else {}


def default_lines(book: str, v: Vault) -> list[str]:
    """Storylines the plot opens with; none listed means all of them."""
    names = view_settings(book).get("lines", [])
    ids = {s["name"]: s["id"] for s in v.storylines}
    missing = [n for n in names if n not in ids]
    if missing:
        print(f"graph: no such storylines in graph.json: {', '.join(missing)}")
    return [ids[n] for n in names if n in ids]


def page(data: dict, open_label: str = "Открыть в Obsidian →",
         open_hint: str = "открыть заметку в Obsidian", home: str = "") -> str:
    html = (TEMPLATES / "graph.html").read_text(encoding="utf-8")
    lib = (TEMPLATES / "cytoscape.min.js").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return (html.replace("/*CYTOSCAPE*/", lib)
                .replace("/*DATA*/null", payload)
                .replace("{{OPEN}}", open_label)
                .replace("{{OPEN_HINT}}", open_hint)
                .replace("<!--HOME-->", home)
                .replace("{{TITLE}}", data["title"]))


def run(book: str) -> Path:
    data = build(book)
    page_ = page(data)
    path = out_dir(book) / "graph.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page_, encoding="utf-8")
    # A copy inside the vault, where the overview note links to it.
    vault = out_dir(book) / safe(data["title"])
    if vault.is_dir():
        (vault / "graph.html").write_text(page_, encoding="utf-8")
    print(f"graph: {len(data['events'])} events, {len(data['characters'])} characters, "
          f"{len(data['edges'])} links in {path}")
    return path
