"""Where each book's stage outputs live: work/<book>/.

Every stage reads the previous stage's files and writes its own, so a run
can stop anywhere and pick up again.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def work_dir(book: str) -> Path:
    path = ROOT / "work" / book
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, data) -> None:
    # Write then rename, so an interrupted run never leaves half a file.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
