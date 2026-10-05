# book-graph

A storyline graph and a linked Obsidian vault from a book, made by a local
LLM (Qwen3.8-27B, abliterated, as GGUF under llama-server) on a rented GPU.

## Stages

Each stage reads the previous one's files in `work/<book>/` and writes its
own, so a run can stop and resume.

| stage | needs the model | writes |
|---|---|---|
| `parse books/NAME.fb2.zip` | no | `chapters.json`: chapters, scenes, paragraphs |
| `chunk NAME` | no | `chunks.json`: ~6k-token pieces cut at scene breaks |
| `calibrate NAME` | tokenizer | `calibration.json`, then rechunks |
| `extract NAME [-c 1-3] [-j 8]` | yes | `extract/<chunk>.json`: events, characters, places, groups, relations |

Still to come: name resolution, storylines and cross-chapter links,
summaries, the Obsidian vault and `graph.html`.

## Running

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[llm]'
.venv/bin/python -m bookgraph parse books/slomannyj_mech-b302190.fb2.zip
.venv/bin/python -m bookgraph chunk slomannyj_mech
ssh -N -L 8080:127.0.0.1:8080 USER@HOST &   # llama-server on the GPU host
.venv/bin/python -m bookgraph calibrate slomannyj_mech
.venv/bin/python -m bookgraph extract slomannyj_mech -c 1-3
```

`BOOKGRAPH_LLM` overrides the server URL (default `http://127.0.0.1:8080`).
`-c` counts chapters in reading order, not by title.

Books go in `books/`, which git ignores, as do `work/` and `out/`.
