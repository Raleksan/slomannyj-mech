# The gold set: how to annotate

Hand-checked answers for «Сломанный Меч», which `bookgraph eval` measures
every run by (stage 0 of [PLAN.md](../PLAN.md)). Written before any
measuring, so the rules don't bend to fit a result. Background:
[docs/report/evaluation.md](report/evaluation.md).

## Setup

Label Studio runs on a remote host, never on the laptop:

```bash
scripts/annotate.sh ubuntu@HOST up       # once: start it (pinned Docker image)
scripts/annotate.sh ubuntu@HOST tunnel   # each session; open http://127.0.0.1:8090
scripts/annotate.sh ubuntu@HOST backup   # after each session: copy to annotate/data/
```

Sign up on the first visit; the page is reachable only through the tunnel.
Make one project per task: *Create Project* → name it after the task →
*Labeling Setup* → *Custom template* → *Code*, paste
`annotate/configs/TASK.xml` → *Data Import*, upload
`gold/slomannyj_mech/packets/TASK.json`.

When a project is done: *Export* → *JSON*, then

```bash
.venv/bin/python -m bookgraph gold import slomannyj_mech ~/Downloads/project-1-at-....json
.venv/bin/python -m bookgraph eval slomannyj_mech
```

Importing again replaces answers by task id, so export as often as you
like. Commit `gold/slomannyj_mech/answers/`.

**Repeat pass.** Two weeks after finishing a task, make a project
`TASK-repeat` from `packets/TASK-repeat.json` (15% of the tasks, the same
ids), annotate it without looking at the first answers, and import with
`--repeat`. `eval` then prints `agree.TASK`: how often you agreed with
yourself, and Cohen's κ.

## Order and time

| task | tasks | about | why first |
|---|---|---|---|
| alias | 197 | 2 h | the worst measured failure (49% singletons) |
| place | 100 | 1 h | M1 changes place matching first |
| link | 100 | 2 h | long-range links are M1's main work |
| compare | 300 | 2 h | M1's ranking |
| top | 1 | 1 h | |
| event | 96 | 2 h | M2's extraction |
| quote | 150 | 1.5 h | M2's speakers |

Do alias, place, link, compare and top before M1 starts; event and quote
before M2.

## Paragraph ids

Packets show each paragraph with an id like `ch007.p0142`: the chapter,
and the paragraph's place in it counting from 1 over all its scenes. Cite
evidence by these ids. The highlighted paragraph is where the run's event
or the line in question most likely is; it is a guess, not a fact.

## Always available

- **uncertain**: you read the context and can't decide.
- **not enough context**: the packet doesn't show enough to decide, and
  you don't remember the book well enough either.

Prefer either to a guess. Both are left out of the scores.

## Aliases

*Do these two names refer to the same one, in this book?*

- **same**: everywhere the book uses both, they name one character
  (place, group). «Жон» and «Мрачный Мальчик» if that nickname is only
  ever his.
- **different**: never the same one. Relatives with one surname are
  different: «Жон Арк» and «Юлиус Арк».
- **sometimes**: one of the names is shared by several ones, so the pair
  is the same in some places only («Арк» for any of the family; «Лидер»).
  These count as different for merging: a run must not merge them.
- A title alone («Директор», «Глава Короны») is *same* only if the book
  uses it for one person throughout.
- An online handle or a disguise is *same* as the person behind it, if the
  text says who it is.
- A role taken over by someone else (a new headmaster) is *sometimes*.
- The note field: anything surprising, or another name of the same one
  you noticed.

## Event places

*Where does this event happen?* Pick the place from the list that the
event's «где» belongs to.

- **exactly**: «где» is the place itself («Бикон» for «Бикон»).
- **inside**: «где» is a part of it: a room, a street, a building in a
  city («Лестницы в Биконе» → Бикон, inside). Pick the smallest listed
  place that contains it.
- Spelling variants of one place («Андриаполь», «Андриополь») are the same
  place; pick either and say so in the field below.
- **none** if no listed place fits; write the right one in the field.

## Links

*Does A (earlier) lead to B (later)?* Judge by what the text supports, not
by what is plausible, and not because A comes first.

| type | when |
|---|---|
| причина | A makes B happen |
| условие | A makes B possible, without causing it |
| мотив | A gives a character a reason for doing B |
| продолжение | B continues the same action or situation |
| развязка | B resolves what A opened: a conflict, a plan, a threat |
| предвестие | A hints at or sets up B before it happens (a setup and its payoff) |
| вопрос → ответ | A raises a question or mystery that B answers |
| параллель | A and B mirror each other, without one leading to the other |
| none | no link the text supports |

Test before choosing a causal type: would B still happen, the same way,
without A? If yes, it is not причина. Write in «how» what exactly carries
A into B; a sentence is enough.

## Importance

*Which event matters more to the whole book?* Not to its chapter.

- Judge by consequence: how much later plot depends on it, how much it
  changes a main character, what it reveals.
- **equal** is allowed and useful.
- Chapter number and how much text the event takes don't count.
- **top**: drag the 30 events that matter most into the bucket, most
  important first. Name missed events in the field, with their chapter.

## Events

*Is the run's event real, and where is it?*

- **An event** is something that happens and changes the situation: an
  action, a decision, a revelation, a death, a fight, a meeting that
  matters. Not a description, a mood, or a habit («Жон часто
  тренировался» is not an event).
- **Two mentions are one event** if they describe one happening, even
  from two viewpoints.
- **correct**: real and its title, who and where are right.
- **details wrong**: real, but a participant or the place is wrong.
- **not an event**: by the definition above.
- **not in this text**: the shown text doesn't contain it (the highlight
  missed, or the run invented it).
- **evidence**: the ids of the paragraphs where it happens, as few as
  show it.
- **mode**: *now* for the story's present; *flashback* when the narration
  moves to the past; *memory* when a character recalls it; *dream*,
  *prophecy*, *letter* as they say.
- **features**: tick each that holds.
- **missed**: events in the highlighted part the run doesn't have.

## Quotes

*Who says the highlighted line?*

- Pick from the list, which is the chunk's characters; **unknown** if the
  text doesn't say; **not speech** if the line isn't a spoken line (a
  dash used otherwise, a thought, a sign).
- A name inside the quote is usually who is spoken *to*, not the speaker.
- **cue**: what decided it for you. This is how stage 1b's rules will be
  checked, so pick the strongest cue you used.
- If the speaker isn't in the list, type the name in the field.

## Implicit and tricky cases

- **Narrator versus character belief.** If a character believes something
  the narration doesn't confirm, it is not a fact: not a revelation, and
  no link built on it.
- **Setup versus foreshadowing.** A setup is concrete (a weapon shown, a
  promise made) and pays off; foreshadowing only hints. Both are
  предвестие here; say which in «how».
- **Relationship facts versus beliefs.** «She is his sister» is a fact;
  «he thinks she hates him» is a belief.
