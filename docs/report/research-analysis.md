# Analysis of the follow-up research

What [research-2026-10-06.md](research-2026-10-06.md) changes in
[PLAN.md](../../PLAN.md), checked against our code and data.

## How far to trust it

- **Mostly sound.** It says plainly where evidence is thin: Russian quote
  attribution, abliteration, ARM speed, setup–payoff extraction. Its
  numbers are mostly attributed to model cards and papers.
- **Weak sourcing in places:**
  - BOOKCOREF and NarraBench are cited to arXiv *listing* pages, not the
    papers;
  - the BooookScore finding is cited to a FABLES page;
  - the LitBank quote count is cited to an essay.
  
  The claims match the first report, so they are probably right, but the
  links don't prove them.
- **Unchecked new work:** several 2026 papers it leans on are very recent
  and unreplicated: Giga-Embeddings (arXiv 2608.23806), the abliteration
  studies (2606.05396, 2606.23375), ModernBERT quote attribution
  (2608.02359). Treat their numbers as claims.
- **It verified the five citations** from the first report as real
  (LitVISTA, CFPG, EvolvTrip, BOOKCOREF, NarraBench). That closes the open
  question in [README.md](README.md).
- **The gold set grew.** Its suggested sizes across sections 4, 7a and 8
  add up to well over 1,500 items. That's too many for one person; see
  "Gold-set budget" below.

## What it confirms

No change to the plan's direction:

- retrieve → constraints → LLM check → clustering, for both entities and
  links;
- book-level importance from pairwise comparisons with Bradley–Terry;
- searching in both directions for setups and payoffs;
- reversible merges, provenance, delaying irreversible decisions;
- an in-domain gold set, because no Russian literary dataset exists.

## What it changes

### Model settings (`bookgraph/llm.py`)

My earlier note "temperature near zero" was too strong. Qwen advises
against greedy decoding in thinking mode.

| call | now | change to |
|---|---|---|
| extract (non-thinking) | 0.3, top_p 0.9 | 0.1–0.3, top_p 0.8, **top_k 20, fixed seed** |
| merge checks (resolve) | 0.3 | 0.1–0.2, both orders |
| storylines and overview (thinking) | 0.4, top_p 0.9 | **0.6, top_p 0.95, top_k 20** |
| importance comparisons | — | 0.2–0.4, both orders, ties allowed |
| notes (summarize) | 0.3 | 0.4–0.7 |

`ask()` needs `top_k` and `seed` parameters; vLLM accepts both in the
request body.

### Abliterated model: a new A/B test (M0)

- No evidence either way for our checkpoint. One 2026 study shows
  TruthfulQA dropping 7 points after abliteration, with other benchmarks
  flat.
- Run the gold set through the original Qwen3.8-27B and the abliterated
  one. Keep the abliterated model only if it isn't worse, or if the
  original refuses the book's violence.
- It's cheap once the gold set exists: one extra deploy and a few chunks.

### Embeddings (stage 4)

- Drop "BGE-M3 by default". Benchmark on gold alias and event pairs:
  - **deepvk/USER2-base** (149M, the safe ARM choice);
  - **Qwen3-Embedding-0.6B** as ONNX INT8 (`qwen3-embed`, no PyTorch);
  - **Giga-Embeddings-480M** (best claimed Russian MTEB, immature tooling).
  
  Keep BGE-M3 as a control.
- **Embed entities as structured profiles:** type, candidate name,
  mention, context left and right, speaker, chapter, entities that appear
  with it. Not the bare name.
- **For events, use an asymmetric instruction** («Найди событие, которое
  могло быть причиной…») where the model supports it.
- Embeddings over-link characters with similar roles (two students), so
  dense retrieval is one candidate source among several, never a merge
  signal on its own.
- Cache by content hash. About 5k texts is a batch job of minutes even on
  CPU.

### Reranker: a new step in stages 5 and 6b

- Retrieve 30–50 → **reranker cuts to 5–12** → constraints → LLM.
- It reduces LLM calls but does **not** replace the LLM check. Relevance
  is not identity or causality.
- **Qwen3-Reranker-0.6B** is the quality baseline, jina-reranker-v2-base
  the cheap one.
- **Where to run it:** about 85k pairs (2,135 events × 40) is slow on the
  laptop CPU. On the A100, vLLM runs at `--gpu-memory-utilization 0.92`,
  leaving about 6 GB. Either lower it to 0.85 and serve the reranker as a
  second vLLM on port 8081, or score on the laptop overnight with the
  smaller jina model.
- **Target:** gold alias recall@10 ≥ 98% before trusting the cut.
  Otherwise the LLM never sees the right candidate.
- Later: LLM verdicts become training pairs for a small in-domain
  reranker (a few thousand pairs is enough).

### Names (stage 5)

- pymorphy3 becomes **features only**. It always produces an analysis,
  even for names it doesn't know, which explains odd lemmas like
  «Ансел» → «ансест» (handled in `lemma()`).
- **Learn inflections from the book:** «Жон», «Жона», «Жону», «Жоном» in
  compatible contexts form an observed set. This replaces the crude
  `stem()` ending-stripper.
- Character n-grams and `ё→е` for candidates; keep the written form as
  evidence.
