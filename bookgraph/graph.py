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

from .store import ROOT
from .vault import Vault, out_dir, safe

TEMPLATES = ROOT / "templates"
# Storylines past this many (by event count) share one gray: eight
# categorical hues is the most that stay apart, and the row label carries
# identity anyway.
COLORED = 7
CAST = 80


def build(book: str) -> dict:
    v = Vault(book)
    vault_name = safe(v.meta["title"])
    chapter_index = {c["id"]: i for i, c in enumerate(v.meta["chapters"])}

    def uri(item: str) -> str | None:
        if item not in v.files:
            return None
        return f"obsidian://open?vault={quote(vault_name)}&file={quote(v.files[item])}"

    sizes = collections.Counter(s for e in v.events for s in e["storylines"])
    lines = sorted(v.storylines, key=lambda s: -sizes[s["id"]])
    cast = [e for e in v.entities["characters"] if e["mentions"] >= 2][:CAST]
    cast_ids = {e["id"] for e in cast}
    return {
        "title": v.meta["title"], "author": v.meta["author"],
        "chapters": [{"id": c["id"], "title": c["title"], "uri": uri(c["id"]),
                      "oneline": v.notes.get(c["id"], {}).get("oneline", "")}
                     for c in v.meta["chapters"]],
        "storylines": [{"id": s["id"], "name": s["name"], "description": s["description"],
                        "slot": i + 1 if i < COLORED else 0, "events": sizes[s["id"]],
                        "uri": uri(s["id"])} for i, s in enumerate(lines)],
        "events": [{"id": e["id"], "ch": chapter_index[e["chapter"]], "title": e["title"],
                    "what": e["what"], "imp": e["importance"], "kind": e["kind"],
                    "who": e["who"], "where": v.titles.get(e["where"], e["where_text"]) if e["where"] else e["where_text"],
                    "sl": e["storylines"],
                    "uri": (uri(e["chapter"]) or "") + quote(f"#^{e['id']}") if uri(e["chapter"]) else None}
                   for e in v.events],
        "characters": [{"id": e["id"], "name": e["name"], "mentions": e["mentions"],
                        "about": v.notes.get(e["id"], {}).get("summary") or (e["about"] or [""])[0],
                        "uri": uri(e["id"])} for e in cast],
        "names": {e["id"]: e["name"] for e in v.entities["characters"]},
        "edges": [{"s": x["src"], "t": x["dst"], "type": x["type"], "why": x["why"]}
                  for x in v.edges if x["src"] in v.by_event and x["dst"] in v.by_event],
        "cast": sorted(cast_ids),
    }


def run(book: str) -> Path:
    data = build(book)
    page = (TEMPLATES / "graph.html").read_text(encoding="utf-8")
    lib = (TEMPLATES / "cytoscape.min.js").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = (page.replace("/*CYTOSCAPE*/", lib)
                .replace("/*DATA*/null", payload)
                .replace("{{TITLE}}", data["title"]))
    path = out_dir(book) / "graph.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    # A copy inside the vault, where the overview note links to it.
    vault = out_dir(book) / safe(data["title"])
    if vault.is_dir():
        (vault / "graph.html").write_text(page, encoding="utf-8")
    print(f"graph: {len(data['events'])} events, {len(data['characters'])} characters, "
          f"{len(data['edges'])} links in {path}")
    return path
