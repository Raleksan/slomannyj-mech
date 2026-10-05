"""Respell a name in all of a book's work data. No model.

The model sometimes writes a name its own way, as "Джон" for the book's
"Жон", in any case form. Each OLD=NEW pair replaces OLD as the start of a
word followed only by lower-case letters, so "Джону" becomes "Жону" and
"Джонс" "Жонс", but "Аджонов" stays; the lower-case form is replaced too,
for the name keys. Aliases and index keys that become duplicates are
merged. Render and site again afterwards.
"""

import re

from .store import read_json, work_dir, write_json


def patterns(pairs: list[tuple[str, str]]) -> list[tuple[re.Pattern, str]]:
    out = []
    for old, new in pairs:
        for o, n in {(old, new), (old.lower(), new.lower())}:
            out.append((re.compile(rf"(?<!\w){re.escape(o)}(?=[a-zа-яё]*(?!\w))"), n))
    return out


def respell(value, pats, counter: list[int]):
    if isinstance(value, str):
        for pat, new in pats:
            value, n = pat.subn(new, value)
            counter[0] += n
        return value
    if isinstance(value, list):
        before = counter[0]
        items = [respell(v, pats, counter) for v in value]
        # Only a list this fix touched loses repeats: "Джоном" and "Жоном".
        if counter[0] > before and all(isinstance(v, str) for v in items):
            items = list(dict.fromkeys(items))
        return items
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            k = respell(k, pats, counter)
            v = respell(v, pats, counter)
            out.setdefault(k, v)  # a key merged into an existing one keeps the first value
        return out
    return value


def run(book: str, pairs: list[tuple[str, str]]) -> int:
    pats = patterns(pairs)
    wd = work_dir(book)
    total = files = 0
    for path in sorted(wd.rglob("*.json")):
        counter = [0]
        data = respell(read_json(path), pats, counter)
        if counter[0]:
            write_json(path, data)
            total += counter[0]
            files += 1
    print(f"fix: {total} replacements in {files} files of {wd}")
    return total