- **Gender only as a soft signal for unknown names.** My plan made
  gender a hard must-not-merge; for Ченьцинь, Сучжоу or transliterated
  English names the final letter says nothing. Keep it hard only when
  pymorphy knows the word from its dictionary.
- **A small RWBY lexicon** (`books/slomannyj_mech.lexicon.json` or in
  `work/NAME/`): canon names, common transliterations, team names, known
  relationships. A hint for candidates; never force the fan fiction's own
  characters into canon ones.
- The LLM picks a canonical name from the observed forms; it doesn't
  invent one.
- Natasha and Petrovich only matter for ordinary Russian names, which
  this book has few of. Skip for now.

### Quote attribution: a new stage (M2)

- No Russian tool exists. Ours is rule-first.
- **Our data:** 48% of paragraphs (15,993 of 33,653) are dialogue.
  Only 4% of those have a common speech verb right after the dash
  («— … — сказал Жон»). That check used a narrow verb list, so the real
  share is higher, but explicit tags clearly cover a minority.
  Turn-taking and the LLM will carry most of the work.
- **Rules, in order:**
  1. explicit tag;
  2. pronoun with a speech verb;
  3. a name in the quote is the addressee, not the speaker;
  4. turn-taking while the set of speakers is stable;
  5. scene roster;
  6. gender of past-tense verbs inside the quote («я пошла»).
  
  Then the LLM picks from the local roster or «unknown».
- **Output:** speaker per dialogue paragraph, used as a **weighted signal**
  in clustering, never a must-merge. A wrong turn-taking guess would merge
  two main characters across a whole dialogue.

### Clustering (stage 5)

The plan said "greedy correlation clustering". Now concretely:

1. Merge must-merge pairs (exact same key, hand merges from `merges.json`)
   with union-find, and fail loudly if a must-not-merge pair ends up
   inside one group.
2. Build a sparse candidate graph and split it into connected
   components.
3. Small components (up to ~100 nodes): solve exactly with OR-Tools
   CP-SAT. It has aarch64 wheels.
4. Larger ones: weighted Pivot, then local search (move, merge, split),
   checking must-not-merge after every move.
5. Close calls stay **unresolved** and go to the review list, not forced.

### Importance tournament (stage 6c)

- **Budget:** 3–4 comparisons per event to start (~1k), fit Bradley–Terry,
  then active comparisons near close scores. Stop at 6–10 per event,
  about 2–3k in total. Short calls, so minutes on vLLM.
- **Extra comparisons only near the boundaries** of the top 10 and top 30.
- **Ask every important pair in both orders.** If the answers disagree,
  record a tie or an unstable result, not a winner.
- **Hide the chapter number and graph centrality** from the judge, so it
  judges consequence, not lateness.
- Use `choix` (I-LSR); it has no ties, so either drop unstable pairs or
  write a small Davidson likelihood.

### Links (stage 6b)

- Model **setup → trigger → payoff** (CFPG), not setup → payoff only.
- Typed checks run non-thinking. Only the hard ones (setup and payoff
  over long distances) use thinking, at Qwen's settings.

### Evidence (stages 3 and 9)

- The research says don't ask for free paragraph numbers from a 16k
  prompt. Constrain them to an enum of IDs that were actually shown.
- Our extraction chunks hold a median of 129 paragraphs (max 227). An enum
  that size is feasible with vLLM's schema mode, but we run in `json`
  mode for speed: the 30% slowdown was measured on llama.cpp, not vLLM.
  **Measure schema mode on vLLM first.**
- Either way: **check every cited number is in the chunk**, and in
  verification passes send only 5–20 retrieved paragraphs, with the enum.
- Store `unsupported`, `partial` and `contradicted`, not only a
  confidence.

### Gold-set tooling (stage 0)

- **Label Studio** in Docker, with a pinned image. Coreference as pairwise
  `COREF` relations.
- Give the annotator **packets**, not the whole book: a scene, paragraph
  IDs, the local roster, retrieved snippets, the pipeline's candidates,
  and accept / reject / uncertain / not enough context.
- One annotator: **re-annotate 10–15% after two weeks** and report
  agreement with yourself, instead of double annotation.
- Use BOOKCOREF's evaluation format for coreference, and report MUC, B³,
  CEAF-e, LEA, singleton accuracy and split/merge errors separately.
  BOOKCOREF's own results show high MUC next to 61 CoNLL F1.

## Gold-set budget

Its sizes cut to what one person can do in about a week of evenings,
most important first:

| item | size | used by |
|---|---|---|
| alias pairs, with hard negatives | 200 | stage 5, recall@10, the A/B test |
| event places | 100 | place matching |
| cross-chapter cause/setup/payoff pairs | 100 | 6b recall and precision |
| importance comparisons | 300 | 6c, instead of only a ranked top 30 |
| events with evidence | 100 | stage 3, the A/B test |
| quotes, mostly without explicit tags | 150 | quote attribution |
| summary claims | 50 | stage 9, later |

Most of these are accept/reject on pipeline candidates, which is fast.
Full scene annotation (mentions, all events) is left out until the
pipeline produces evidence spans.

## Left open

- Real CPU speed of the embedding models on Asahi: measure it.
- Whether vLLM schema mode slows extraction: measure it.
- Whether the original Qwen3.8-27B refuses parts of the book: the A/B
  test answers it.
