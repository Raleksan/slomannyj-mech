# Plan: rebuilding the pipeline stage by stage

Based on the report «State-of-the-Art Pipeline for a Novel-Scale Russian
Narrative Knowledge Graph» (October 2026) and the follow-up research of
6 October 2026, compared against the run on «Сломанный Меч». The reports,
sorted by theme, and the analysis of the follow-up are in
[docs/report/](docs/report/README.md).
The target pipeline as diagrams: [docs/pipeline.md](docs/pipeline.md).

## Ground rules

- Each stage still reads the previous stage's files in `work/<book>/` and
  writes its own, and still caches its answers.
- `threads.json` keeps its current shape: events with `importance` 1–3,
  `where`, `storylines`, and edges with `type`. New data goes in new
  fields, so `render`, `site` and `graph.html` keep working while each
  stage changes.
- Delay irreversible decisions: merges, links and levels are hypotheses
  with evidence and confidence until the passes over the whole book.
- The work comes in four milestones. M1 needs no new model run over the
  book. M2 needs one new extraction run. M3 and M4 build on M2.

## Baseline (the first run of «Сломанный Меч»)

| measure | value |
|---|---|
| singleton entities | characters 271/556 (49%), places 58%, groups 63% |
| event places that don't resolve to a place | 573/2060 (28%); mostly sub-places: «Лестницы в Биконе», «Подвал дома Арков» |
| events marked as turning points (importance 3) | 443/2135 (21%) |
| links | 1826, of which 1414 are within single chunks; 412 cross chapters, none more than 50 chapters apart (77 chapters) |
| storylines | 25; every event has at least one |
| dialogue | 15,993 of 33,653 paragraphs (48%); a common speech verb right after the dash in only ~4% of them |
| paragraphs per chunk | median 129, max 227 |

## Model settings (do first, in `bookgraph/llm.py`)

`ask()` gains `top_k` and `seed`; every call sets its own values:

| call | settings |
|---|---|
| extraction, non-thinking | temperature 0.1–0.3, top_p 0.8, top_k 20, fixed seed |
| merge checks | 0.1–0.2, both orders of the pair |
| thinking calls (storylines, overview, hard link checks) | 0.6, top_p 0.95, top_k 20; never greedy |
| importance comparisons | 0.2–0.4, both orders, ties allowed |
| notes | 0.4–0.7 |

## Stage 0 (new): `eval`, the measuring stick, built first

Without it, every later change gets judged by eye.

- **Tool:** Label Studio in Docker, image pinned. Coreference as pairwise
  `COREF` relations. Move to INCEpTION only if chains become the
  bottleneck.
- **Packets, not the whole book:** a scene, paragraph IDs, the local
  roster, retrieved snippets, the pipeline's candidates, and accept /
  reject / uncertain / not enough context, plus "add a missed candidate".
- **Gold set** in `gold/slomannyj_mech/`, about a week of evenings:

  | item | size |
  |---|---|
  | alias pairs, with hard negatives | 200 |
  | event places | 100 |
  | cross-chapter cause/setup/payoff pairs | 100 |
  | importance comparisons, plus a ranked top 30 | 300 |
  | events with evidence | 100 |
  | quotes, mostly without explicit tags | 150 |
  | summary claims (later, for M3) | 50 |

- One annotator: re-annotate 10–15% after two weeks and report agreement
  with yourself.
- **`bookgraph eval NAME`** reports:
  - coreference in BOOKCOREF's format: MUC, B³, CEAF-e, LEA, singleton
    accuracy, split and merge errors, each separately;
  - alias pair precision and recall, false merges among the 20 main
    characters;
  - singleton rate, and unresolved-place rate;
  - for links, candidate recall@k separately from checking precision;
  - importance: pairwise accuracy against the gold comparisons, top-k
    overlap, nDCG@30;
  - bootstrap confidence intervals on every number.
- **Model A/B test:** run the gold set through the original Qwen3.8-27B
  and the abliterated one. Keep the abliterated model only if it isn't
  worse, or if the original refuses parts of the book.
- Every later step has to beat the baseline above.

