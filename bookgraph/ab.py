"""bookgraph ab: the same chunks through two models, side by side.

  bookgraph ab NAME [-j 3]      extract the sample with whatever model the
                                server runs, into work/NAME/ab/<model>/
  bookgraph ab NAME --report    compare every model in work/NAME/ab/

The sample is the chunks the gold event packets come from, topped up to
SAMPLE spread over the book. Each answer is kept, failures with the model's
last raw text, so refusals can be told from broken JSON, and the outputs
can be scored against the gold set later without a GPU.

PLAN.md's rule: keep the abliterated model unless it is worse, or the
original refuses parts of the book.
"""

import asyncio
import re
import time
from collections import defaultdict

from .extract import SYSTEM, prompt
from .llm import Client, dump
from .schemas import ChunkFacts
from .store import ROOT, read_json, work_dir, write_json

SAMPLE = 40
REFUSAL = re.compile(r"не могу|не буду|не стану|извините|к сожалению, я|I can(no|')t|I'm sorry|"
                     r"I am sorry|as an AI|не имею права|неприемлем", re.I)


def sample(book: str) -> list[dict]:
    chunks = read_json(work_dir(book) / "chunks.json")
    packets = ROOT / "gold" / book / "packets" / "event.json"
    chosen = list(dict.fromkeys(t["data"]["chunk"] for t in read_json(packets))) if packets.exists() else []
    rest = [c["id"] for c in chunks if c["id"] not in chosen]
    need = max(0, SAMPLE - len(chosen))
    if need and rest:
        step = len(rest) / need
        chosen += [rest[int(k * step)] for k in range(need)]
    by_id = {c["id"]: c for c in chunks}
    return [by_id[c] for c in chosen if c in by_id]


def label(model: str) -> str:
    return re.sub(r"[^\w.-]+", "_", model)


async def run(book: str, concurrency: int) -> None:
    wd = work_dir(book)
    meta = read_json(wd / "chapters.json")
    client = Client(concurrency)
    try:
        model = await client.model()
        out = wd / "ab" / label(model)
        out.mkdir(parents=True, exist_ok=True)
        todo = [c for c in sample(book) if not (out / f"{c['id']}.json").exists()]
        print(f"{model}: {len(todo)} chunks to extract, {concurrency} at a time")
        done = 0

        async def one(c: dict) -> None:
            nonlocal done
            t = time.monotonic()
            before = 0  # see measure(): counted from the start of the run
            row = {"chunk": c["id"], "model": model}
            try:
                facts = await client.ask(ChunkFacts, SYSTEM, prompt(meta, c), kind="extract", max_tokens=6144)
                row["facts"] = dump(facts)
            except Exception as e:
                row["error"] = str(e)
            row["seconds"] = round(time.monotonic() - t, 1)
            row["tokens"] = client.stats.completion - before
            write_json(out / f"{c['id']}.json", row)
            done += 1
            note = f"{len(row['facts']['events'])} events" if "facts" in row else "FAILED"
            print(f"[{done}/{len(todo)}] {c['id']}: {note}, {row['seconds']:.0f}s", flush=True)

        await asyncio.gather(*(one(c) for c in todo))
        print(client.stats.line())
    finally:
        await client.close()


def names(facts: dict) -> set[str]:
    from .resolve import key

    return {key(c["name"]) for c in facts.get("characters", [])}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def measure(rows: list[dict], reference: dict[str, dict]) -> dict:
    ok = [r for r in rows if "facts" in r]
    events = [e for r in ok for e in r["facts"]["events"]]
    refused = [r for r in rows if REFUSAL.search(r.get("error", "") + r.get("facts", {}).get("summary", ""))]
    shared = [r for r in ok if r["chunk"] in reference]
    # Every request starts with the run and waits for a server slot, so a
    # row's seconds and tokens count from the start of the run: the largest
    # is the run's total.
    secs = max((r["seconds"] for r in rows), default=0)
    tokens = max((r.get("tokens", 0) for r in rows), default=0)
    return {
        "chunks": len(rows),
        "failed": len(rows) - len(ok),
        "refused": len(refused),
        "no events": sum(not r["facts"]["events"] for r in ok),
        "events / chunk": round(len(events) / len(ok), 1) if ok else 0,
        "characters / chunk": round(sum(len(r["facts"]["characters"]) for r in ok) / len(ok), 1) if ok else 0,
        "turning points": f"{sum(e['importance'] == 3 for e in events) / len(events):.0%}" if events else "—",
        "same names as the run": (f"{sum(jaccard(names(r['facts']), names(reference[r['chunk']])) for r in shared) / len(shared):.0%}"
                                  if shared else "—"),
        "generated tokens": tokens,
        "minutes": round(secs / 60),
        "tokens / s": round(tokens / secs, 1) if secs else 0,
    }


def report(book: str) -> None:
    wd = work_dir(book)
    base = wd / "ab"
    models = sorted(p for p in base.iterdir() if p.is_dir()) if base.exists() else []
    if not models:
        raise SystemExit(f"nothing in {base}; run bookgraph ab {book} first")
    reference = {p.stem: read_json(p)["facts"] for p in (wd / "extract").glob("*.json")}
    rows = {m.name: [read_json(p) for p in sorted(m.glob("*.json"))] for m in models}
    table = {m: measure(r, reference) for m, r in rows.items()}
    keys = list(next(iter(table.values())))
    width = max(map(len, keys))
    cols = list(table)
    print(" " * width + "  " + "  ".join(f"{c:>24}" for c in cols))
    for k in keys:
        print(f"{k:<{width}}  " + "  ".join(f"{str(table[c][k]):>24}" for c in cols))
    if len(cols) == 2:
        a, b = (dict((r["chunk"], r) for r in rows[c]) for c in cols)
        both = [k for k in a if k in b and "facts" in a[k] and "facts" in b[k]]
        if both:
            same = sum(jaccard(names(a[k]["facts"]), names(b[k]["facts"])) for k in both) / len(both)
            print(f"\nsame character names between the two: {same:.0%} over {len(both)} chunks")
    for m, rs in rows.items():
        bad = defaultdict(list)
        for r in rs:
            if "error" in r:
                bad["refused" if REFUSAL.search(r["error"]) else "failed"].append(r)
        for kind, items in bad.items():
            print(f"\n{m}, {kind}:")
            for r in items[:5]:
                print(f"  {r['chunk']}: {r['error'][:300]}")
