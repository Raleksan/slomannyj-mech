"""bookgraph eval: how good a run is, in numbers.

Two kinds of measure. Shape measures need only the run's own files in
work/<book>/: how many entities were seen once, how many event places
don't resolve, how importance and links are spread. Gold measures compare
the run with the hand-checked answers in gold/<book>/ (see docs/gold.md).

Every run writes work/<book>/eval.json. With --save, it also becomes
gold/<book>/baseline.json, which later runs are printed against.
"""

import statistics
from collections import Counter
from pathlib import Path

from .store import ROOT, read_json, work_dir, write_json

KINDS = ("characters", "places", "groups")
SPEECH_VERBS = ("сказал", "сказала", "спросил", "спросила", "ответил", "ответила",
                "крикнул", "крикнула", "прошептал", "прошептала", "произнёс", "произнесла",
                "произнес", "пробормотал", "пробормотала", "воскликнул", "воскликнула")


def gold_dir(book: str) -> Path:
    return ROOT / "gold" / book


def share(part: int, whole: int) -> dict:
    return {"n": part, "of": whole, "value": round(part / whole, 4) if whole else None}


def shape(book: str) -> dict:
    """Measures of a run that need no gold answers."""
    wd = work_dir(book)
    out: dict = {}
    if (wd / "entities.json").exists():
        ents = read_json(wd / "entities.json")
        for kind in KINDS:
            items = ents[kind]
            out[f"singletons.{kind}"] = share(sum(len(e["chunks"]) == 1 for e in items), len(items))
    if (wd / "threads.json").exists():
        threads = read_json(wd / "threads.json")
        events = threads["events"]
        by_id = {e["id"]: e for e in events}
        placed = [e for e in events if e.get("where_text")]
        out["places.unresolved"] = share(sum(e["where"] is None for e in placed), len(placed))
        out["importance.3"] = share(sum(e["importance"] == 3 for e in events), len(events))
        out["storylines"] = {"value": len(threads["storylines"])}
        out["events.without_storyline"] = share(sum(not e["storylines"] for e in events), len(events))
        chapters = sorted({e["chapter"] for e in events})
        index = {c: i for i, c in enumerate(chapters)}
        edges = [(by_id[x["src"]], by_id[x["dst"]]) for x in threads["edges"]
                 if x["src"] in by_id and x["dst"] in by_id]
        far = [abs(index[b["chapter"]] - index[a["chapter"]]) for a, b in edges
               if a["chapter"] != b["chapter"]]
        out["links.same_chunk"] = share(sum(a["chunk"] == b["chunk"] for a, b in edges), len(edges))
        out["links.cross_chapter"] = share(len(far), len(edges))
        out["links.max_chapters"] = {"value": max(far, default=0)}
        out["links.over_20_chapters"] = share(sum(d > 20 for d in far), len(edges))
    if (wd / "chapters.json").exists():
        paras = [p for ch in read_json(wd / "chapters.json")["chapters"] for s in ch["scenes"] for p in s]
        speech = [p for p in paras if p.startswith("—")]
        out["dialogue"] = share(len(speech), len(paras))
        tagged = sum(any(v in p.split("—", 2)[-1][:40].lower() for v in SPEECH_VERBS)
                     for p in speech if p.count("—") >= 2)
        out["dialogue.speech_verb_tag"] = share(tagged, len(speech))
    if (wd / "chunks.json").exists():
        counts = [sum(1 for p in c["text"].split("\n\n") if p.strip() != "***")
                  for c in read_json(wd / "chunks.json")]
        out["chunk.paragraphs_median"] = {"value": statistics.median(counts)}
        out["chunk.paragraphs_max"] = {"value": max(counts)}
    return out


def value(m: dict):
    return m.get("value")


def table(now: dict, before: dict | None) -> str:
    rows = []
    for name, m in now.items():
        v = value(m)
        text = "—" if v is None else (f"{v:.1%}" if "n" in m else f"{v:g}")
        if "n" in m:
            text += f" ({m['n']}/{m['of']})"
        if "low" in m:
            text += f"  [{m['low']:.1%}–{m['high']:.1%}]"
        if before and name in before and value(before[name]) is not None and v is not None:
            old = value(before[name])
            diff = v - old
            if diff:
                text += f"  {'+' if diff > 0 else ''}{diff:.1%}" if "n" in m else f"  ({old:g} before)"
        rows.append((name, text))
    width = max((len(n) for n, _ in rows), default=0)
    return "\n".join(f"{n:<{width}}  {t}" for n, t in rows)


def run(book: str, save: bool = False) -> None:
    result = {"shape": shape(book)}
    gd = gold_dir(book)
    if (gd / "answers").exists():
        from . import gold

        result["gold"] = gold.score(book)
    write_json(work_dir(book) / "eval.json", result)
    base_path = gd / "baseline.json"
    base = read_json(base_path) if base_path.exists() else {}
    for part in ("shape", "gold"):
        if result.get(part):
            print(f"## {part}" + (" (against baseline)" if base.get(part) else ""))
            print(table(result[part], base.get(part)))
    if save:
        gd.mkdir(parents=True, exist_ok=True)
        write_json(base_path, result)
        print(f"saved as {base_path.relative_to(ROOT)}")
