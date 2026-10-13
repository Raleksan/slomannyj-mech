"""The silver set: the gold tasks answered by a bigger model than the run's.

  bookgraph gold silver NAME [-t alias,place] [-j 32] [--limit N]

Each task of gold/NAME/packets/ goes to the served model with the same
text the annotator sees and, as instructions, the same sections of
docs/gold.md: the task's rules, the tricky cases and the rulings. The
answers land in gold/NAME/silver/<task>.jsonl, in the rows gold import
writes for hand answers, plus the model's reason and name, so eval scores
the run against them the same way and measures how often the model agrees
with the hand answers.

Silver numbers are for fast comparisons between runs; a stage is accepted
on the hand answers. The judge must not be the model that made the run:
it would grade its own mistakes as right. Compare answers are asked in
both orders; when the two disagree the answer is "uncertain". The top-30
ranking is left to the hand set.
"""

import asyncio
import html
import json
import re
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, create_model

from .gold import KEEP, gold_dir
from .llm import Client, dump
from .store import ROOT, read_json

TASKS = ("alias", "place", "link", "compare", "event", "quote")
SECTIONS = {"alias": "Aliases", "place": "Event places", "link": "Links", "compare": "Importance",
            "event": "Events (before M2)", "quote": "Quotes (before M2)"}
SHARED = ("Tricky cases", "Your rulings")

ALIAS = ("same", "different", "sometimes", "uncertain", "not enough context")
LINKS = ("причина", "условие", "мотив", "продолжение", "развязка", "предвестие", "вопрос → ответ",
         "параллель", "none", "uncertain", "not enough context")
MODES = ("now", "flashback", "memory", "dream", "prophecy", "letter")
FEATURES = ("state change", "decision", "revelation", "death or injury", "irreversible",
            "object changes hands", "relationship change")
CUES = ("explicit tag", "pronoun and verb", "turn-taking", "addressee named", "gender of a verb",
        "only from the scene")

WHY = Field(description="коротко, по-русски: что в тексте решило ответ")


class Alias(BaseModel):
    why: str = WHY
    verdict: Literal[ALIAS]
    note: str = ""


class Link(BaseModel):
    why: str = WHY
    link: Literal[LINKS]
    mechanism: str = Field("", description="как именно A ведёт к B; пусто, если связи нет")


class Compare(BaseModel):
    why: str = WHY
    winner: Literal["A", "B", "equal", "uncertain"]


class Event(BaseModel):
    why: str = WHY
    verdict: Literal["correct", "details wrong", "not an event", "not in this text"]
    evidence: str = Field("", description="id абзацев через пробел, как ch007.p0142 ch007.p0143")
    mode: Literal[MODES] = "now"
    features: list[Literal[FEATURES]] = []
    missed: str = ""


def with_options(name: str, field: str, options: list[str], **extra) -> type[BaseModel]:
    """A schema whose answer must be one of the task's own options."""
    return create_model(name, why=(str, WHY), **{field: (Literal[tuple(options)], ...)}, **extra)


def schema(task: str, data: dict) -> type[BaseModel]:
    if task == "place":
        return with_options("Place", "place", [o["value"] for o in data["options"]],
                            relation=(Literal["exactly", "inside", "unclear"], "unclear"),
                            missed=(str, ""))
    if task == "quote":
        return with_options("Quote", "speaker", [o["value"] for o in data["options"]],
                            cue=(Literal[CUES], "only from the scene"), other=(str, ""))
    return {"alias": Alias, "link": Link, "compare": Compare, "event": Event}[task]


# --- what the model reads ------------------------------------------------------

def guide(task: str) -> str:
    """The sections of docs/gold.md an annotator of this task follows."""
    text = (ROOT / "docs" / "gold.md").read_text(encoding="utf-8")
    parts = re.split(r"(?m)^## ", text)
    by = {p.split("\n", 1)[0].strip(): p.split("\n", 1)[1] for p in parts[1:]}
    return "\n\n".join(f"## {name}\n{by[name].strip()}" for name in (SECTIONS[task], *SHARED))


def plain(page: str) -> str:
    """A task's html as text; the highlighted paragraph is marked ►."""
    page = re.sub(r'<p style="background:[^"]*">', "\n► ", page)
    page = re.sub(r"<br\s*/?>|</?(p|div|h3|li)[^>]*>", "\n", page)
    page = html.unescape(re.sub(r"<[^>]+>", "", page))
    return re.sub(r"\n\s*\n+", "\n", page).strip()


SYSTEM = """Ты аннотатор золотого набора для графа сюжета по роману «Сломанный Меч»
(фанфик по RWBY). Ответь на задание так, как ответил бы внимательный
аннотатор, следуя инструкции ниже. Суди только по показанному тексту и
справочнику автора, если он показан; если текста не хватает, так и ответь.
Инструкция на английском, текст книги на русском.

{guide}"""


