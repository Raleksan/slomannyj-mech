"""The gold set: hand-checked answers that bookgraph eval measures a run by.

  bookgraph gold pack NAME     Label Studio tasks from the current run,
                               gold/NAME/packets/<task>.json (+ -repeat.json)
  bookgraph gold import NAME FILE [--repeat]
                               a Label Studio JSON export into
                               gold/NAME/answers/<task>.jsonl

Packets are drawn from the run's own output with a fixed seed, so packing
again gives the same tasks. Each task has a stable "gid", which is what
answers, scores and the repeat pass refer to. Paragraphs are cited as
"ch007.p0142": the chapter id and the paragraph's place in the chapter,
counting from 1 over all its scenes. Stage 1 (M2) keeps the same ids.

docs/gold.md is how to annotate; annotate/configs/ holds one labeling
config per task.
"""

import html
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

from .store import ROOT, read_json, work_dir, write_json

SEED = 20261006
TASKS = ("alias", "place", "link", "compare", "top", "event", "quote")
REPEAT_SHARE = 0.15
WINDOW = 6
SIZES = {"alias": 200, "place": 100, "link": 100, "compare": 300, "event": 100, "quote": 150}
TOP_POOL = 100


def gold_dir(book: str) -> Path:
    return ROOT / "gold" / book


# --- the book's text, by paragraph ---------------------------------------------

class Text:
    """Paragraphs with stable ids, which chunk each lies in, and lookups."""

    def __init__(self, book: str) -> None:
        wd = work_dir(book)
        self.paras: list[dict] = []
        self.by_chunk: dict[str, list[int]] = {}
        chunks = read_json(wd / "chunks.json")
        for ch in read_json(wd / "chapters.json")["chapters"]:
            start = len(self.paras)
            for n, p in enumerate((p for s in ch["scenes"] for p in s), 1):
                self.paras.append({"id": f"{ch['id']}.p{n:04d}", "chapter": ch["id"],
                                   "title": ch["title"], "text": p})
            at = start
            for c in chunks:
                if c["chapter"] == ch["id"]:
                    n = sum(1 for p in c["text"].split("\n\n") if p != "***")
                    self.by_chunk[c["id"]] = list(range(at, at + n))
                    at += n
        self.chapters = list(dict.fromkeys(p["chapter"] for p in self.paras))
        self._tokens: list[set[str]] | None = None

    def tenth(self, chapter: str) -> int:
        return min(9, 10 * self.chapters.index(chapter) // len(self.chapters))

    def tokens(self, i: int) -> set[str]:
        if self._tokens is None:
            self._tokens = [stems(p["text"]) for p in self.paras]
        return self._tokens[i]

    def best(self, chunk: str, text: str) -> int:
        """The paragraph of a chunk that shares the most words with a text."""
        want = stems(text)
        pool = self.by_chunk.get(chunk) or [0]
        return max(pool, key=lambda i: (len(want & self.tokens(i)), -i))

    def window(self, i: int, before: int = WINDOW, after: int = WINDOW,
               mark: int | None = None) -> str:
        ch = self.paras[i]["chapter"]
        out = []
        for j in range(max(0, i - before), min(len(self.paras), i + after + 1)):
            p = self.paras[j]
            if p["chapter"] != ch:
                continue
            style = ' style="background:#fff3c4"' if j == mark else ""
            out.append(f'<p{style}><b>{p["id"]}</b> {html.escape(p["text"])}</p>')
        return f'<div><i>{html.escape(self.paras[i]["title"])}</i>{"".join(out)}</div>'

    def _grep(self, pattern: str) -> list[int]:
        pat = re.compile(pattern, re.IGNORECASE)
        return [i for i, p in enumerate(self.paras) if pat.search(p["text"])]

    def find(self, form: str, limit: int = 2, rng: random.Random | None = None) -> list[int]:
        """Paragraphs where a name form appears as written, spread over the book."""
        hits = self._grep(rf"(?<!\w){re.escape(form)}")
        if not hits:
            # Inflected ("Озпина") or labelled ("Жон (мальчик)"): the stem of
            # the longest word.
            words = re.findall(r"\w{4,}", re.sub(r"\(.*?\)", "", form))
            if words:
                w = max(words, key=len)
                hits = self._grep(rf"(?<!\w){re.escape(w[:max(4, len(w) - 2)])}")
        if len(hits) <= limit:
            return hits
        step = len(hits) / limit
        return [hits[int(k * step)] for k in range(limit)]


def stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"\w+", text.lower().replace("ё", "е")) if len(w) > 3}