## Stage 1: `parse`, stable addresses (M2)

- Give every paragraph a stable ID and position: `ch007.p0142` with
  character offsets, stored in `chapters.json` next to `scenes` (which
  stays for compatibility).
- Mark each paragraph's type:
  - `speech`: it starts with «—»;
  - `epigraph`, `poem`, `letter`, from the FB2 tags that are flattened
    today.
- No sentence splitting yet. Paragraphs are precise enough to cite and
  cheap to show.
- Tests: IDs stay the same across re-parses; offsets point back to the
  text.

## Stage 1b (new): `quotes`, who speaks each line (M2)

No Russian tool exists; this one is rules first.

- Rules, in order:
  1. explicit tag («— … — сказал Жон»);
  2. pronoun with a speech verb, resolved to a local character;
  3. a name inside the quote is the addressee, not the speaker;
  4. turn-taking, only while the set of speakers is stable;
  5. the scene's roster;
  6. gender of past-tense verbs inside the quote («я пошла»).
- The LLM picks from the local roster or `unknown` for the rest.
- Writes `quotes.json`: speaker per dialogue paragraph, with the rule
  that decided it.
- Used in stage 5 as a **weighted signal**, never a must-merge: a wrong
  turn-taking guess would merge two main characters.

## Stage 2: `chunk`, scene-shaped input with real context (M2)

- Each chunk records the paragraph IDs it covers.
- The text goes to the model with numbered paragraphs (`[142] …`) so it
  can cite them.
- Swap the 800-char prefix (`CONTEXT_CHARS`) for whole previous
  paragraphs, up to about 1.5k tokens. Stay at about 6k tokens of main
  text: the report's budget is 5–7k.
- Keep cutting at scene breaks as now.

## Stage 3: `extract`, local facts only, with evidence (M2, new run ~30 min)

Schema changes in `schemas.py`:

- **Remove `importance`** and the "3–12 events" rule. Allow zero events,
  using a clear test for what counts as an event.
- Add to events:
  - `evidence: list[int]` (paragraph numbers);
  - `features`: state change, decision, revelation, death or injury,
    irreversible, object changes hands, relationship change;
  - `objects`;
  - `mode`: what's happening now, flashback, memory, dream, prophecy,
    letter.
- Characters and places get `evidence`. Places get `inside`: «Лестницы в
  Биконе» → inside «Бикон».
- `open_threads`: promise, mystery, threat, prophecy, secret, goal or
  object, each with evidence. This is the input for the payoff work in
  stage 6b.
- `relations` become **changes**: who, to whom, which dimension (trust,
  hostility, love, kinship, rank), up or down, and evidence.
- **Citations:** first measure vLLM's schema mode, which can restrict
  `evidence` to the paragraph numbers in the chunk. Keep `json` mode if
  it's much slower. Either way, reject cited numbers outside the chunk.
- The cache hash also covers the prompt version and model name.

If the schema gets too big for one reliable call, split it in two: facts
(characters, places, events), then threads and relationship changes, with
the first answer given as input.

**Kept for later:** the stateful book memory. As a cheap version, add a
"known names" hint: entities from the previous run's `entities.json` whose
aliases appear word-for-word in the chunk. It's a hint, not authority.

## Stage 4: `embed` (new), vectors for retrieval (M1)

- **Pick the model by benchmark** on the gold alias and event pairs:
  deepvk/USER2-base, Qwen3-Embedding-0.6B as ONNX INT8 (`qwen3-embed`, no
  PyTorch) and Giga-Embeddings-480M, with BGE-M3 as a control. Measure
  speed on the laptop CPU too.
- Embed:
  - **entity profiles** as structured text: type, candidate name,
    mention, context on either side, speaker (M2), chapter, entities
    that appear with it;
  - **event cards**: title, what happened, who, where, objects, kind,
    with an asymmetric query instruction («Найди событие, которое могло
    быть причиной…») where the model supports it.
- Cache by content hash. Writes `vectors.npz` and `cards.json`.
- Adds an optional extra `embed` in `pyproject.toml`.

## Stage 4b (new): reranker, cutting candidates (M1)

