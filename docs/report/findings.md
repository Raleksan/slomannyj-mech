# Research findings

Results the report bases its design on.

## Summarizing books

- **BooookScore:** updating a summary incrementally keeps more detail but
  is less coherent than merging summaries in a hierarchy. Hence the
  report's hybrid: incremental memory for recall, a hierarchy over the
  whole book for the final text.
- **FABLES:**
  - most errors in book-length summaries concern events and character
    states, and often need indirect reasoning about the story to catch;
  - LLM judges don't reliably catch unfaithful claims, so people are still
    needed;
  - summaries over-weight events near the end of the book.
- Generate summaries from checked records, not from summaries of
  summaries.

## Ranking

- Pairwise LLM ranking is more reliable than isolated relevance scores.
- Efficient variants use sorting or sliding windows instead of comparing
  all pairs.
- Combining pointwise labels with pairwise preferences beats trusting raw
  self-ratings.
- Fit the pairwise results with Bradley–Terry, Thurstone or Elo, and
  repeat close comparisons.

## Turning points

- TRIPOD formalized turning points for films and screenplays. Its expected
  positions shouldn't be imposed on novels, which may have braided plots,
  frame stories, several climaxes, or no five-point structure.
- CHADPOD covers character decision points, a separate label.

## Causality

- LLMs often infer cause from the order of events or from world knowledge
  rather than the text (the "Failure Modes of LLMs for Causal Reasoning on
  Narratives" paper).
- Codified Foreshadowing–Payoff (2026) models foreshadow → trigger →
  payoff triples and keeps a pool of unresolved commitments instead of
  free-form memory. The report adapts it for detection: extract setups
  with high recall, retrieve possible payoffs, check strictly twice.
- A narratology-based framework separates timelines, causelines and
  storylines; the report adopts that separation.

## Graph structure

- GraphRAG communities are a retrieval index, not ground truth for plot or
  causality. Use them to propose candidates and bridges; an LLM with
  evidence decides the edges.
- Run community detection (Leiden/Louvain) at several resolutions over
  separate edge layers: shared characters, causes, closeness in time,
  similarity, shared goals or objects, place, relationship changes,
  motifs. Don't collapse the layers into one score until the weights are
  tuned on gold data.

## Memory and merges

- Stateful memory improves continuity, but an early wrong summary or merge
  that becomes authoritative causes cascading errors. Every memory item is
  a revisable hypothesis backed by source text.
- Memory updates are append-only proposals; a merge is a reversible
  redirect, a split is a new version.
- Union-find is unsafe for merges: one false bridge joins everything
  transitively and is hard to undo.

## Relationships

- Early work on literary relationships already treated them as changing
  sequences rather than fixed labels; later work learned them without full
  supervision.
- A 2025 study evaluated LLMs on tracking evolving book relationships
  zero-shot, with error analysis.
- EvolvTrip tracks characters' beliefs, desires and intentions over time.

## The state of the field

No mature benchmark or package solves, for a whole Russian novel at once:
coreference, event extraction, story order, setup and payoff, changing
relationships, arc hierarchy and grounded summaries. The best result comes
from combining resources and testing on a gold set for this novel.
NarraBench's taxonomy is a check that evaluation doesn't collapse all of
this into generic QA.
