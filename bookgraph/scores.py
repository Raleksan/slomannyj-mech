"""Gold measures: the run's answers against gold/<book>/answers/.

The metrics are plain functions over plain data, so tests can check each
one on small hand-made cases. Every rate carries a 95% bootstrap interval
over the gold items it was measured on.
"""

import math
import random
import re
from collections import defaultdict

from .store import read_json, work_dir

BOOTSTRAP = 1000
SEED = 20261006
TOP_CHARACTERS = 20


# --- statistics ----------------------------------------------------------------

def interval(items: list, stat, rounds: int = BOOTSTRAP) -> tuple[float, float]:
    """The 2.5th and 97.5th percentiles of stat over resamples of items."""
    if not items:
        return (math.nan, math.nan)
    rng = random.Random(SEED)
    values = sorted(v for v in (stat([rng.choice(items) for _ in items]) for _ in range(rounds))
                    if v is not None and not math.isnan(v))
    if not values:
        return (math.nan, math.nan)
    return (values[int(0.025 * (len(values) - 1))], values[int(0.975 * (len(values) - 1))])


def rate(items: list, stat) -> dict:
    v = stat(items)
    lo, hi = interval(items, stat)
    return {"value": None if v is None or math.isnan(v) else round(v, 4),
            "low": round(lo, 4), "high": round(hi, 4), "n": len(items)}


def mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else math.nan


def kappa(pairs: list[tuple]) -> float:
    """Cohen's kappa of two labelings of the same items."""
    if not pairs:
        return math.nan
    po = mean(a == b for a, b in pairs)
    left, right = defaultdict(int), defaultdict(int)
    for a, b in pairs:
        left[a] += 1
        right[b] += 1
    n = len(pairs)
    pe = sum(left[k] * right.get(k, 0) for k in left) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


# --- coreference ---------------------------------------------------------------

def clusters_of(mentions: list, same: list[tuple]) -> list[set]:
    """Clusters of mentions joined by the same pairs (union-find)."""
    parent = {m: m for m in mentions}

    def find(m):
        while parent[m] != m:
            parent[m] = parent[parent[m]]
            m = parent[m]
        return m

    for a, b in same:
        parent[find(a)] = find(b)
    groups = defaultdict(set)
    for m in mentions:
        groups[find(m)].add(m)
    return list(groups.values())


def _where(clusters: list[set]) -> dict:
    return {m: i for i, c in enumerate(clusters) for m in c}


def muc(key: list[set], response: list[set]) -> tuple[float, float, float]:
    def side(a, b):
        where = _where(b)
        num = sum(len(c) - len({where.get(m, ("alone", m)) for m in c}) for c in a)
        den = sum(len(c) - 1 for c in a)
        return num / den if den else math.nan
    return prf(side(key, response), side(response, key))


def b_cubed(key: list[set], response: list[set]) -> tuple[float, float, float]:
    def side(a, b):
        where = _where(b)
        total = sum(len(c) for c in a)
        s = sum(len(c & b[where[m]]) / len(c) if m in where else 1 / len(c) for c in a for m in c)
        return s / total if total else math.nan
    return prf(side(response, key), side(key, response))


def ceaf_e(key: list[set], response: list[set]) -> tuple[float, float, float]:
    def phi(k, r):
        return 2 * len(k & r) / (len(k) + len(r))
    sim = assignment([[phi(k, r) for r in response] for k in key])
    return prf(sim / len(response) if response else math.nan, sim / len(key) if key else math.nan)


def lea(key: list[set], response: list[set]) -> tuple[float, float, float]:
    """Link-based entity-aware: each entity weighted by its size."""
    def links(n):
        return n * (n - 1) / 2

    def side(a, b):
        num = den = 0.0
        for c in a:
            if len(c) == 1:
                # A singleton counts as a self-link (Moosavi and Strube 2016).
                resolved = 1.0 if any(c == r for r in b) else 0.0
            else:
                resolved = sum(links(len(c & r)) for r in b) / links(len(c))
            num += len(c) * resolved
            den += len(c)
        return num / den if den else math.nan
    return prf(side(response, key), side(key, response))


def prf(p: float, r: float) -> tuple[float, float, float]:
    f = 2 * p * r / (p + r) if p == p and r == r and p + r else (0.0 if p == p and r == r else math.nan)
    return (p, r, f)


def assignment(sim: list[list[float]]) -> float:
    """The largest total similarity of a one-to-one matching (Hungarian, O(n³))."""
    if not sim or not sim[0]:
        return 0.0
    rows, cols = len(sim), len(sim[0])
    n = max(rows, cols)
    big = max(max(r) for r in sim)
    cost = [[(big - sim[i][j]) if i < rows and j < cols else big for j in range(n)] for i in range(n)]
    u, v, p, way = [0.0] * (n + 1), [0.0] * (n + 1), [0] * (n + 1), [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [math.inf] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], math.inf, 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    return sum(sim[p[j] - 1][j - 1] for j in range(1, n + 1) if p[j] and p[j] <= rows and j <= cols)


