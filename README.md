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
| `render NAME` | no | `out/NAME/<title>/` Obsidian vault, `graph.html` beside it and inside it |
| `site NAME [-o DIR]` | no | `out/NAME/site/`: the vault as a static website |
| `fix NAME OLD=NEW` | no | respells a name in all of `work/NAME/`, in every case form; then render and site |

`progress NAME [-w 10]` shows the running stage: done/total, ETA, tokens,
GPU load and busy server slots, the most present characters so far.

## A website

`site` turns the same notes into plain HTML: a page per note with the
pages that link to it, a list per folder, a search box over names,
aliases and events, and the graph, whose links open the pages. Links are
relative, so it works from disk, under any path, and on GitHub Pages
(it writes `.nojekyll`). To look at it locally:

```bash
python3 -m http.server -d out/slomannyj_mech/site 8765
```

To publish it, push the folder's contents to a repository's `gh-pages`
branch and choose that branch under Settings → Pages:

```bash
cd out/slomannyj_mech/site && git init -b gh-pages && git add -A && git commit -m site
git push -f git@github.com:USER/REPO.git gh-pages
```

## A GPU host

```bash
scripts/deploy.sh -b vllm Ubuntu@HOST a100     # A100 80 GB: vLLM, bf16 weights
scripts/deploy.sh Ubuntu@HOST a6000            # smaller cards: llama.cpp, GGUF
scripts/analyze.sh -j 24 Ubuntu@HOST books/slomannyj_mech-b302190.fb2.zip
scripts/status.sh Ubuntu@HOST slomannyj_mech
```

`deploy.sh` sets up the model server under systemd on 127.0.0.1:8080 and
copies this repo (with `books/`) to `~/book-graph` with a venv. The llama
backend builds llama.cpp with CUDA and fetches the GGUF with aria2c; the
vllm backend installs vLLM and fetches the bf16 safetensors. `analyze.sh`
runs every stage in the host's tmux session `bookgraph`; `-j` is how many
requests go at once (24 for vLLM, 8 for llama.cpp on a100, 4 on a6000).
`status.sh` redraws the progress. Afterwards copy the results home:

```bash
rsync -az Ubuntu@HOST:book-graph/work/slomannyj_mech/ work/slomannyj_mech/
.venv/bin/python -m bookgraph render slomannyj_mech
```

For «Сломанный Меч» (1.35M tokens) on an A100 with vLLM the whole run took
about 70 minutes: extract 28, resolve 3, thread 12, summarize 12. llama.cpp
on the same card writes only 86–120 tokens/s however many requests run, and
vLLM about 470 (see `bookgraph/llm.py` and `host/vllm.sh`).

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
order, not by title (in «Сломанный Меч», «Глава 72.1» is 72). Tests, for
the stages that need no model: `.venv/bin/python -m unittest discover tests`.

Books go in `books/`, which git ignores, as do `work/` and `out/`.