- Cuts 30–50 retrieved candidates to 5–12 before the LLM, in stages 5
  and 6b. It does not replace the LLM check: relevance is not identity or
  causality.
- Qwen3-Reranker-0.6B as the quality baseline, jina-reranker-v2-base as
  the cheap one.
- Runs on the A100 as a second vLLM on port 8081, with the main server
  lowered from `--gpu-memory-utilization 0.92` to about 0.85
  (`host/vllm.sh`). The fallback is the jina model overnight on the
  laptop.
- **Gate:** gold alias recall@10 ≥ 98%; otherwise widen the cut.
- Later: LLM verdicts become training pairs for a small in-domain
  reranker.

## Stage 5: `resolve`, verified merges (core in M1, finished in M2)

1. **Places (M1):** when the exact lookup fails, match the longest known
   place name inside the text. Then try `inside` (M2), then the nearest
   embedding, then stay unknown.
   - Keep `where_text` as the sub-location.
   - Store the place hierarchy as `parent` on places.
2. **Names:**
   - pymorphy3 gives features only; record whether it knew the word or
     guessed;
   - learn inflections from the book («Жон», «Жона», «Жону», «Жоном» in
     compatible contexts), replacing `stem()`;
   - character n-grams and `ё→е` for candidates; written forms are kept
     as evidence;
   - a small RWBY lexicon (canon names, transliterations, teams, known
     relationships) as a hint, never forcing the fan fiction's own
     characters into canon ones.
3. **Candidates:** what we group today (shared name words), the nearest
   profile embeddings, n-grams and the lexicon, cut by the reranker.
   **Every singleton** gets candidates.
4. **Ruled-out merges (no model needed):**
   - different kind;
   - both appear as separate people in one event's `who`, or speak to
     each other (M2);
   - different gender, **only when pymorphy knows the word**; for
     invented and foreign names it's a soft signal.
5. **Checking:** for each uncertain pair, ask same/different/uncertain,
   in both orders. Show both profiles and 2–3 evidence paragraphs (M2) or
   descriptions (M1). The LLM picks a canonical name from the observed
   forms and says which evidence decided it.
6. **Clustering:**
   1. merge must-merge pairs with union-find, and fail loudly if a
      must-not-merge pair ends up inside one group;
   2. split the candidate graph into connected components;
   3. solve components up to ~100 nodes exactly with OR-Tools CP-SAT;
   4. larger ones: weighted Pivot, then local search (move, merge,
      split), checking must-not-merge after every move;
   5. close calls stay unresolved and go to a review list.
7. **Reversible:** decisions go to `merges.json`. Add
   `bookgraph merge NAME A=B` and `bookgraph split NAME A`, like `fix`, so
   a hand correction survives re-runs.

**Done when:** gold alias recall improves with no new false merges among
main characters, and character singletons drop well below 49%.

## Stage 6: `thread`, split into three passes

### 6a `storylines`

- Keep the tag merging that works.
- Add a `level` (main plot, subplot, character arc, relationship).
- Score the main plot by how much of the protagonist it covers, the
  chapters it spans, and its causal weight.
- Later, maybe: run Leiden on the event graph to propose lines the tags
  missed.

### 6b `links`, long-range in both directions (M1)

- For **every** event, retrieve 30–50 earlier candidates. Score them by:
  - embedding similarity;
  - shared characters, objects or places;
  - shared storyline;
  - a bonus for open threads that fit (M2).
  
  Cut to 5–12 with the reranker.
- From each setup or open thread, also search **forward** for payoffs.
  Model setup → trigger → payoff, not setup → payoff only.
- No limit on distance. Drop the 150-event window (`PRIOR_LIMIT`).
- Check in batches: one target event and its candidates per call. Ask for
  the link type, the mechanism ("how exactly"), the evidence at both ends,
  and whether the link still holds if you ignore the order of events.
  "None" is always allowed. Non-thinking by default; thinking only for
  long-range setups and payoffs.
- Link types widen to: причина, условие, мотив, продолжение, развязка,
  предвестие → развязка, вопрос → ответ, параллель.
