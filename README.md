# book-graph

A storyline graph and a linked Obsidian vault from a book, made by a local
LLM (Qwen3.8-27B, abliterated) on a rented GPU.

## Stages

Each stage reads the previous one's files in `work/<book>/` and writes its
own, so a run can stop and resume; the model stages cache every answer.

| stage | model | writes |
|---|---|---|
| `parse books/NAME.fb2.zip` | no | `chapters.json`: chapters, scenes, paragraphs |
| `chunk NAME` | no | `chunks.json`: ~6k-token pieces cut at scene breaks |
| `calibrate NAME` | tokenizer | `calibration.json`, then rechunks |
| `extract NAME [-c 1-3]` | yes | `extract/<chunk>.json`: events, characters, places, groups, relations |
| `resolve NAME` | yes | `entities.json`: one entity per person, place, group, with aliases |
| `thread NAME` | yes | `threads.json`: storylines, events, cause and continuation links |
| `summarize NAME` | yes | `notes/`: chapter, character, storyline, place and group texts, overview |
| `render NAME` | no | `out/NAME/<title>/` Obsidian vault and `out/NAME/graph.html` |

`progress NAME [-w 10]` shows the running stage: done/total, ETA, tokens,
GPU load and busy server slots, the most present characters so far.

## A GPU host

```bash
scripts/deploy.sh Ubuntu@HOST a100      # or a6000; llama.cpp + GGUF + llama-server
scripts/analyze.sh Ubuntu@HOST books/slomannyj_mech-b302190.fb2.zip
scripts/status.sh Ubuntu@HOST slomannyj_mech
```

`deploy.sh` installs CUDA build tools, builds llama.cpp, fetches the GGUF
with aria2c, runs llama-server under systemd on 127.0.0.1:8080 and copies
this repo to `~/book-graph` with a venv. `analyze.sh` runs the pipeline in
the host's tmux session `bookgraph`; `status.sh` redraws its progress.

On an A100 80 GB, `host/vllm.sh` swaps llama-server for vLLM with the bf16
weights, which batches parallel requests much better (see the measurements
in `bookgraph/llm.py` and `host/vllm.sh`).

Profiles in `host/profiles/`:

| profile | weights | context |
|---|---|---|
| a100 | Q8_0_L, 38.8 GB | 8 slots × 16k |
| a6000 | Q5_K_L, 22.9 GB | 4 slots × 16k |

## Locally

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[llm]'
ssh -N -L 8080:127.0.0.1:8080 Ubuntu@HOST &
.venv/bin/python -m bookgraph extract slomannyj_mech -c 1-3
```

`BOOKGRAPH_LLM` overrides the server URL. `-c` counts chapters in reading
order, not by title (in «Сломанный Меч», «Глава 72.1» is 72).

Books go in `books/`, which git ignores, as do `work/` and `out/`.
