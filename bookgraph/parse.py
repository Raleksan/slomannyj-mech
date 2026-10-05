"""Stage 0: read an FB2 (or .fb2.zip) into chapters of scenes of paragraphs.

A chapter is a leaf <section> of the main <body>; nested sections get their
parents' titles joined in front. A paragraph of only asterisks ("***",
"* * *") ends a scene. Notes bodies and embedded images are dropped.
"""

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "{http://www.gribuser.ru/xml/fictionbook/2.0}"
SCENE_BREAK = re.compile(r"^[\s*⁂]+$")


def read_fb2(path: Path) -> bytes:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist() if n.endswith(".fb2")]
            if len(names) != 1:
                raise ValueError(f"{path}: expected one .fb2 inside, found {names}")
            return zf.read(names[0])
    return path.read_bytes()


def book_id(path: Path) -> str:
    # slomannyj_mech-b302190.fb2.zip -> slomannyj_mech
    name = path.name
    for suffix in (".zip", ".fb2"):
        name = name.removesuffix(suffix)
    return re.sub(r"-b\d+$", "", name)


def text_of(el) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


def paragraphs(el):
    """Yields the text paragraphs directly under a section, in order.

    Poems, citations and epigraphs are flattened into their lines.
    """
    for child in el:
        tag = child.tag.removeprefix(NS)
        if tag in ("p", "subtitle", "v", "text-author"):
            yield text_of(child)
        elif tag in ("poem", "stanza", "cite", "epigraph"):
            yield from paragraphs(child)
        elif tag == "table":
            for row in child:
                yield " | ".join(text_of(cell) for cell in row)


def chapters(section, path: list[str]):
    title_el = section.find(NS + "title")
    title = text_of(title_el) if title_el is not None else ""
    here = path + [title] if title else path
    subs = section.findall(NS + "section")
    if not subs:
        yield " / ".join(here), list(paragraphs(section))
        return
    # Text beside the subsections (paragraphs() skips <section> and <title>)
    # becomes its own chapter.
    intro = list(paragraphs(section))
    if any(intro):
        yield " / ".join(here), intro
    for sub in subs:
        yield from chapters(sub, here)


def scenes(paras: list[str]) -> list[list[str]]:
    out: list[list[str]] = [[]]
    for p in paras:
        if not p:
            continue
        if SCENE_BREAK.match(p):
            if out[-1]:
                out.append([])
        else:
            out[-1].append(p)
    return [s for s in out if s]


def annotation(info) -> str:
    """The blurb, without notices set wholly in bold (age or legal warnings)."""
    el = info.find(NS + "annotation") if info is not None else None
    if el is None:
        return ""
    keep = []
    for p in el:
        text = text_of(p)
        bold = "".join(text_of(b) for b in p if b.tag == NS + "strong")
        if text and not SCENE_BREAK.match(text) and bold != text:
            keep.append(text)
    return " ".join(keep)


def parse(path: Path) -> dict:
    root = ET.fromstring(read_fb2(path))
    info = root.find(f"{NS}description/{NS}title-info")
    author = info.find(NS + "author") if info is not None else None
    bodies = [b for b in root.findall(NS + "body") if b.get("name") not in ("notes", "comments")]
    if not bodies:
        raise ValueError(f"{path}: no main <body>")
    out = []
    for section in bodies[0].findall(NS + "section"):
        for title, paras in chapters(section, []):
            sc = scenes(paras)
            if not sc:
                continue
            n = len(out) + 1
            out.append({
                "n": n,
                "id": f"ch{n:03d}",
                "title": title or f"Часть {n}",
                "scenes": sc,
            })
    def field(tag: str) -> str:
        el = info.find(NS + tag) if info is not None else None
        return text_of(el) if el is not None else ""

    return {
        "book": book_id(path),
        "title": field("book-title") or path.stem,
        "author": " ".join(filter(None, (
            text_of(e) for e in author
            if e.tag.removeprefix(NS) in ("first-name", "middle-name", "last-name", "nickname")
        ))) if author is not None else "",
        "lang": field("lang"),
        "annotation": annotation(info),
        "chapters": out,
    }