# --- ranking -------------------------------------------------------------------

def ndcg(gold: list, system: list, k: int) -> float:
    """nDCG@k of a system ranking against a gold top list, best first."""
    rel = {g: len(gold) - i for i, g in enumerate(gold)}
    dcg = sum(rel.get(s, 0) / math.log2(i + 2) for i, s in enumerate(system[:k]))
    ideal = sum(rel[g] / math.log2(i + 2) for i, g in enumerate(gold[:k]))
    return dcg / ideal if ideal else math.nan


# --- the run under test --------------------------------------------------------

class Run:
    def __init__(self, book: str) -> None:
        from .resolve import key

        wd = work_dir(book)
        self.entities = read_json(wd / "entities.json")
        threads = read_json(wd / "threads.json")
        self.events = {e["id"]: e for e in threads["events"]}
        self.order = {e: i for i, e in enumerate(self.events)}
        self.edges = {(x["src"], x["dst"]): x["type"] for x in threads["edges"]}
        self.key = key
        self.forms: dict[tuple, str] = {}
        for kind in ("characters", "places", "groups"):
            for x in sorted(self.entities[kind], key=lambda x: x["mentions"]):
                for f in [x["name"], *x["aliases"]]:
                    self.forms[(kind, f)] = x["id"]
        chars = sorted(self.entities["characters"], key=lambda x: -x["mentions"])
        self.main = {x["id"] for x in chars[:TOP_CHARACTERS]}

    def entity(self, kind: str, name: str) -> str | None:
        return self.entities["index"].get(f"{kind}:{self.key(name)}") or self.forms.get((kind, name))


# --- per task ------------------------------------------------------------------

def decided(rows: list[dict], field: str, drop=("uncertain", "not enough context")) -> list[dict]:
    return [r for r in rows if r.get(field) and r[field] not in drop]


def score_alias(run: Run, rows: list[dict]) -> dict:
    rows = [r for r in decided(rows, "verdict") if r["verdict"] in ("same", "different")]
    if not rows:
        return {}
    items = [(r["verdict"] == "same", (ea := run.entity(r["kind"], r["a"])) is not None
              and ea == run.entity(r["kind"], r["b"]), r) for r in rows]
    out = {
        "alias.precision": rate(items, lambda xs: mean(g for g, p, _ in xs if p)),
        "alias.recall": rate(items, lambda xs: mean(p for g, p, _ in xs if g)),
    }
    main_wrong = [r for g, p, r in items if p and not g and run.entity(r["kind"], r["a"]) in run.main]
    out["alias.false_merges_main"] = {"value": len(main_wrong)}
    out["alias.split_errors"] = {"value": sum(g and not p for g, p, _ in items)}
    out["alias.merge_errors"] = {"value": sum(p and not g for g, p, _ in items)}
    # Clusters over the name forms the gold set covers, per kind.
    chars = [r for r in rows if r["kind"] == "characters"]
    mentions = sorted({f for r in chars for f in (r["a"], r["b"])})
    key = clusters_of(mentions, [(r["a"], r["b"]) for r in chars if r["verdict"] == "same"])
    by_entity = defaultdict(set)
    for m in mentions:
        by_entity[run.entity("characters", m) or ("alone", m)].add(m)
    response = list(by_entity.values())
    for name, fn in (("muc", muc), ("b3", b_cubed), ("ceaf_e", ceaf_e), ("lea", lea)):
        p, r, f = fn(key, response)
        out[f"coref.{name}"] = {"value": round(f, 4), "p": round(p, 4), "r": round(r, 4)}
    gold_single = {next(iter(c)) for c in key if len(c) == 1}
    sys_single = {next(iter(c)) for c in response if len(c) == 1}
    out["coref.singleton_accuracy"] = {"value": round(mean((m in gold_single) == (m in sys_single)
                                                           for m in mentions), 4)}
    return out


def score_place(run: Run, rows: list[dict]) -> dict:
    rows = [r for r in rows if r.get("place")]
    if not rows:
        return {}

    def gold(r):
        return None if r["place"].startswith("none") else r["place"].split()[0]
    items = [(gold(r), run.events.get(r["event"], {}).get("where")) for r in rows]
    return {"places.accuracy": rate(items, lambda xs: mean(g == p for g, p in xs)),
            "places.resolved_when_known": rate([x for x in items if x[0]],
                                               lambda xs: mean(p is not None for _, p in xs))}


LINK_NONE = ("none",)