def snippet(text: Text, i: int, around: int = 1) -> str:
    return text.window(i, around, around, mark=i)


# --- packets -------------------------------------------------------------------

def card(e: dict, names: dict[str, str]) -> str:
    who = ", ".join(names.get(w, w) for w in e["who"])
    where = names.get(e["where"], "") if e["where"] else ""
    return (f'<div><b>{html.escape(e["title"])}</b> — {html.escape(e["chapter_title"])}<br>'
            f'{html.escape(e["what"])}<br><small>кто: {html.escape(who)}; '
            f'где: {html.escape(e.get("where_text") or "")}'
            f'{" → " + html.escape(where) if where else ""}</small></div>')


def spread(items: list, n: int, key, rng: random.Random) -> list:
    """n items, as evenly as the items allow over the values of key (tenths)."""
    by: dict = defaultdict(list)
    for it in items:
        by[key(it)].append(it)
    for v in by.values():
        rng.shuffle(v)
    out = []
    while len(out) < n and any(by.values()):
        for k in sorted(by):
            if by[k] and len(out) < n:
                out.append(by[k].pop())
    return out


class Run:
    def __init__(self, book: str) -> None:
        wd = work_dir(book)
        self.text = Text(book)
        self.entities = read_json(wd / "entities.json")
        threads = read_json(wd / "threads.json")
        self.events = threads["events"]
        self.edges = threads["edges"]
        self.by_id = {e["id"]: e for e in self.events}
        self.names = {x["id"]: x["name"] for k in ("characters", "places", "groups")
                      for x in self.entities[k]}
        self.order = {e["id"]: i for i, e in enumerate(self.events)}
        self.extract = {p.stem: read_json(p)["facts"] for p in sorted((wd / "extract").glob("*.json"))}


def pack_alias(run: Run, rng: random.Random) -> list[dict]:
    text = run.text
    tasks = []
    seen = set()

    def add(kind: str, a: str, b: str, stratum: str, about: dict) -> None:
        pair = tuple(sorted((a, b)))
        if a == b or (kind, pair) in seen:
            return
        seen.add((kind, pair))
        sides = []
        for form in (a, b):
            hits = text.find(form, 2)
            body = "".join(snippet(text, i) for i in hits) or "<i>(не найдено в тексте дословно)</i>"
            sides.append(f'<h3>{html.escape(form)}</h3><p><small>{html.escape(about.get(form, ""))}'
                         f'</small></p>{body}')
        tasks.append({"kind": kind, "a": a, "b": b, "stratum": stratum,
                      "a_html": sides[0], "b_html": sides[1]})

    chars = sorted(run.entities["characters"], key=lambda x: -x["mentions"])
    main = chars[:30]
    about = {}
    for k in ("characters", "places", "groups"):
        for x in run.entities[k]:
            if x.get("about"):
                about.setdefault(x["name"], x["about"][0])
    # Merged by the run: are they really one? Weighted to main characters,
    # where a false merge does the most damage.
    inside = [(x["name"], f) for x in chars[:60] for f in x["aliases"] if f != x["name"]]
    rng.shuffle(inside)
    for a, b in inside[:70]:
        add("characters", a, b, "merged", about)
    # Kept apart though they share a name word: relatives or missed merges.
    by_word = defaultdict(list)
    for x in chars:
        for w in set(re.findall(r"\w{3,}", x["name"])):
            by_word[w].append(x["name"])
    shared = [(a, b) for v in by_word.values() if 1 < len(v) < 15 for a in v for b in v if a < b]
    rng.shuffle(shared)
    for a, b in shared[:50]:
        add("characters", a, b, "shared_word", about)
    # Seen once, next to a main character in the same chunk: an epithet or a stranger?
    main_chunks = {x["name"]: set(x["chunks"]) for x in main}
    singles = [x for x in chars if len(x["chunks"]) == 1]
    rng.shuffle(singles)
    n = 0
    for x in singles:
        near = [m for m, cs in main_chunks.items() if x["chunks"][0] in cs]
        if near and n < 50:
            add("characters", x["name"], rng.choice(near), "singleton", about)
            n += 1
    # Easy negatives, so precision is not measured on hard cases only.
    for _ in range(10):
        a, b = rng.sample(main, 2)
        add("characters", a["name"], b["name"], "easy", about)
    for kind in ("places", "groups"):
        items = run.entities[kind]
        words = defaultdict(list)
        for x in items:
            for w in set(re.findall(r"\w{4,}", x["name"])):
                words[w].append(x["name"])
        pairs = [(a, b) for v in words.values() if 1 < len(v) < 10 for a in v for b in v if a < b]
        pairs += [(x["name"], f) for x in items for f in x["aliases"] if f != x["name"]]
        rng.shuffle(pairs)
        for a, b in pairs[:10]:
            add(kind, a, b, "shared_word", about)
    return tasks[:SIZES["alias"]]


