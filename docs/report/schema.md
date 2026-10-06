# Schema details

Fields the report proposes, beyond what PLAN.md already adds.

## Every object

| field | values |
|---|---|
| `id` | stable |
| `status` | `proposed`, `verified`, `rejected`, `superseded` |
| `confidence` | number |
| `evidence[]` | source spans; none only for a marked inference, with confidence and reasoning |
| `created_by` | which pass and prompt version |
| `version` | |
| `contradictions[]` | evidence that argues against it |

An evidence object:

```json
{
  "source_id": "ch07.sc03.p014.s002",
  "char_start": 18342,
  "char_end": 18491,
  "evidence_role": "explicit|supporting|contradicting",
  "extractor_version": "qwen27b-prompt-12"
}
```

## Events

`event_mentions[]`, `state_before`, `state_after`, `goals_affected`,
`objects`, `syuzhet_index`, `fabula_interval`, `presentation_mode`,
`global_salience`, `arc_salience`, `storyline_memberships[]`.

Presentation modes: current action, flashback scene, remembered event,
narrated backstory, dream or vision, hypothetical future, prophecy,
letter or document, repeated retelling, uncertain. Dreams and prophecies
stay out of the actual story timeline.

## Edges

`type`, `direction`, `valid_interval`, `perspective`, `mechanism`,
`evidence_at_source`, `evidence_at_target`, `verification_status`.

Typed link kinds, each with its own prompt and schema:

- direct cause;
- enabling precondition;
- motivation;
- continuation or same episode;
- sub-event;
- setup → trigger → payoff;
- foreshadow → payoff;
- mystery or question → answer;
- promise or threat → fulfilment;
- thematic or structural parallel;
- contrast;
- event coreference (two mentions of one event).

## Places

- A containment hierarchy (room → house → town).
- Three kinds of location on an event: `mentioned_location`,
  `event_location`, `inferred_location`.
- Link a place mention to a known place *before* attaching it to an event;
  allow null or unknown.

## Importance

Five separate ranked scores instead of one:

- `plot_consequence`;
- `character_change`;
- `revelation`;
- `emotional_weight`;
- `structural_turning_point`.

A quiet revelation can then rank high without being labelled an action
climax. Add a separate `decision_point` label (from CHADPOD): not every
major decision is a turning point for the whole book.

Assign levels only after ranking, by percentile or thresholds checked by a
person. Don't force a fixed number of turning points, but flag an
implausible share for review.

## Open threads

```json
{
  "thread_id": "T184",
  "type": "promise|mystery|prophecy|threat|object|secret|goal|foreshadow",
  "introduced_by": ["E311"],
  "holders": ["C07"],
  "activation_conditions": ["..."],
  "status": "open|activated|partially_resolved|resolved|abandoned",
  "resolved_by": [],
  "evidence": ["..."]
}
```

## Relationships

A relationship is a state that changes over time, with several labels, not
one fixed edge:

```json
{
  "source": "C12",
  "target": "C04",
  "dimension": "trust",
  "value": -0.7,
  "valid_from": "E882",
  "valid_to": null,
  "change": "decreased",
  "cause_event": "E882",
  "perspective": "C12|narrator|objective",
  "evidence": ["ch18.sc02.p006.s001"]
}
```

- Types, some directed and some symmetric: kinship, institutional role,
  alliance, affection, trust, hostility, power/dependence,
  obligation/debt, mentorship, knowledge/secrecy, interaction.
- **Facts about a relationship are kept apart from what each character
  believes about it.**
- Ask per scene for changes caused by what happened, not a full
  reclassification of every pair.
- Collect changes into snapshots per chapter; smooth one-scene swings with
  an HMM, CRF or Viterbi-style transition model.

## Time

- Two axes per event: `syuzhet_index` (where the reader meets it) and
  `fabula_time` (an interval, anchor or position in a partial order).
- Labels between events: before, after, overlap, equal, contains, vague,
  each with evidence and confidence.
- Inputs: time expressions, tense and aspect, ages, dated documents,
  seasons, words like "now" and "then", relative anchors.
- Prefer a partial order or rough intervals to invented exact dates.
- Mark a flashback where reading order and confident story order disagree.
- Keep story time and causal time apart: an event revealed earlier may
  explain a later one; a prophecy shown early may point to an uncertain
  future.

## Summary claims

Atomic claims, each with supporting event IDs and source spans, marked
supported, contradicted or not enough evidence.
