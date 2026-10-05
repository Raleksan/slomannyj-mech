"""Stage 4: storylines, and links between events across chunks and chapters.

1. The free storyline tags from extraction are merged into STORYLINES named
   storylines; every tag is then mapped to one of them (or to none), in
   batches. An event belongs to the storylines of its tags.
2. For each chapter, in parallel with step 1, the model sees that chapter's notable
   events and the notable events before it, and says which earlier event
   led to, continued, resolved or mirrored each one. Links inside one chunk
   come from extraction already.

Writes work/<book>/threads.json: storylines, events (with entity ids), edges.
"""

import asyncio
import collections
import time
from typing import Literal

from pydantic import BaseModel

from .llm import Client
from .progress import Progress
from .resolve import entity_id, key
from .store import read_json, work_dir, write_json

STORYLINES = "от 12 до 30"
TAG_BATCH = 150
PRIOR_LIMIT = 150


class Storyline(BaseModel):
    name: str
    description: str


class Storylines(BaseModel):
    storylines: list[Storyline]


class TagMap(BaseModel):
    tag: int
    storyline: int


class TagMaps(BaseModel):
    tags: list[TagMap]


class Link(BaseModel):
    src: str
    dst: str
    type: Literal["причина", "продолжение", "развязка", "параллель"]
    why: str


class Links(BaseModel):
    links: list[Link]


def load_events(book: str, entities: dict) -> list[dict]:
    chunks = read_json(work_dir(book) / "chunks.json")
    events = []
    missing = 0
    for c in chunks:
        path = work_dir(book) / "extract" / f"{c['id']}.json"
        if not path.exists():
            missing += 1
            continue
        for e in read_json(path)["facts"]["events"]:
            eid = f"{c['id']}-e{e['n']:02d}"
            who = [entity_id(entities, "characters", w) for w in e["who"]]
            events.append({
                "id": eid, "chunk": c["id"], "chapter": c["chapter"],
                "chapter_title": c["chapter_title"], "n": e["n"], "title": e["title"],
                "what": e["what"], "who": [w for w in dict.fromkeys(who) if w],
                "where": entity_id(entities, "places", e["where"]) if e["where"] else None,
                "where_text": e["where"], "when": e["when"], "kind": e["kind"],
                "importance": e["importance"], "tags": [key(t) for t in e["threads"]],
                "tag_text": e["threads"],
                "causes": [f"{c['id']}-e{n:02d}" for n in e["causes"] if 0 < n < e["n"]],
            })
    if missing:
        print(f"note: {missing} of {len(chunks)} chunks are not extracted yet; working on the rest")
    return events


STORY_SYSTEM = """Ты редактор, который составляет схему сюжета романа. Тебе дают метки сюжетных линий, которые расставлялись по фрагментам книги, с числом фрагментов, где встречается каждая. Объедини их в {n} сюжетных линий: главная линия, побочные линии, арки ключевых персонажей, линии отношений. name — короткое название (до 6 слов), description — 1–2 предложения, о чём линия. Ответ — только JSON по схеме."""

MAP_SYSTEM = """Тебе дают пронумерованные сюжетные линии романа и пронумерованные метки, которыми помечались события. Для каждой метки укажи номер линии, к которой она относится, или 0, если ни к одной. Ответ — только JSON по схеме, по одной записи на каждую метку."""

LINK_SYSTEM = """Ты строишь граф причин и следствий в романе. Тебе дают события текущей главы и важные события до неё, у каждого есть id. Для событий текущей главы найди связи с более ранними событиями (из прошлых глав или раньше в этой главе): src — id более раннего события, dst — id события текущей главы, type: «причина» (src прямо привело к dst), «продолжение» (dst продолжает ту же линию действий), «развязка» (dst завершает или разрешает src), «параллель» (dst перекликается с src, повторяет или противопоставляет). why — до 12 слов. Связывай только когда связь явная; не больше 3 связей на событие; у многих событий связей нет. Ответ — только JSON по схеме."""


def line(e: dict) -> str:
    return f"{e['id']} [{e['chapter_title']}, важность {e['importance']}] {e['title']}"