def pack_place(run: Run, rng: random.Random) -> list[dict]:
    places = run.entities["places"]
    placed = [e for e in run.events if e.get("where_text")]
    unresolved = spread([e for e in placed if e["where"] is None], 60,
                        lambda e: run.text.tenth(e["chapter"]), rng)
    resolved = spread([e for e in placed if e["where"]], 40,
                      lambda e: run.text.tenth(e["chapter"]), rng)
    in_chapter = defaultdict(Counter)
    for e in run.events:
        if e["where"]:
            in_chapter[e["chapter"]][e["where"]] += 1
    tasks = []
    for e in unresolved + resolved:
        want = stems(e["where_text"])
        scored = sorted(places, key=lambda p: -len(want & stems(" ".join([p["name"], *p["aliases"]]))))
        options = [p["id"] for p in scored[:6] if want & stems(p["name"] + " " + " ".join(p["aliases"]))]
        options += [pid for pid, _ in in_chapter[e["chapter"]].most_common(4)]
        if e["where"]:
            options.insert(0, e["where"])
        options = list(dict.fromkeys(options))[:8]
        rng.shuffle(options)
        i = run.text.best(e["chunk"], e["what"] + " " + e["where_text"])
        tasks.append({"event": e["id"], "where_text": e["where_text"], "run": e["where"],
                      "card": card(e, run.names), "context": run.text.window(i, 3, 3, mark=i),
                      "options": [{"value": f"{pid} {run.names[pid]}"} for pid in options]
                      + [{"value": "none: no such place in the list"}]})
    return tasks


