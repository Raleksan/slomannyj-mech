# Diagnosing the current errors

The report's point: break each measured failure down by cause before
fixing it. A raw percentage is not an error rate.

## Singletons (49% of characters, 58% of places, 63% of groups)

Sort a sample into seven kinds:

1. real one-off characters (correct);
2. generic roles promoted to characters («стражник»);
3. aliases that should have merged;
4. groups of people taken as one person;
5. confusion between person and place;
6. FB2 or OCR artifacts;
7. hallucinations, with no support in the text.

Report the singleton rate separately for real singletons and for wrong
fragmentation.

## Unresolved places (28%)

Probably a mix of:

- place names the extraction missed;
- failure to link a mention to a known place;
- a location carried over from earlier text without being restated;
- metonymy (a place name standing for its people or rulers);
- the schema forcing a value when the text gives none.

Score these stages separately. A sample of 25 suggests nesting is the main
cause («Лестницы в Биконе», «Подвал дома Арков», «Ворота Анселя»), but
measure it.

## Russian names

Model each part separately and keep the written form:

- first name, patronymic, surname;
- diminutive and pet forms;
- title;
- kinship term;
- profession;
- epithet;
- pronouns and dropped subjects.

Morphology is evidence, not an identity key. A shared word is a candidate
signal only, never a reason to merge on its own.

## Signals for merging and not merging

- **Who speaks to whom tells you who is who.** Two aliases that share no
  word can be told apart because one speaks to the other.
- **Candidates from:** normalized name matching, patronymic/surname
  compatibility, contextual embeddings of the mention, similar
  descriptions, shared dialogue partners, apposition («капитан, Иксор,
  …»), aliases seen before.
- **Must not merge:** different type, different gender or number, both
  speaking at once as different people, explicit contrast, conflicting
  family roles, conflicting timelines.
- **Recheck after the whole book:** singletons, clusters held together by
  one weak link, and unusually large clusters.

## Arc boundaries

Signals that an arc starts or ends:

- a shift in meaning (embedding distance);
- a change of cast or place;
- a change in a character's goal;
- a time jump;
- a change of event community;
- an event that bridges communities.

Find turning points inside each arc first; promote to book level only the
events that join or redirect major arcs.

## Main plot and arcs

- Score a main-plot candidate by protagonist coverage, time span, causal
  weight, high-importance events, and connection to the climax and
  resolution, not by cluster size.
- Character arcs come from changes in goals, beliefs, values, status and
  relationships; plot arcs come from cause and goal threads.
- An event may belong to several arcs at once.
- Hierarchy: book → main plot / major subplot / frame narrative → arc or
  thread → episode → scene event.