async def storylines(client: Client, events: list[dict], progress: Progress) -> tuple[list[dict], dict]:
    counts = collections.Counter()
    text: dict[str, str] = {}
    for e in events:
        chunk_tags = set(e["tags"])
        counts.update(chunk_tags)
        for k, t in zip(e["tags"], e["tag_text"]):
            text.setdefault(k, t)
    top = counts.most_common(400)
    listing = "\n".join(f"{text[k]} — {n}" for k, n in top)
    t = time.monotonic()
    answer = await client.ask(Storylines, STORY_SYSTEM.format(n=STORYLINES), listing,
                              think=True, max_tokens=24000, temperature=0.4)
    lines = [{"id": f"s{i:02d}", "name": s.name, "description": s.description}
             for i, s in enumerate(answer.storylines, 1)]
    progress.tick("storylines", time.monotonic() - t, f"{len(lines)} storylines", client.stats)
    numbered = "\n".join(f"{i}. {s['name']} — {s['description']}" for i, s in enumerate(lines, 1))
    tags = list(counts)

    async def batch(part: list[str]) -> dict[str, str]:
        t = time.monotonic()
        listing = "\n".join(f"{i}. {text[k]}" for i, k in enumerate(part, 1))
        answer = await client.ask(TagMaps, MAP_SYSTEM,
                                  f"Сюжетные линии:\n{numbered}\n\nМетки:\n{listing}", max_tokens=6000)
        out = {}
        for m in answer.tags:
            if 1 <= m.tag <= len(part) and 1 <= m.storyline <= len(lines):
                out[part[m.tag - 1]] = lines[m.storyline - 1]["id"]
        progress.tick(f"tags {text[part[0]]}…", time.monotonic() - t,
                      f"{len(out)}/{len(part)} tags mapped", client.stats)
        return out

    mapping: dict[str, str] = {}
    for part in await asyncio.gather(*(batch(tags[i:i + TAG_BATCH])
                                       for i in range(0, len(tags), TAG_BATCH))):
        mapping.update(part)
    return lines, mapping


async def links(client: Client, events: list[dict], progress: Progress) -> list[dict]:
    chapters = list(dict.fromkeys(e["chapter"] for e in events))
    by_id = {e["id"]: e for e in events}
    order = {e["id"]: i for i, e in enumerate(events)}

    async def one(ch: str) -> list[dict]:
        t = time.monotonic()
        here = [e for e in events if e["chapter"] == ch and e["importance"] >= 2]
        if not here:
            progress.tick(ch, 0, "no notable events", client.stats)
            return []
        start = order[here[0]["id"]]
        earlier = [e for e in events[:start] if e["importance"] == 3]
        recent_chapters = chapters[max(0, chapters.index(ch) - 3):chapters.index(ch)]
        earlier += [e for e in events[:start] if e["importance"] == 2 and e["chapter"] in recent_chapters]
        earlier = sorted(earlier, key=lambda e: order[e["id"]])[-PRIOR_LIMIT:]
        current = "\n".join(f"{line(e)}: {e['what']}" for e in here)
        prior = "\n".join(line(e) for e in earlier) or "(начало книги)"
        answer = await client.ask(Links, LINK_SYSTEM,
                                  f"Важные события до этой главы:\n{prior}\n\nСобытия текущей главы:\n{current}",
                                  max_tokens=6000)
        ok = [lk.model_dump() for lk in answer.links
              if lk.src in by_id and lk.dst in by_id and by_id[lk.dst]["chapter"] == ch
              and order[lk.src] < order[lk.dst]]
        progress.tick(ch, time.monotonic() - t, f"{len(here)} events, {len(ok)} links", client.stats)
        return ok

    out = []
    for part in await asyncio.gather(*(one(ch) for ch in chapters)):
        out.extend(part)
    return out


async def run(book: str, concurrency: int) -> None:
    wd = work_dir(book)
    entities = read_json(wd / "entities.json")
    events = load_events(book, entities)
    chapters = len({e["chapter"] for e in events})
    n_tags = len({t for e in events for t in e["tags"]})
    progress = Progress(book, "thread", 1 + -(-n_tags // TAG_BATCH) + chapters)
    client = Client(concurrency)
    try:
        # The storyline call thinks for a long time; the links need none of
        # its output, so they run alongside it.
        (lines, mapping), linked = await asyncio.gather(
            storylines(client, events, progress), links(client, events, progress))
        for e in events:
            e["storylines"] = list(dict.fromkeys(mapping[t] for t in e["tags"] if t in mapping))
        edges = [{"src": c, "dst": e["id"], "type": "причина", "why": ""}
                 for e in events for c in e["causes"]] + linked
    finally:
        await client.close()
        progress.finish()
    write_json(wd / "threads.json", {"storylines": lines, "events": events, "edges": edges})
    loose = sum(1 for e in events if not e["storylines"])
    print(f"{len(lines)} storylines, {len(events)} events ({loose} without a storyline), "
          f"{len(edges)} edges")
    print(client.stats.line())