def prompt(task: str, data: dict, swap: bool = False) -> str:
    if task == "alias":
        return (f"Вид: {data['kind']}. Пара: «{data['a']}» и «{data['b']}» (отбор: {data['stratum']}).\n\n"
                f"=== {plain(data['a_html'])}\n\n=== {plain(data['b_html'])}")
    if task == "place":
        options = "\n".join(f"- {o['value']}" for o in data["options"])
        return (f"Где: «{data['where_text']}»\n\nСобытие:\n{plain(data['card'])}\n\n"
                f"Текст:\n{plain(data['context'])}\n\nВарианты (ответь одним из них дословно):\n{options}")
    if task == "link":
        return (f"A (раньше) → B (позже), {data['chapters_apart']} глав между ними.\n\n"
                f"=== A\n{plain(data['a_html'])}\n\n=== B\n{plain(data['b_html'])}")
    if task == "compare":
        a, b = (data["b_html"], data["a_html"]) if swap else (data["a_html"], data["b_html"])
        return f"Какое событие важнее для всей книги?\n\n=== A\n{plain(a)}\n\n=== B\n{plain(b)}"
    if task == "event":
        return f"Событие из прогона:\n{plain(data['card'])}\n\nТекст:\n{plain(data['context'])}"
    if task == "quote":
        options = "\n".join(f"- {o['value']}" for o in data["options"])
        return (f"Кто говорит реплику, отмеченную ►?\n\n{plain(data['context'])}\n\n"
                f"Варианты (ответь одним из них дословно):\n{options}")
    raise ValueError(task)


# --- asking --------------------------------------------------------------------

def unswap(winner: str) -> str:
    return {"A": "B", "B": "A"}.get(winner, winner)


async def answer(client: Client, task: str, data: dict) -> dict:
    model = schema(task, data)
    system = SYSTEM.format(guide=guide(task))
    got = dump(await client.ask(model, system, prompt(task, data), kind="judge", max_tokens=8192))
    if task == "compare":
        back = dump(await client.ask(model, system, prompt(task, data, swap=True), kind="judge",
                                     max_tokens=8192))
        second = unswap(back["winner"])
        got["orders"] = [got["winner"], second]
        if got["winner"] != second:
            got["winner"] = "uncertain"
        got["why"] = f"{got['why']} | обратный порядок: {back['why']}"
    return got


def silver_dir(book: str) -> Path:
    return gold_dir(book) / "silver"


def done(file: Path) -> dict[str, dict]:
    if not file.exists():
        return {}
    rows = {}
    for line in file.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:  # cut short by a killed run; that task is asked again
            continue
        rows[r["gid"]] = r
    return rows


async def label(book: str, tasks: tuple[str, ...], jobs: int, limit: int | None) -> None:
    out = silver_dir(book)
    out.mkdir(parents=True, exist_ok=True)
    client = Client(jobs)
    name = await client.model()
    try:
        for task in tasks:
            file = out / f"{task}.jsonl"
            have = done(file)
            items = [t["data"] for t in read_json(gold_dir(book) / "packets" / f"{task}.json")]
            # Another model's answers (the run's own model, a test) are asked again.
            todo = [d for d in items if have.get(d["gid"], {}).get("model") != name][:limit]
            mine = sum(r.get("model") == name for r in have.values())
            print(f"{task}: {mine} answered by {name}, {len(todo)} to ask")
            failed = 0
            start = time.monotonic()

            async def one(d: dict) -> None:
                nonlocal failed
                try:
                    got = await answer(client, task, d)
                except Exception as e:  # one bad task must not stop the rest
                    failed += 1
                    print(f"  {d['gid']}: {str(e)[:200]}")
                    return
                row = {"gid": d["gid"], **{k: d.get(k) for k in KEEP[task]}, **got,
                       "model": name, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
                have[d["gid"]] = row
                with file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

            await asyncio.gather(*(one(d) for d in todo))
            # Sorted and without duplicates, once the task is done; write then
            # rename, so a kill here never empties the file.
            tmp = file.with_suffix(file.suffix + ".tmp")
            tmp.write_text("".join(json.dumps(have[g], ensure_ascii=False) + "\n" for g in sorted(have)),
                           encoding="utf-8")
            tmp.replace(file)
            print(f"{task}: {len(have)} in {file.relative_to(ROOT)}, {failed} failed, "
                  f"{time.monotonic() - start:.0f}s; {client.stats.line()}")
    finally:
        await client.close()


def run(book: str, tasks: str | None, jobs: int, limit: int | None) -> None:
    chosen = tuple(tasks.split(",")) if tasks else TASKS
    unknown = [t for t in chosen if t not in TASKS]
    if unknown:
        raise SystemExit(f"silver: no such task {unknown}; tasks: {', '.join(TASKS)}")
    asyncio.run(label(book, chosen, jobs, limit))


def load(book: str, task: str) -> list[dict]:
    return list(done(silver_dir(book) / f"{task}.jsonl").values())

