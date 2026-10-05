"""bookgraph STAGE ...

  bookgraph parse books/NAME.fb2.zip   chapters into work/NAME/chapters.json
  bookgraph chunk NAME                 chunks into work/NAME/chunks.json
  bookgraph calibrate NAME             measure chars/token with the model, rechunk
  bookgraph extract NAME [-c 1-3] [-j 8]
                                       facts per chunk into work/NAME/extract/
  bookgraph resolve NAME [-j 8]        one entity per person/place/group: entities.json
  bookgraph thread NAME [-j 8]         storylines and cross-chapter links: threads.json
  bookgraph summarize NAME [-j 8]      note texts into work/NAME/notes/
  bookgraph render NAME                vault and graph.html into out/NAME/
  bookgraph stats NAME                 chapter and chunk sizes
  bookgraph progress NAME [-w SECONDS] progress of the running stage
"""

import argparse
import asyncio
import statistics
import sys
from pathlib import Path

from . import chunk, parse
from .store import read_json, work_dir, write_json


def cmd_parse(args) -> None:
    data = parse.parse(Path(args.path))
    write_json(work_dir(data["book"]) / "chapters.json", data)
    paras = sum(len(s) for ch in data["chapters"] for s in ch["scenes"])
    print(f"{data['book']}: «{data['title']}», {data['author']}, lang={data['lang']}")
    print(f"{len(data['chapters'])} chapters, {paras} paragraphs")


def cmd_chunk(args) -> None:
    chunks = chunk.chunk(args.book)
    print(f"{len(chunks)} chunks, about {chunk.TARGET_TOKENS} tokens each "
          f"at {chunk.chars_per_token(args.book)} chars/token")


def cmd_calibrate(args) -> None:
    from .llm import Client

    chunks = read_json(work_dir(args.book) / "chunks.json")
    sample = chunks[:: max(1, len(chunks) // 12)]

    async def measure() -> int:
        client = Client(4)
        try:
            return sum(await asyncio.gather(*(client.tokenize(c["text"]) for c in sample)))
        finally:
            await client.close()

    tokens = asyncio.run(measure())
    chars = sum(len(c["text"]) for c in sample)
    ratio = round(chars / tokens, 3)
    write_json(work_dir(args.book) / "calibration.json",
               {"chars_per_token": ratio, "sample_chunks": len(sample), "tokens": tokens})
    print(f"{ratio} chars/token over {len(sample)} chunks")
    if any((work_dir(args.book) / "extract").glob("*.json")):
        print("extract/ already has results; rechunking makes chunks with new text rerun")
    cmd_chunk(args)


def cmd_extract(args) -> None:
    from . import extract

    asyncio.run(extract.run(args.book, args.chapters, args.jobs))


def cmd_progress(args) -> None:
    import os
    import time

    from .progress import show

    base = os.environ.get("BOOKGRAPH_LLM", "http://127.0.0.1:8080").rstrip("/")
    while True:
        text = show(args.book, base)
        if not args.watch:
            print(text)
            return
        print("\033[2J\033[H" + text + f"\n\n(refresh every {args.watch}s, Ctrl-C to quit)", flush=True)
        time.sleep(args.watch)


def cmd_resolve(args) -> None:
    from . import resolve

    asyncio.run(resolve.run(args.book, args.jobs))


def cmd_thread(args) -> None:
    from . import thread

    asyncio.run(thread.run(args.book, args.jobs))


def cmd_summarize(args) -> None:
    from . import summarize

    asyncio.run(summarize.run(args.book, args.jobs))


def cmd_render(args) -> None:
    from . import graph, vault

    vault.run(args.book)
    graph.run(args.book)


def cmd_stats(args) -> None:
    wd = work_dir(args.book)
    data = read_json(wd / "chapters.json")
    ratio = chunk.chars_per_token(args.book)
    sizes = [sum(len(p) for s in ch["scenes"] for p in s) for ch in data["chapters"]]
    total = sum(sizes)
    print(f"text: {total} chars, about {round(total / ratio)} tokens at {ratio} chars/token")
    print(f"chapters: {len(sizes)}, median {round(statistics.median(sizes) / ratio)} tokens, "
          f"max {round(max(sizes) / ratio)} tokens")
    if (wd / "chunks.json").exists():
        tokens = [c["est_tokens"] for c in read_json(wd / "chunks.json")]
        print(f"chunks: {len(tokens)}, min {min(tokens)}, median {round(statistics.median(tokens))}, "
              f"max {max(tokens)} tokens")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="bookgraph", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="stage", required=True)
    p = sub.add_parser("parse")
    p.add_argument("path")
    p.set_defaults(func=cmd_parse)
    for name, func in (("chunk", cmd_chunk), ("calibrate", cmd_calibrate), ("stats", cmd_stats), ("render", cmd_render)):
        p = sub.add_parser(name)
        p.add_argument("book")
        p.set_defaults(func=func)
    p = sub.add_parser("extract")
    p.add_argument("book")
    p.add_argument("-c", "--chapters", help="chapters by reading order, as 1-3,7 (not by title); default all")
    p.add_argument("-j", "--jobs", type=int, default=8,
                   help="requests at once; match llama-server --parallel")
    p.set_defaults(func=cmd_extract)
    p = sub.add_parser("resolve")
    p.add_argument("book")
    p.add_argument("-j", "--jobs", type=int, default=8)
    p.set_defaults(func=cmd_resolve)
    p = sub.add_parser("thread")
    p.add_argument("book")
    p.add_argument("-j", "--jobs", type=int, default=8)
    p.set_defaults(func=cmd_thread)
    p = sub.add_parser("summarize")
    p.add_argument("book")
    p.add_argument("-j", "--jobs", type=int, default=8)
    p.set_defaults(func=cmd_summarize)
    p = sub.add_parser("progress")
    p.add_argument("book")
    p.add_argument("-w", "--watch", type=int, default=0, metavar="SECONDS",
                   help="redraw every SECONDS until Ctrl-C")
    p.set_defaults(func=cmd_progress)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