def pack_link(run: Run, rng: random.Random) -> list[dict]:
    text = run.text
    far = []
    for x in run.edges:
        a, b = run.by_id.get(x["src"]), run.by_id.get(x["dst"])
        if a and b and a["chapter"] != b["chapter"]:
            far.append((a, b, x["type"]))
    chosen = spread(far, 50, lambda t: min(3, abs(text.chapters.index(t[1]["chapter"])
                                                   - text.chapters.index(t[0]["chapter"])) // 5), rng)
    linked = {(x["src"], x["dst"]) for x in run.edges}
    pool = [e for e in run.events if e["importance"] >= 2]
    by_who = defaultdict(list)
    for e in pool:
        for w in e["who"]:
            by_who[w].append(e)
    candidates = []
    tries = 0
    while len(candidates) < 50 and tries < 100000:
        tries += 1
        a = rng.choice(pool)
        if not a["who"]:
            continue
        b = rng.choice(by_who[rng.choice(a["who"])])
        if run.order[a["id"]] > run.order[b["id"]]:
            a, b = b, a
        if (a["chapter"] != b["chapter"] and set(a["storylines"]) & set(b["storylines"])
                and (a["id"], b["id"]) not in linked
                and all((a["id"], b["id"]) != (c[0]["id"], c[1]["id"]) for c in candidates)):
            candidates.append((a, b, None))
    tasks = []
    for a, b, kind in chosen + candidates:
        ia, ib = text.best(a["chunk"], a["what"]), text.best(b["chunk"], b["what"])
        tasks.append({"src": a["id"], "dst": b["id"], "run": kind,
                      "stratum": "edge" if kind else "shared_line",
                      "chapters_apart": abs(text.chapters.index(b["chapter"]) - text.chapters.index(a["chapter"])),
                      "a_html": card(a, run.names) + text.window(ia, 2, 2, mark=ia),
                      "b_html": card(b, run.names) + text.window(ib, 2, 2, mark=ib)})
    rng.shuffle(tasks)
    return tasks


def out_degree(run: Run) -> Counter:
    return Counter(x["src"] for x in run.edges)


def pack_compare(run: Run, rng: random.Random) -> list[dict]:
    tenth = lambda e: run.text.tenth(e["chapter"])
    pool = (spread([e for e in run.events if e["importance"] == 3], 150, tenth, rng)
            + spread([e for e in run.events if e["importance"] == 2], 150, tenth, rng)
            + spread([e for e in run.events if e["importance"] == 1], 100, tenth, rng))
    tasks, seen = [], set()
    while len(tasks) < SIZES["compare"]:
        a, b = rng.sample(pool, 2)
        pair = tuple(sorted((a["id"], b["id"])))
        if pair in seen:
            continue
        seen.add(pair)
        tasks.append({"a": a["id"], "b": b["id"],
                      "a_html": card(a, run.names), "b_html": card(b, run.names)})
    return tasks


def pack_top(run: Run, rng: random.Random) -> list[dict]:
    deg = out_degree(run)
    turning = sorted((e for e in run.events if e["importance"] == 3),
                     key=lambda e: (-deg[e["id"]], run.order[e["id"]]))
    pool = turning[:70]
    rest = [e for e in run.events if e["importance"] >= 2 and e not in pool]
    pool += spread(rest, TOP_POOL - len(pool), lambda e: run.text.tenth(e["chapter"]), rng)
    pool.sort(key=lambda e: run.order[e["id"]])
    items = [{"id": e["id"], "title": f'{e["chapter_title"]}: {e["title"]}', "body": e["what"]}
             for e in pool]
    return [{"items": items}]


def pack_event(run: Run, rng: random.Random) -> list[dict]:
    by_chunk = defaultdict(list)
    for e in run.events:
        by_chunk[e["chunk"]].append(e)
    chunks = list(by_chunk)
    ordinary = spread(chunks, 15, lambda c: run.text.tenth(by_chunk[c][0]["chapter"]), rng)
    boundary = [c for c in chunks if c.endswith("-01") or any(e["kind"] == "воспоминание" for e in by_chunk[c])]
    dense = sorted(chunks, key=lambda c: -len(by_chunk[c]))[:20]
    picked = list(dict.fromkeys(ordinary + rng.sample(boundary, 5) + rng.sample(dense, 5)))
    tasks = []
    for c in picked:
        evs = by_chunk[c]
        for e in rng.sample(evs, min(4, len(evs))):
            i = run.text.best(c, e["title"] + " " + e["what"])
            tasks.append({"event": e["id"], "chunk": c, "card": card(e, run.names),
                          "context": run.text.window(i, WINDOW, WINDOW, mark=i)})
    return tasks[:SIZES["event"]]


SPEECH_VERB = re.compile(r"—[^—]*—\s*(\w+\s+)?(сказал|спросил|ответил|крикнул|прошептал|произн[её]с|"
                         r"пробормотал|воскликнул|бросил|заметил|усмехнул|протянул|выдохнул)", re.I)


def pack_quote(run: Run, rng: random.Random) -> list[dict]:
    text = run.text
    chunk_of = {i: c for c, idx in text.by_chunk.items() for i in idx}
    speech = [i for i, p in enumerate(text.paras) if p["text"].startswith("—") and i in chunk_of]
    tagged = [i for i in speech if SPEECH_VERB.search(text.paras[i]["text"])]
    plain = sorted(set(speech) - set(tagged))
    tenth = lambda i: text.tenth(text.paras[i]["chapter"])
    chosen = [(i, "tagged") for i in spread(tagged, 30, tenth, rng)]
    chosen += [(i, "untagged") for i in spread(plain, SIZES["quote"] - 30, tenth, rng)]
    tasks = []
    for i, stratum in chosen:
        facts = run.extract.get(chunk_of[i], {})
        roster = [c["name"] for c in facts.get("characters", [])]
        tasks.append({"para": text.paras[i]["id"], "stratum": stratum,
                      "context": text.window(i, 5, 2, mark=i),
                      "options": [{"value": n} for n in roster]
                      + [{"value": "unknown"}, {"value": "not speech"}]})
    rng.shuffle(tasks)
    return tasks


PACKERS = {"alias": pack_alias, "place": pack_place, "link": pack_link, "compare": pack_compare,
           "top": pack_top, "event": pack_event, "quote": pack_quote}


def pack(book: str) -> None:
    run = Run(book)
    out = gold_dir(book) / "packets"
    out.mkdir(parents=True, exist_ok=True)
    for task in TASKS:
        rng = random.Random(f"{SEED}-{task}")
        items = PACKERS[task](run, rng)
        for n, it in enumerate(items, 1):
            it["gid"] = f"{task}-{n:04d}"
        data = [{"data": it} for it in items]
        write_json(out / f"{task}.json", data)
        repeat = rng.sample(data, max(1, round(len(data) * REPEAT_SHARE))) if task != "top" else data
        write_json(out / f"{task}-repeat.json", repeat)
        print(f"{task}: {len(items)} tasks, {len(repeat)} to repeat")


# --- answers -------------------------------------------------------------------

# The task fields kept with an answer; the rest (html) is display only.
KEEP = {"alias": ("kind", "a", "b", "stratum"), "place": ("event", "where_text", "run"),
        "link": ("src", "dst", "run", "stratum", "chapters_apart"), "compare": ("a", "b"),
        "top": ("items",), "event": ("event", "chunk"), "quote": ("para", "stratum")}


def answer(result: list[dict]) -> dict:
    out = {}
    for r in result:
        v = r.get("value", {})
        if "choices" in v:
            out[r["from_name"]] = v["choices"] if len(v["choices"]) > 1 or r["from_name"] in MULTI \
                else v["choices"][0]
        elif "text" in v:
            out[r["from_name"]] = "\n".join(v["text"]).strip()
        elif "ranker" in v:
            out[r["from_name"]] = v["ranker"]
    return out


MULTI = {"features"}


def task_of(gid: str) -> str:
    return gid.rsplit("-", 1)[0]


def import_export(book: str, path: Path, repeat: bool = False) -> None:
    export = json.loads(path.read_text(encoding="utf-8"))
    out = gold_dir(book) / "answers" / ("repeat" if repeat else "")
    out.mkdir(parents=True, exist_ok=True)
    rows: dict[str, dict[str, dict]] = defaultdict(dict)
    for t in export:
        gid = t["data"].get("gid")
        done = [a for a in t.get("annotations", []) if not a.get("was_cancelled") and a.get("result")]
        if not gid or not done:
            continue
        last = max(done, key=lambda a: a.get("updated_at") or a.get("created_at") or "")
        task = task_of(gid)
        row = {"gid": gid, **{k: t["data"].get(k) for k in KEEP[task]},
               **answer(last["result"]), "at": last.get("updated_at") or last.get("created_at")}
        rows[task][gid] = row
    for task, new in rows.items():
        file = out / f"{task}.jsonl"
        old = {}
        if file.exists():
            old = {r["gid"]: r for r in map(json.loads, file.read_text(encoding="utf-8").splitlines())}
        old.update(new)
        file.write_text("".join(json.dumps(old[g], ensure_ascii=False) + "\n" for g in sorted(old)),
                        encoding="utf-8")
        print(f"{task}: {len(new)} answers in, {len(old)} in {file}")


def load(book: str, task: str, repeat: bool = False) -> list[dict]:
    file = gold_dir(book) / "answers" / ("repeat" if repeat else "") / f"{task}.jsonl"
    if not file.exists():
        return []
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line]


def score(book: str) -> dict:
    from . import scores

    return scores.score(book)