- `eval` shows the **retrieval recall** and the **checking precision**
  separately.

### 6c `rank`, importance across the whole book (M1)

- **Starting score:**
  - number of causal links out, weighted by chapter distance;
  - number of storylines touched;
  - main characters involved;
  - features (M2);
  - centrality between storylines.
- **Tournament** over the top ~300 by starting score:
  - 3–4 comparisons per event to start (~1k), then fit Bradley–Terry
    (`choix`, I-LSR);
  - then active comparisons where scores are close, up to 6–10 per event
    (2–3k in total, minutes on vLLM);
  - extra comparisons only near the top-10 and top-30 boundaries;
  - every important pair in both orders; if they disagree, record it as
    unstable, not a win;
  - hide the chapter number and graph centrality from the judge.
- **Five scores** instead of one: plot consequence, character change,
  revelation, emotional weight, structural turning point. `importance`
  comes from the last; the others feed notes and filters.
- **Levels:** importance 3 = top ~3–5%, 2 = next ~30%, 1 = the rest.
  That's a parameter, checked on the gold comparisons.
- Also store `arc_salience`: rank within each storyline.
- Writes `salience.json`; `thread` fills `importance` from it. The old
  score per chunk stays as `local_importance`.

## Stage 7 (new, M4): `time`

- `mode` from extraction marks flashbacks, dreams and prophecies. They are
  shown differently and kept out of the main plot chain.
- Store `syuzhet` (order in the text) and a rough `fabula` order. Only
  derive the fabula where there are explicit anchors ("three years
  before"). No constraint solver until the gold set shows it's needed.

## Stage 8 (new, M4): `relations`

- Collect relationship changes into a timeline per pair: chapter,
  dimension, value, with evidence (EvolvTrip's idea of states over time).
- Smooth one-scene swings: a change must persist or be clearly signalled.
- Character notes and the site get "how the relationship changed" with
  chapter references.

## Stage 9: `summarize`, grounded (M3)

- The input is events chosen by **book-level rank**, each with its
  evidence paragraphs, within the token budget. It is no longer summaries
  of summaries.
- The answer is claims with `[event id]` citations, chosen from IDs
  actually shown.
- **Checking pass:** each claim against only its cited paragraphs,
  marked supported, partial, unsupported or contradicted. Drop or
  regenerate unsupported claims, and record the rate.
- The overview reads storyline notes and the top-ranked events, not
  chapter one-liners only.
- Check coverage by tenth of the book, since summaries tend to favour
  late-book events.

## Stage 10: `render` / `site` / `graph.html`

- Event pages show the **quotes** (evidence paragraphs), with sub-location
  and place hierarchy.
- New link types get their own styles; flashback and dream events are
  marked.
- The importance filter uses the new levels; `graph.json` keeps working.
- Character pages show the relationship timeline (M4).

## Order of work

| milestone | stages | new book run? | payoff |
|---|---|---|---|
| **M0** | model settings, eval, gold set, model A/B test | no | numbers to compare against; the right model |
| **M1** | place matching, embed, reranker, links 6b, rank 6c, singleton pass in resolve | no; links and rank need the GPU host for about 30 min | fixes three of the four measured failures |
| **M2** | parse IDs, quotes, chunk, extract schema, resolve with evidence and constraints | yes, extract plus everything after it, ~70 min | traceability, speakers, features, open threads |
| **M3** | grounded summarize, quotes on the site | summarize only | trustworthy notes |
| **M4** | time, relations, storyline hierarchy | small extra passes | the deeper layers from the report |

Each milestone is a few commits, and `eval` runs after each. Start with
the model settings and the gold-set format, then place matching.

## Open measurements

- CPU speed of the embedding candidates on Asahi.
- Whether vLLM's schema mode slows extraction.
- Whether the original Qwen3.8-27B refuses parts of the book.

## Deferred

The time-constraint solver, relationship states smoothed by an HMM, full
stateful-memory extraction, Natasha and Petrovich (the book has few
ordinary Russian names), and fine-tuning a reranker until there are a few
thousand LLM verdicts to train on.
