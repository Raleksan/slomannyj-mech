"""Stage 1: cut chapters into chunks of about TARGET_TOKENS for extraction.

Each chapter is cut into chunks of near equal size, at scene breaks where
one is close enough, else between paragraphs. A chunk never spans two
chapters. Each chunk also carries the end of the text before it, so the
model knows who "he" is in the first lines; extraction marks that part as
context only.

Token counts are estimates from a characters-per-token ratio until the
calibrate stage measures the real ratio with the model's tokenizer.
"""

from .store import read_json, work_dir, write_json

TARGET_TOKENS = 6000
# A cut may move this share of the chunk size to land on a scene break.
SNAP_SHARE = 0.2
CONTEXT_CHARS = 800
# Russian prose on Qwen's tokenizer, before calibration.
DEFAULT_CHARS_PER_TOKEN = 3.6


def chars_per_token(book: str) -> float:
    path = work_dir(book) / "calibration.json"
    if path.exists():
        return read_json(path)["chars_per_token"]
    return DEFAULT_CHARS_PER_TOKEN


def chunk_chapter(scenes: list[list[str]], limit: int) -> list[str]:
    """Cuts a chapter into ceil(size / limit) chunks of near equal size.

    Each cut lands on the scene break nearest its ideal place, if one lies
    within SNAP_SHARE of a chunk's size, else on the nearest paragraph end.
    """
    paras = [(p, i > 0 and j == 0) for i, s in enumerate(scenes) for j, p in enumerate(s)]
    offsets = [0]
    for p, _ in paras:
        offsets.append(offsets[-1] + len(p) + 2)
    total = offsets[-1]
    n = max(1, -(-total // limit))
    step = total / n
    cuts = [0]
    for k in range(1, n):
        ideal = k * step
        options = range(cuts[-1] + 1, len(paras))
        breaks = [b for b in options if paras[b][1] and abs(offsets[b] - ideal) <= SNAP_SHARE * step]
        pool = breaks or list(options)
        if not pool:
            break
        cuts.append(min(pool, key=lambda b: abs(offsets[b] - ideal)))
    cuts.append(len(paras))
    out = []
    for a, b in zip(cuts, cuts[1:]):
        text = ""
        for k in range(a, b):
            p, scene_start = paras[k]
            if k > a:
                text += "\n\n***\n\n" if scene_start else "\n\n"
            text += p
        out.append(text)
    return out


def chunk(book: str) -> list[dict]:
    data = read_json(work_dir(book) / "chapters.json")
    ratio = chars_per_token(book)
    limit = int(TARGET_TOKENS * ratio)
    out = []
    before = ""
    for ch in data["chapters"]:
        for i, text in enumerate(chunk_chapter(ch["scenes"], limit), 1):
            out.append({
                "id": f"{ch['id']}-{i:02d}",
                "chapter": ch["id"],
                "chapter_title": ch["title"],
                "part": i,
                "context_before": before[-CONTEXT_CHARS:],
                "text": text,
                "chars": len(text),
                "est_tokens": round(len(text) / ratio),
            })
            before = text
    for c in out:
        c["parts"] = sum(1 for o in out if o["chapter"] == c["chapter"])
    write_json(work_dir(book) / "chunks.json", out)
    return out
