# Model settings and prompt rules

Things we can change directly in the code and prompts.

## Sampling

- **Extraction at temperature near zero.** We use 0.3 everywhere: the
  default of `Client.ask()` in `bookgraph/llm.py`.
- **Checking passes shuffle the order of options**, so the model doesn't
  favour A over B by position. Applies to merge checks (stage 5), link
  checks (6b) and the pairwise importance tournament (6c).

## Caching

The cache key should cover:

- source text hash;
- prompt version;
- model version;
- schema version;
- the memory snapshot the request saw.

Ours covers only the text (`text_hash()` in `bookgraph/extract.py`).

## Context budget for one 16k request

| part | tokens |
|---|---|
| source text (the scene or scenes) | 5–7k |
| preceding text (a real boundary window) | 1–2k |
| retrieved entity and storyline state | 2–3k |
| retrieved earlier event evidence | 1–2k |
| schema, examples, output | the rest |

Don't send the full cast list. Retrieve the active characters, aliases
that appear word-for-word in the scene, nearest embedding matches, open
threads and the most relevant earlier events.

## Prompt rules

- **Use the 27B model to decide between options, not to search.**
  Embeddings and sparse retrieval cut thousands of candidates to tens; the
  LLM picks among options backed by evidence.
- **Keep schemas shallow and specific to one task.** One big ontology per
  call increases omissions and answers that fit the schema but are wrong.
- **Structured output guarantees valid JSON, not true facts.**
- **Allow `uncertain`** in every check, and allow zero results in every
  extraction.
- **Causality check:** ask the verifier for evidence at both ends, the
  mechanism and the direction, and whether the link would still hold if
  you ignored the order of events. LLMs tend to infer cause from
  chronology or world knowledge rather than the text.
- **Separate story causality from real-world causality**: the question is
  what the text supports, not what is plausible.
- **Bounded yes/no questions** work better than asking for an
  unconstrained graph (knowledge-guided binary QA for document-level
  causality).
- **Generated titles and summaries are never evidence.** Only source text
  is.
