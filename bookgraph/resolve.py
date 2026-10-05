"""Stage 3: one entity per person, place and group across the whole book.

Chunks name the same person many ways ("Жон Арк", "Жона", "Арк"). First
every name is reduced to the normal forms of its words with pymorphy3, which
merges case endings. Names that then share a meaningful word, or a written
form, land in one candidate set; sets of one are accepted as they are, and
the model splits each larger set into real entities, since a shared surname
may be a family rather than one person.

Writes work/<book>/entities.json: entities by kind, each with id, name,
aliases, mention count and chunks, and an index from (chunk, name as the
chunk wrote it) to entity id.
"""

import asyncio
import collections
import re
import time

from pydantic import BaseModel

from .llm import Client
from .progress import Progress
from .store import read_json, work_dir, write_json

# Words that say what someone is, not who: never a reason to merge.
TITLES = {
    "господин", "госпожа", "мистер", "миссис", "мисс", "сэр", "леди", "лорд",
    "капитан", "генерал", "майор", "полковник", "лейтенант", "сержант", "рядовой",
    "профессор", "доктор", "директор", "учитель", "учительница", "король", "королева",
    "принц", "принцесса", "мать", "отец", "мама", "папа", "брат", "сестра", "сестрёнка",
    "братец", "дед", "бабушка", "старик", "старуха", "девочка", "мальчик", "командир",
    "солдат", "охотник", "охотница", "глава", "госпожа", "фон", "де", "ван", "аль",
}
KINDS = {"characters": "персонажа", "places": "места", "groups": "организации или группы"}


class Cluster(BaseModel):
    name: str
    members: list[int]


class Clusters(BaseModel):
    clusters: list[Cluster]


_morph = None


def lemma(word: str) -> str:
    global _morph
    if _morph is None:
        import pymorphy3
        _morph = pymorphy3.MorphAnalyzer()
    word = word.lower().replace("ё", "е")
    if not re.search(r"[а-я]", word):
        return word
    parses = _morph.parse(word)
    # Prefer a reading as a name, surname or toponym when there is one.
    for p in parses:
        if {"Name", "Surn", "Patr", "Geox"} & set(p.tag.grammemes):
            return p.normal_form.replace("ё", "е")
    # Unknown names get odd verb readings ("Ансел" -> "ансест"); keep those as written.
    for p in parses:
        if p.tag.POS in ("NOUN", "ADJF"):
            return p.normal_form.replace("ё", "е")
    return word


def is_alias(form: str, name: str) -> bool:
    """A name form worth listing: capitalized, not the name itself, not a title.

    Drops the descriptions chunks also report as forms ("брат", "старик").
    """
    return form != name and form[:1].isupper() and key(form) not in TITLES


def words(name: str) -> list[str]:
    return re.findall(r"[\w'-]+", name)


def key(name: str) -> str:
    return " ".join(lemma(w) for w in words(name))


def collect(book: str, kind: str) -> dict[str, dict]:
    """Groups every mention of this kind by normalized name."""
    groups: dict[str, dict] = {}
    for path in sorted((work_dir(book) / "extract").glob("*.json")):
        data = read_json(path)
        for item in data["facts"][kind]:
            k = key(item["name"])
            if not k:
                continue
            g = groups.setdefault(k, {"key": k, "names": collections.Counter(), "forms": set(),
                                      "about": [], "chunks": []})
            g["names"][item["name"]] += 1
            g["forms"].update(item.get("forms", []))
            if data["chunk"] not in g["chunks"]:
                g["chunks"].append(data["chunk"])
            if len(g["about"]) < 3 and item.get("about"):
                g["about"].append(item["about"])
    return groups


ENDINGS = re.compile(r"(ами|ями|ого|его|ому|ему|ой|ей|ом|ем|ам|ям|ах|ях|ь|й|а|я|у|ю|е|ы|и|о)$")


def stem(token: str) -> str:
    """A crude stem for invented names pymorphy does not know ("Озпина")."""
    return ENDINGS.sub("", token) if len(token) > 4 else token