def score_link(run: Run, rows: list[dict]) -> dict:
    rows = decided(rows, "link")
    if not rows:
        return {}
    items = [(r["link"] not in LINK_NONE, (r["src"], r["dst"]) in run.edges, r) for r in rows]
    out = {"links.precision": rate(items, lambda xs: mean(g for g, p, _ in xs if p)),
           "links.recall": rate(items, lambda xs: mean(p for g, p, _ in xs if g)),
           # No retrieval yet: recall@k arrives with M1's candidates.
           "links.candidate_recall": {"value": None}}
    typed = [(r["link"], run.edges[(r["src"], r["dst"])]) for g, p, r in items if g and p]
    if typed:
        out["links.type_accuracy"] = rate(typed, lambda xs: mean(a == b for a, b in xs))
    return out


def importance(run: Run, eid: str) -> float:
    e = run.events.get(eid, {})
    return e.get("salience", e.get("importance", 0))


def score_compare(run: Run, rows: list[dict]) -> dict:
    rows = [r for r in decided(rows, "winner") if r["winner"] in ("A", "B")]
    if not rows:
        return {}

    def right(r):
        a, b = importance(run, r["a"]), importance(run, r["b"])
        if a == b:
            return 0.5
        return 1.0 if (a > b) == (r["winner"] == "A") else 0.0
    return {"importance.pairwise": rate(rows, lambda xs: mean(right(r) for r in xs)),
            "importance.ties": rate(rows, lambda xs: mean(importance(run, r["a"]) == importance(run, r["b"])
                                                          for r in xs))}


def score_top(run: Run, rows: list[dict]) -> dict:
    if not rows or not rows[0].get("rank"):
        return {}
    gold = list(rows[0]["rank"].get("top", []))
    pool = [i["id"] for r in rows for i in r.get("items", [])] or list(rows[0]["rank"].get("events", []))
    pool = pool or list(run.events)
    deg = defaultdict(int)
    for s, _ in run.edges:
        deg[s] += 1
    system = sorted(pool, key=lambda e: (-importance(run, e), -deg[e], run.order.get(e, 0)))
    k = min(30, len(gold))
    if not k:
        return {}
    return {"importance.ndcg30": {"value": round(ndcg(gold, system, 30), 4)},
            f"importance.top{k}_overlap": {"value": round(len(set(gold[:k]) & set(system[:k])) / k, 4)}}


def score_event(run: Run, rows: list[dict]) -> dict:
    rows = decided(rows, "verdict")
    if not rows:
        return {}
    return {"events.real": rate(rows, lambda xs: mean(r["verdict"] in ("correct", "details wrong") for r in xs)),
            "events.correct": rate(rows, lambda xs: mean(r["verdict"] == "correct" for r in xs))}


def score_quote(run: Run, rows: list[dict]) -> dict:
    rows = [r for r in rows if r.get("speaker")]
    if not rows:
        return {}
    # Speakers come in stage 1b (M2); until then, how many lines are attributable.
    return {"quotes.known_speaker": rate(rows, lambda xs: mean(r["speaker"] not in ("unknown", "not speech")
                                                               for r in xs))}


SCORERS = {"alias": score_alias, "place": score_place, "link": score_link, "compare": score_compare,
           "top": score_top, "event": score_event, "quote": score_quote}

# What two passes over the same task are compared on.
AGREE = {"alias": "verdict", "place": "place", "link": "link", "compare": "winner",
         "event": "verdict", "quote": "speaker"}


def agreement(book: str) -> dict:
    from .gold import load

    out = {}
    for task, field in AGREE.items():
        first = {r["gid"]: r.get(field) for r in load(book, task)}
        pairs = [(first[r["gid"]], r.get(field)) for r in load(book, task, repeat=True) if r["gid"] in first]
        if pairs:
            out[f"agree.{task}"] = {"value": round(mean(a == b for a, b in pairs), 4),
                                    "kappa": round(kappa(pairs), 4), "n": len(pairs)}
    return out


def silver_agreement(book: str) -> dict:
    """How often the silver judge answers as the hand answers do."""
    from .gold import load
    from .silver import load as load_silver

    out = {}
    for task, field in AGREE.items():
        hand = {r["gid"]: r.get(field) for r in load(book, task)}
        pairs = [(hand[r["gid"]], r.get(field)) for r in load_silver(book, task) if r["gid"] in hand]
        if pairs:
            out[f"silver.agree.{task}"] = {"value": round(mean(a == b for a, b in pairs), 4),
                                           "kappa": round(kappa(pairs), 4), "n": len(pairs)}
    return out


def score(book: str, silver: bool = False) -> dict:
    """The run against the hand answers, or with silver against the judge's."""
    from .gold import load
    from .silver import load as load_silver

    run = Run(book)
    out = {}
    for task, fn in SCORERS.items():
        out.update(fn(run, load_silver(book, task) if silver else load(book, task)))
    out.update(silver_agreement(book) if silver else agreement(book))
    return out


def evidence_ids(text: str) -> list[str]:
    return re.findall(r"ch\d+\.p\d+", text or "")
