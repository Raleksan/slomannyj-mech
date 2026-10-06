# Evaluation

How to build and use the gold set for stage 0 of PLAN.md.

## Before annotating

Write guidelines *before* measuring the system, especially for:

- what counts as an event, and when two mentions are one event;
- implicit causality;
- setup versus foreshadowing;
- facts about a relationship versus what a character believes about it.

The Corpus Novelties alias guidelines (see [resources](resources.md)) are a
starting point for names, descriptions, titles and aliases.

## Sampling

Not a random set of chunks. Four groups:

| group | size |
|---|---|
| ordinary scenes, spread over every tenth of the book | 20–30 |
| boundary scenes: chapter edges, flashbacks, letters, narrator changes | 10–15 |
| dense scenes with many characters and events | 10–15 |
| targeted hard cases | 100–200 aliases and epithets, all suspected long-range payoffs, all detected flashbacks, major relationship reversals |

## Pilot sizes

These are engineering targets, not guarantees:

- 40–60 scenes;
- 250–400 event mentions;
- 500–1000 coreference pair decisions, concentrated on hard cases;
- 150–250 event-relation candidates;
- 100 relationship-state observations;
- 100–200 summary claims.

## Annotation

- Annotate 20–25% twice and settle the disagreements.
- Send low-margin pairs and high-impact merges or splits to a person
  (active learning).

## Challenge buckets

Keep these even when rare, with enough examples to see:

- aliases with no shared word;
- relatives with the same surname;
- title-only mentions;
- flashbacks;
- nested places;
- false causality from chronology;
- objects that pay off far later;
- thematic parallels;
- narrator beliefs versus character beliefs.

## Metrics by layer

| layer | main metrics | slices |
|---|---|---|
| mentions, entities | span F1, type F1, MUC / B³ / CEAF, LEA, alias pair F1 | major/minor character, pronoun/name/epithet, distance, singleton, dialogue |
| places, event arguments | linking accuracy, top-k recall, argument role F1, precision of "none" | explicit/implicit, containment, metonymy |
| events | trigger and evidence span F1, argument F1, event coreference F1 | action/state/revelation/decision, scene density |
| importance | nDCG@k, pairwise accuracy, Kendall/Spearman, top-k F1 | tenth of book, main plot/subplot, character arc |
| long-range links | candidate recall@k; checked edge precision/recall/F1 | distance bucket, cause/payoff/parallel, explicit/implicit |
| plot hierarchy | event-to-arc B³, adjusted Rand, hierarchy purity, boundary F1 | overlap, minor arcs, frame narrative |
| time | pairwise relation macro-F1, consistency after closure, cycle count, Kendall tau | flashback, vague anchor, document/dream/prophecy |
| relationships | typed edge F1, change-point F1, state accuracy per chapter | direction, perspective, rare pairs |
| summaries | claim faithfulness, citation precision/recall, major-event recall, BooookScore | length, level, tenth of book |

Notes:

- **LEA** weights links by entity importance, so it exposes damaging
  errors on main characters that MUC/B³/CEAF dilute.
- **Report candidate recall@k separately from checking precision** for
  long-range links. Otherwise a good checker hides retrieval failures, and
  a good retriever gets blamed for checker errors.
- For coreference, also report the number of false merges, fragmentation
  per main character, and accuracy on the hard-alias set.

## Statistics

- Bootstrap confidence intervals on every metric.
- Paired tests when comparing pipeline versions on the same items.

## Summaries specifically

- Claim faithfulness: supported / contradicted / not enough evidence.
- Evidence precision: does the cited span support the claim?
- Evidence recall: does every checkable claim have a citation?
- Content selection: recall of gold major events, arcs and state changes.
- Coherence: consistent entities, chronology, redundancy, causal
  continuity, unresolved references.
- Positional bias: coverage by tenth of the book.
- Automated checks are for catching regressions; keep a person reviewing a
  stratified sample of claims.
