"""Stage 5: the text of the notes, one model call per note, in parallel.

Chapters, main characters, storylines, places and groups each get a note
in work/<book>/notes/<kind>/<id>.json; a note already there is kept, so a
stopped run resumes. The book overview comes last, from the chapters'
one-line summaries and the storylines.
"""

import asyncio
import collections
import time
from pathlib import Path

from pydantic import BaseModel, Field

from .llm import Client, dump
from .progress import Progress
from .resolve import entity_id
from .store import read_json, work_dir, write_json

MIN_MENTIONS = {"characters": 3, "places": 3, "groups": 3}
MAX_NOTES = {"characters": 120, "places": 60, "groups": 60}
MAX_EVENTS = 160


class ChapterNote(BaseModel):
    oneline: str
    summary: str
    key_points: list[str] = Field(max_length=8)


class ArcStep(BaseModel):
    chapter: str
    change: str


class Bond(BaseModel):
    other: str
    description: str


class CharacterNote(BaseModel):
    summary: str
    traits: list[str] = Field(max_length=8)
    arc: list[ArcStep] = Field(max_length=15)
    relationships: list[Bond] = Field(max_length=12)


class Phase(BaseModel):
    title: str
    chapters: str
    text: str


class StorylineNote(BaseModel):
    summary: str
    phases: list[Phase] = Field(max_length=10)
    outcome: str


class EntityNote(BaseModel):
    summary: str


class Overview(BaseModel):
    summary: str
    themes: list[str] = Field(max_length=8)
    structure: str


STYLE = "Пиши по-русски, ясно и без оценок, только то, что следует из данных. Ответ — только JSON по схеме."

CHAPTER = f"""Ты составляешь конспект главы романа по кратким пересказам её частей и списку событий. oneline — одно предложение о главном в главе. summary — связный пересказ в 5–8 предложениях. key_points — 3–8 ключевых моментов, по одной короткой фразе. {STYLE}"""

CHARACTER = f"""Ты составляешь карточку персонажа романа по его событиям в порядке книги и отношениям. summary — 4–6 предложений: кто он и какую роль играет. traits — черты характера и способности, коротко. arc — как персонаж меняется: шаги с главой («Глава 12») и сутью перемены. relationships — главные связи: other — имя другого персонажа, как оно дано в данных, description — каковы отношения и как меняются. {STYLE}"""

STORYLINE = f"""Ты описываешь одну сюжетную линию романа по её событиям в порядке книги. summary — 3–5 предложений о линии целиком. phases — этапы развития: название, главы (например «Главы 3–7»), 1–3 предложения. outcome — чем линия кончается к концу книги или в каком состоянии остаётся. {STYLE}"""

ENTITY = f"""Ты пишешь справку для указателя к роману по описаниям из разных глав и событиям, где фигурирует этот объект. summary — 2–4 предложения: что это и какую роль играет в сюжете. {STYLE}"""

OVERVIEW = f"""Ты пишешь обзор романа по однострочным пересказам глав и списку сюжетных линий. summary — пересказ всей книги в 8–12 предложениях. themes — главные темы. structure — 2–4 предложения о том, как устроен сюжет: части, переломные моменты. {STYLE}"""


def event_line(e: dict) -> str:
    return f"[{e['chapter_title']}] {e['title']}: {e['what']}"


def pick(events: list[dict]) -> list[dict]:
    """At most MAX_EVENTS, dropping minor ones first, in book order."""
    if len(events) <= MAX_EVENTS:
        return events
    for floor in (2, 3):
        kept = [e for e in events if e["importance"] >= floor]
        if len(kept) <= MAX_EVENTS:
            return kept
    step = len(kept) / MAX_EVENTS
    return [kept[int(i * step)] for i in range(MAX_EVENTS)]