def candidate_sets(groups: dict[str, dict]) -> list[list[str]]:
    """Connected sets of keys that share a meaningful word or a written form."""
    parent = {k: k for k in groups}

    def find(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    by_token: dict[str, list[str]] = collections.defaultdict(list)
    for k, g in groups.items():
        tokens = {t for t in k.split() if t not in TITLES and len(t) > 2}
        tokens |= {key(f) for f in g["forms"] if key(f) and key(f) not in TITLES}
        tokens = {stem(t) for t in tokens}
        for t in tokens:
            by_token[t].append(k)
    for ks in by_token.values():
        for other in ks[1:]:
            parent[find(other)] = find(ks[0])
    sets: dict[str, list[str]] = collections.defaultdict(list)
    for k in groups:
        sets[find(k)].append(k)
    return list(sets.values())


def describe(i: int, g: dict) -> str:
    names = ", ".join(n for n, _ in g["names"].most_common(4))
    forms = ", ".join(sorted(g["forms"])[:8])
    about = " / ".join(g["about"])
    return (f"{i}. {names} — упоминаний во фрагментах: {len(g['chunks'])}"
            + (f"; формы: {forms}" if forms else "") + (f"; {about}" if about else ""))


SYSTEM = """Ты редактор указателя имён к роману. Тебе дают пронумерованные варианты имён {what} из разных фрагментов одной книги, с описаниями. Объедини в кластер варианты, которые обозначают одно и то же. Разные персонажи с общей фамилией (родственники) или общим словом в названии — разные кластеры. name кластера — самое полное каноническое имя в именительном падеже. Каждый номер должен попасть ровно в один кластер. Ответ — только JSON по схеме."""


async def split(client: Client, kind: str, groups: dict[str, dict], keys: list[str]) -> list[tuple[str, list[str]]]:
    keys = sorted(keys, key=lambda k: -len(groups[k]["chunks"]))
    listing = "\n".join(describe(i, groups[k]) for i, k in enumerate(keys, 1))
    answer = await client.ask(Clusters, SYSTEM.format(what=KINDS[kind]), listing, max_tokens=4096)
    seen: set[int] = set()
    out = []
    for c in answer.clusters:
        members = [m for m in c.members if 1 <= m <= len(keys) and m not in seen]
        seen.update(members)
        if members:
            out.append((c.name, [keys[m - 1] for m in members]))
    # Anything the model left out stands alone.
    for i, k in enumerate(keys, 1):
        if i not in seen:
            out.append((groups[k]["names"].most_common(1)[0][0], [k]))
    return out


async def run(book: str, concurrency: int) -> None:
    client = Client(concurrency)
    result: dict = {"index": {}}
    try:
        for kind in KINDS:
            groups = collect(book, kind)
            sets = candidate_sets(groups)
            multi = [s for s in sets if len(s) > 1]
            print(f"{kind}: {len(groups)} names, {len(multi)} sets for the model to split")
            progress = Progress(book, f"resolve {kind}", len(multi))

            async def one(s: list[str]) -> list[tuple[str, list[str]]]:
                t = time.monotonic()
                out = await split(client, kind, groups, s)
                progress.tick(", ".join(s[:3]), time.monotonic() - t,
                              f"{len(s)} names → {len(out)}", client.stats)
                return out

            clusters = [(groups[s[0]]["names"].most_common(1)[0][0], s) for s in sets if len(s) == 1]
            for part in await asyncio.gather(*(one(s) for s in multi)):
                clusters.extend(part)
            progress.finish()
            entities = []
            for name, keys in clusters:
                chunks = sorted({c for k in keys for c in groups[k]["chunks"]})
                aliases = collections.Counter()
                for k in keys:
                    aliases.update(groups[k]["names"])
                    aliases.update({f: 1 for f in groups[k]["forms"]})
                entities.append({"name": name, "aliases": sorted(a for a in aliases if is_alias(a, name)),
                                 "keys": keys, "mentions": len(chunks), "chunks": chunks,
                                 "about": [a for k in keys for a in groups[k]["about"]][:5]})
            entities.sort(key=lambda e: (-e["mentions"], e["name"]))
            prefix = kind[0]
            for i, e in enumerate(entities, 1):
                e["id"] = f"{prefix}{i:04d}"
            result[kind] = entities
            for e in entities:
                for k in e["keys"]:
                    result["index"][f"{kind}:{k}"] = e["id"]
            print(f"{kind}: {len(entities)} entities; top: "
                  + ", ".join(f"{e['name']} ({e['mentions']})" for e in entities[:10]))
    finally:
        await client.close()
    write_json(work_dir(book) / "entities.json", result)
    print(client.stats.line())


def entity_id(entities: dict, kind: str, name: str) -> str | None:
    return entities["index"].get(f"{kind}:{key(name)}")
