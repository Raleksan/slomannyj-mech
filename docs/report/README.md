# Notes from the pipeline report

Facts taken from «State-of-the-Art Pipeline for a Novel-Scale Russian
Narrative Knowledge Graph» (October 2026) that [PLAN.md](../../PLAN.md)
does not already use, sorted by theme. The follow-up research confirmed
that the five 2025–2026 papers it leans on exist (LitVISTA, CFPG,
EvolvTrip, BOOKCOREF, NarraBench); the other citations are unchecked.

| note | what it holds |
|---|---|
| [settings.md](settings.md) | model settings and prompt rules we can apply directly |
| [schema.md](schema.md) | fields for objects, edges, places, importance, threads, relationships, time |
| [diagnostics.md](diagnostics.md) | how to break down our measured errors before fixing them |
| [evaluation.md](evaluation.md) | gold-set sampling, sizes, metrics, statistics |
| [findings.md](findings.md) | research results that shaped the report's design |
| [resources.md](resources.md) | datasets, models and tools it names, with limits |
| [research-2026-10-06.md](research-2026-10-06.md) | follow-up research on the gaps, as received |
| [research-analysis.md](research-analysis.md) | what the follow-up changes in the plan, checked against our code and data |

Note: [settings.md](settings.md) says "temperature near zero"; the
follow-up corrects that to 0.1–0.3 for extraction and Qwen's own settings
for thinking calls (see the analysis).

## Most worth folding into the plan

- extraction temperature near zero ([settings](settings.md)), a one-line
  change;
- five separate importance scores in stage 6c ([schema](schema.md));
- `status` and `confidence` on every object in the stage 3 schema
  ([schema](schema.md));
- sorting a sample of singletons into the seven kinds before stage 5
  ([diagnostics](diagnostics.md));
- the "ignore chronology" check in the 6b prompt ([settings](settings.md));
- who speaks to whom as a merge signal ([diagnostics](diagnostics.md)).
