"""Stage 2: facts from each chunk, one model call per chunk, in parallel.

Writes work/<book>/extract/<chunk>.json. A chunk whose file exists and was
made from the same text is skipped, so a stopped run resumes where it was.
"""

import asyncio
import hashlib
import time

from .llm import Client, dump
from .schemas import ChunkFacts
from .store import read_json, work_dir, write_json

SYSTEM = """Ты литературный аналитик. Ты читаешь роман по фрагментам и извлекаешь из каждого факты для графа сюжета. Ответ — только JSON по заданной схеме, все значения на русском языке.

Правила.
1. Извлекай только то, что есть в ОСНОВНОМ ТЕКСТЕ. Блок КОНТЕКСТ (конец предыдущего фрагмента) нужен лишь чтобы понять, кто есть кто; события из него не бери.
2. characters: name — самое полное имя персонажа, какое известно из текста, в именительном падеже («Жон Арк», а не «Жона» или «Арку»). forms — все варианты, которыми персонаж назван во фрагменте, как в тексте: падежные формы, фамилия, прозвища, обращения («братец»). about — одно предложение: что мы узнаём о персонаже здесь. Безымянных статистов (стражник, продавец) не включай, если они ни на что не влияют; если влияют — дай описательное имя («капитан стражи Вейла»).
3. events: от 3 до 12 событий в порядке текста, n — номер с 1. title — до 8 слов. what — 1–2 предложения: кто что сделал и чем кончилось. who — значения name из characters. where и when — место и время, если названы, иначе пустая строка. kind — тип события; флешбэк или воспоминание — «воспоминание». importance: 3 — поворот сюжета (смерть, предательство, решение, меняющее судьбу героя, ключевая битва, важное откровение), 2 — заметное развитие, 1 — фон и быт. causes — номера более ранних событий этого же фрагмента, прямо приведших к этому. threads — 1–3 короткие метки сюжетных линий, к которым относится событие («учёба в Биконе», «конфликт с Кардином», «семья Арков»); одну и ту же линию называй одинаково.
4. places и groups — места и организации (семьи, команды, армии, королевства), важные для этого фрагмента, с одним предложением о каждом.
5. relations — только явные проявления или перемены в отношениях двух персонажей в этом фрагменте: kind — тип (семья, дружба, вражда, соперничество, наставничество, романтика, союз, подчинение), note — что именно произошло.
6. summary — 4–6 предложений о том, что произошло во фрагменте, без оценок."""


def text_hash(chunk: dict) -> str:
    return hashlib.sha1((chunk["context_before"] + chunk["text"]).encode()).hexdigest()[:16]


def prompt(book: dict, chunk: dict) -> str:
    head = f"Книга: «{book['title']}», автор {book['author']}."
    if book.get("annotation"):
        head += f"\nАннотация: {book['annotation']}"
    parts = f", часть {chunk['part']} из {chunk['parts']}" if chunk["parts"] > 1 else ""
    ctx = chunk["context_before"] or "(начало книги)"
    return (f"{head}\n{chunk['chapter_title']}{parts}.\n\n"
            f"КОНТЕКСТ:\n{ctx}\n\nОСНОВНОЙ ТЕКСТ:\n{chunk['text']}")


def select(chunks: list[dict], chapters: str | None) -> list[dict]:
    """chapters is "1-3,7" by chapter order number, or None for all."""
    if not chapters:
        return chunks
    wanted: set[int] = set()
    for part in chapters.split(","):
        a, _, b = part.partition("-")
        wanted.update(range(int(a), int(b or a) + 1))
    return [c for c in chunks if int(c["chapter"][2:]) in wanted]


async def run(book: str, chapters: str | None, concurrency: int) -> None:
    wd = work_dir(book)
    meta = read_json(wd / "chapters.json")
    out_dir = wd / "extract"
    out_dir.mkdir(exist_ok=True)
    todo = []
    for c in select(read_json(wd / "chunks.json"), chapters):
        path = out_dir / f"{c['id']}.json"
        if path.exists() and read_json(path)["hash"] == text_hash(c):
            continue
        todo.append(c)
    print(f"{len(todo)} chunks to extract, {concurrency} at a time")
    client = Client(concurrency)
    done = 0

    async def one(c: dict) -> None:
        nonlocal done
        t = time.monotonic()
        facts = await client.ask(ChunkFacts, SYSTEM, prompt(meta, c), max_tokens=6144)
        write_json(out_dir / f"{c['id']}.json",
                   {"chunk": c["id"], "hash": text_hash(c), "facts": dump(facts)})
        done += 1
        print(f"[{done}/{len(todo)}] {c['id']}: {len(facts.events)} events, "
              f"{len(facts.characters)} characters, {time.monotonic() - t:.0f}s")

    try:
        results = await asyncio.gather(*(one(c) for c in todo), return_exceptions=True)
    finally:
        await client.close()
    failed = [(c["id"], r) for c, r in zip(todo, results) if isinstance(r, BaseException)]
    for cid, err in failed:
        print(f"FAILED {cid}: {err!r}")
    print(client.stats.line())
    if failed:
        raise SystemExit(f"{len(failed)} chunks failed; run again to retry them")
