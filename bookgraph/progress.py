"""Progress of the running stage, for `bookgraph progress`.

A stage calls Progress.tick() after each item; that rewrites
work/<book>/progress.json with counts, token totals and an ETA. show() reads
it back, adds the GPU's load and llama-server's busy slots when they can be
reached, and the most mentioned characters so far.
"""

import collections
import json
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime, timedelta

from .store import read_json, work_dir, write_json


class Progress:
    def __init__(self, book: str, stage: str, total: int, skipped: int = 0) -> None:
        self.path = work_dir(book) / "progress.json"
        self.state = {
            "stage": stage, "started": time.time(), "updated": time.time(),
            "total": total, "skipped": skipped, "done": 0, "failed": 0,
            "prompt_tokens": 0, "gen_tokens": 0, "recent": [], "finished": False,
        }
        self.write()

    def tick(self, item: str, seconds: float, note: str, stats=None, failed: bool = False) -> None:
        s = self.state
        s["failed" if failed else "done"] += 1
        if stats is not None:
            s["prompt_tokens"], s["gen_tokens"] = stats.prompt, stats.completion
        s["recent"] = ([{"item": item, "seconds": round(seconds), "note": note,
                         "at": time.time()}] + s["recent"])[:8]
        self.write()

    def finish(self) -> None:
        self.state["finished"] = True
        self.write()

    def write(self) -> None:
        self.state["updated"] = time.time()
        write_json(self.path, self.state)


def bar(frac: float, width: int = 30) -> str:
    full = int(frac * width)
    return "█" * full + "░" * (width - full)


def span(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))


def gpu() -> str:
    if not shutil.which("nvidia-smi"):
        return ""
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total,power.draw",
         "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip()
    if not out:
        return ""
    name, util, used, total, power = [x.strip() for x in out.splitlines()[0].split(",")]
    return f"{name}: {util}% busy, {int(used) / 1024:.1f}/{int(total) / 1024:.0f} GB, {float(power):.0f} W"


def slots(base: str) -> str:
    try:
        with urllib.request.urlopen(base + "/slots", timeout=3) as r:
            data = json.load(r)
    except Exception:
        return ""
    busy = sum(1 for s in data if s.get("is_processing"))
    return f"llama-server: {busy}/{len(data)} slots busy"


def top_characters(book: str, n: int = 12) -> list[tuple[str, int]]:
    count: collections.Counter = collections.Counter()
    for path in (work_dir(book) / "extract").glob("*.json"):
        facts = read_json(path)["facts"]
        count.update({c["name"] for c in facts["characters"]})
    return count.most_common(n)


def show(book: str, base: str) -> str:
    path = work_dir(book) / "progress.json"
    if not path.exists():
        return f"{book}: no stage has run yet"
    s = read_json(path)
    now = time.time()
    finished = s["done"] + s["failed"]
    total = max(s["total"], 1)
    elapsed = (s["updated"] if s["finished"] else now) - s["started"]
    lines = [f"{book} · stage {s['stage']} · "
             + ("finished" if s["finished"] else f"running, last update {span(now - s['updated'])} ago")]
    lines.append(f"{bar(finished / total)} {finished}/{s['total']} "
                 f"({100 * finished / total:.0f}%), {s['failed']} failed, "
                 f"{s['skipped']} cached from earlier runs")
    rate = finished / elapsed if elapsed > 0 and finished else 0
    eta = (s["total"] - finished) / rate if rate else None
    lines.append(f"elapsed {span(elapsed)}" + (f", {rate * 3600:.0f} items/h" if rate else "")
                 + (f", ETA {span(eta)} (about {(datetime.now() + timedelta(seconds=eta)):%H:%M})"
                    if eta and not s["finished"] else ""))
    if s["gen_tokens"]:
        lines.append(f"tokens: {s['prompt_tokens']:,} read, {s['gen_tokens']:,} written, "
                     f"{s['gen_tokens'] / max(elapsed, 1):.0f} written/s")
    for extra in (gpu(), slots(base)):
        if extra:
            lines.append(extra)
    if s["recent"]:
        lines.append("recent:")
        for r in s["recent"][:5]:
            lines.append(f"  {datetime.fromtimestamp(r['at']):%H:%M:%S} {r['item']} "
                         f"{r['seconds']}s · {r['note']}")
    if s["stage"] == "extract":
        top = top_characters(book)
        if top:
            lines.append("most present characters so far (chunks): "
                         + ", ".join(f"{name} {n}" for name, n in top))
    return "\n".join(lines)