async def run(book: str, concurrency: int) -> None:
    wd = work_dir(book)
    meta = read_json(wd / "chapters.json")
    entities = read_json(wd / "entities.json")
    threads = read_json(wd / "threads.json")
    events = threads["events"]
    chunks = [c for c in read_json(wd / "chunks.json") if (wd / "extract" / f"{c['id']}.json").exists()]
    extracts = {c["id"]: read_json(wd / "extract" / f"{c['id']}.json")["facts"] for c in chunks}
    names = {e["id"]: e["name"] for kind in ("characters", "places", "groups") for e in entities[kind]}

    jobs: list[tuple[Path, type[BaseModel], str, str]] = []

    def add(kind: str, item: str, model: type[BaseModel], system: str, user: str) -> None:
        jobs.append((wd / "notes" / kind / f"{item}.json", model, system, user))

    chapters = [ch for ch in meta["chapters"] if any(c["chapter"] == ch["id"] for c in chunks)]
    for ch in chapters:
        parts = [c for c in chunks if c["chapter"] == ch["id"]]
        summaries = "\n".join(f"Часть {c['part']}: {extracts[c['id']]['summary']}" for c in parts)
        evs = "\n".join(event_line(e) for e in events if e["chapter"] == ch["id"] and e["importance"] >= 2)
        add("chapters", ch["id"], ChapterNote, CHAPTER,
            f"{ch['title']}.\n\nПересказы частей:\n{summaries}\n\nВажные события:\n{evs}")

    relations = collections.defaultdict(list)
    for c in chunks:
        for r in extracts[c["id"]]["relations"]:
            a, b = (entity_id(entities, "characters", x) for x in (r["a"], r["b"]))
            if a and b and a != b:
                line = f"[{c['chapter_title']}] {names[a]} — {names[b]}: {r['kind']}, {r['note']}"
                relations[a].append(line)
                relations[b].append(line)
    for kind in ("characters", "places", "groups"):
        chosen = [e for e in entities[kind] if e["mentions"] >= MIN_MENTIONS[kind]][:MAX_NOTES[kind]]
        for ent in chosen:
            if kind == "characters":
                evs = pick([e for e in events if ent["id"] in e["who"]])
            elif kind == "places":
                evs = pick([e for e in events if e["where"] == ent["id"]])
            else:
                evs = []
            if not evs:
                # Groups are not tied to events; the chunks they appear in stand in.
                evs = [{"chapter_title": next(c["chapter_title"] for c in chunks if c["id"] == cid),
                        "title": "фрагмент", "what": extracts[cid]["summary"]}
                       for cid in ent["chunks"][:20]]
            about = "\n".join(f"- {a}" for a in ent["about"])
            body = (f"{ent['name']} (также: {', '.join(ent['aliases'][:10]) or '—'}).\n\n"
                    f"Описания:\n{about}\n\nСобытия:\n" + ("\n".join(event_line(e) for e in evs) or "—"))
            if kind == "characters":
                body += "\n\nОтношения:\n" + ("\n".join(relations[ent["id"]][-60:]) or "—")
                add(kind, ent["id"], CharacterNote, CHARACTER, body)
            else:
                add(kind, ent["id"], EntityNote, ENTITY, body)
    for s in threads["storylines"]:
        evs = pick([e for e in events if s["id"] in e["storylines"]])
        add("storylines", s["id"], StorylineNote, STORYLINE,
            f"Линия «{s['name']}»: {s['description']}\n\nСобытия:\n"
            + ("\n".join(event_line(e) for e in evs) or "—"))

    todo = [j for j in jobs if not j[0].exists()]
    progress = Progress(book, "summarize", len(todo) + 1, skipped=len(jobs) - len(todo))
    client = Client(concurrency)

    async def one(job) -> None:
        path, model, system, user = job
        t = time.monotonic()
        note = await client.ask(model, system, user, max_tokens=4096)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json(path, dump(note))
        progress.tick(f"{path.parent.name}/{path.stem}", time.monotonic() - t,
                      names.get(path.stem, path.stem), client.stats)

    try:
        results = await asyncio.gather(*(one(j) for j in todo), return_exceptions=True)
        failed = [(j[0].stem, r) for j, r in zip(todo, results) if isinstance(r, BaseException)]
        for item, err in failed:
            print(f"FAILED {item}: {err!r}")
        if failed:
            raise SystemExit(f"{len(failed)} notes failed; run again to retry them")
        lines = "\n".join(
            f"{ch['title']}: {read_json(wd / 'notes' / 'chapters' / (ch['id'] + '.json'))['oneline']}"
            for ch in chapters)
        story = "\n".join(f"- {s['name']}: {s['description']}" for s in threads["storylines"])
        t = time.monotonic()
        overview = await client.ask(Overview, OVERVIEW,
                                    f"«{meta['title']}», {meta['author']}.\n\nГлавы:\n{lines}\n\n"
                                    f"Сюжетные линии:\n{story}", think=True, max_tokens=20000)
        write_json(wd / "notes" / "overview.json", dump(overview))
        progress.tick("overview", time.monotonic() - t, "book overview", client.stats)
    finally:
        await client.close()
        progress.finish()
    print(client.stats.line())
