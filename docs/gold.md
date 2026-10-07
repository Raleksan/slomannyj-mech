# The gold set: how to annotate

Hand-checked answers for «Сломанный Меч», which `bookgraph eval` measures
every run by (stage 0 of [PLAN.md](../PLAN.md)). The rules were written
before any measuring, so they don't bend to fit a result. Background:
[docs/report/evaluation.md](report/evaluation.md).

You don't need to be exhaustive or fast. You need to be **consistent**: the
same kind of case gets the same answer on day 1 and day 6. When you settle a
borderline case, note it under "Your rulings" at the end of this file, so
later you (and the repeat pass) decide it the same way.

## The plan

Before M1 starts, five tasks, about 8 hours. That's six evenings of 1–1.5 h:

| evening | task | tasks | about | what it measures |
|---|---|---|---|---|
| 1–2 | alias | 197 | 2–3 h | false and missed merges: 49% of characters are singletons |
| 3 | place | 100 | 1 h | the 28% of event places that don't resolve |
| 4 | link | 100 | 2 h | long-range links: none over 50 chapters today |
| 5 | compare | 300 | 1.5–2 h | importance: 21% of events are turning points |
| 6 | top | 1 | 1 h | the 30 events that matter most |

Before M2: event (96 tasks, ~2 h) and quote (150, ~1.5 h).
Two weeks after each task is done: its repeat pass (see the end).

After each task: export, import, `eval` (below). From then on that number
is what M1 has to beat.

## Setup, once

```bash
scripts/annotate.sh local up     # starts Label Studio; open http://127.0.0.1:8090
```

It uses Docker or Podman, whichever is installed, and listens on
127.0.0.1 only. Its data is `annotate/data/` (not in git). Sign in with the
account you made; the project `alias` carries on where you left it.

**A project per task.** They are already there: `alias`, `place`, `link`, `compare`, `top`, `event` and `quote`. To
make one again, or on a fresh install (after signing up):

```bash
scripts/annotate.sh local projects alias place link compare top event quote
```

It loads `annotate/configs/TASK.xml` and `gold/slomannyj_mech/packets/TASK.json`
into a project named after the task, through Label Studio's own import, and
leaves a project whose name exists alone. By hand instead: *Create Project*
→ *Labeling Setup* → *Custom template* → *Code*: paste the config →
*Data Import*: upload the packet. The project's name doesn't matter to the
import: every task carries its own id (`alias-0042`).

## A session

1. `scripts/annotate.sh local up`, open http://127.0.0.1:8090, open the
   project, press **Label All Tasks**: it goes through the unanswered tasks
   in order.
2. For each task: read, choose, **Submit** (or Ctrl+Enter). The next task
   opens.
3. At the end: the project's **Export** → **JSON** → save the file, then

   ```bash
   .venv/bin/python -m bookgraph gold import slomannyj_mech ~/Downloads/project-3-at-2026-10-08-....json
   .venv/bin/python -m bookgraph eval slomannyj_mech
   git add gold/slomannyj_mech/answers && git commit -m "Gold: alias, 60 of 197"
   ```

   Import as often as you like: answers are replaced by task id, so a
   half-done project imports fine and a corrected answer replaces the old.
4. `scripts/annotate.sh local down`.

The committed answers are your backup; `annotate/data/` is only the work
in progress.

## Working in Label Studio

- **Changing an answer:** open the task from the project's list, change it,
  press **Update**. Import again to carry it over.
- **Skip** leaves a task unanswered; it is left out of the scores. Prefer
  *uncertain* or *not enough context*, which record that you looked.
- **The text fields** are optional everywhere. Write in them when something
  surprised you: those notes are how the guide's rules get better.
- **Keys:** in alias, 1–5 pick the answer; in compare, 1 is A, 2 is B, 3
  equal, 4 uncertain. Ctrl+Enter submits.
- **The highlighted paragraph** (yellow) is where the run's event or the
  line most likely is. It is a guess from shared words, not a fact; read
  around it.
- **Long contexts** scroll inside the task.

## Paragraph ids

Every paragraph is shown with an id like `ch007.p0142`: the chapter, and
the paragraph's place in it counting from 1 over all its scenes. Where a
task asks for evidence, cite these ids. They stay the same in M2, when the
pipeline starts citing them too.

## Always available

- **uncertain**: you read the context and can't decide.
- **not enough context**: the packet doesn't show enough to decide, and
  you don't remember the book well enough either.

Prefer either to a guess: both are left out of the scores, a guess isn't.
But don't use them to avoid thinking: if more than about one task in ten
gets one, the rule for that kind of case needs writing down.

## Aliases

*Do these two names refer to the same one, in this book?*

**On screen:** the two names side by side, each with the run's one-line
description and up to two paragraphs where it appears (a different part of
the book each). The header says the kind (characters, places, groups) and
why the pair was picked:

| stratum | the run says | what you're catching |
|---|---|---|
| merged | same | false merges: two people the run made one |
| shared_word | different | relatives, or missed merges |
| singleton | different | an epithet the run didn't recognise, or a real stranger |
| easy | different | a control: these should all be *different* |

**The rules:**

- **same**: everywhere the book uses both, they name one character (place,
  group). «Жон» and «Мрачный Мальчик» if that nickname is only ever his.
- **different**: never the same one. Relatives with one surname are
  different: «Жон Арк» and «Юлиус Арк».
- **sometimes**: one of the names is shared by several ones, so the pair is
  the same in some places only («Арк» for any of the family; «Лидер»).
  These count as different for merging: a run must not merge them.
- A title alone («Директор», «Глава Короны») is *same* only if the book
  uses it for one person throughout.
- An online handle or a disguise is *same* as the person behind it, if the
  text says who it is.
- A role taken over by someone else (a new headmaster) is *sometimes*.
- The note field: anything surprising, or another name of the same one you
  noticed.

**From the packets:**

- *Нора Валькирия | Янг* (merged): two different characters. *different*;
  this is exactly the false merge the task exists to catch.
- *Жон Арк | Мрачный Арк* (merged): read the snippets. If the nickname is
  only ever his, *same*; if it's also used for, say, his father, *sometimes*.
- *Жон Арк | Император Жона* (merged): mind the case. «Император Жона» is
  genitive, *Жон's* emperor: someone else. The run's forms come from the
  model, which sometimes takes a phrase for a name.
- *Жон Арк | Жон Базиль*: a second «Жон» with another surname is another
  person unless the text says otherwise.
- A form marked *(не найдено в тексте дословно)* never appears in the book
  as written: the model made it up or reworded it. Decide from the other
  side's snippets and your memory, or *not enough context*.

## Event places

*Where does this event happen?* Pick the place from the list that the
event's «где» belongs to.

**On screen:** the event (title, what happened, who, «где» as the model
wrote it, and the place the run resolved it to, if any), the text around
it, and a list of up to eight known places: the run's choice, places with
words in common, and the chapter's most frequent places, in random order.

**The rules:**

- **exactly**: «где» is the place itself («Бикон» for «Бикон»).
- **inside**: «где» is a part of it: a room, a street, a building in a
  city («Лестницы в Биконе» → Бикон, inside). Pick the smallest listed
  place that contains it.
- Spelling variants of one place («Андриаполь», «Андриополь») are the same
  place; pick either and say so in the field below.
- **none** if no listed place fits; write the right one in the field.

**From the packets:**

- *«Поезд Андриаполь-Мистраль»*: a moving train is in neither city. *none*,
  and write «поезд» in the field.
- *«Коридоры Академии»* with Академия Бикон, Академия Хейвен and Академия
  in the list: the context says which academy. Pick that one, *inside*. If
  the context doesn't say, *not enough context* goes in the field and the
  choice is *none*.
- *«Квартира в Мистрале»*: the flat itself isn't a known place, Мистраль
  is: Мистраль, *inside*.

## Links

*Does A (earlier) lead to B (later)?* Judge by what the text supports, not
by what is plausible, and not because A comes first.

**On screen:** two event cards, A earlier and B later, how many chapters
apart, and each one's text. Half the pairs are links the run made across
chapters (stratum *edge*, with the run's type); half are pairs the run
didn't link, sharing a character and a storyline (*shared_line*). Both kinds
can go either way.

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

**The test before any causal type:** would B still happen, the same way,
without A? If yes, it isn't причина. Then write in «how» what exactly
carries A into B; one sentence.

**From the packets:**

- *Демонстрация Подобия Жона* (ch. 5) → *Жон раскрывает своё Подобие*
  (ch. 10), which the run called продолжение: the same ability shown twice
  is not one continuing action, and the second doesn't happen *because of*
  the first. *none*, unless the text makes the second showing answer the
  first (then вопрос → ответ) or deliberately mirror it (параллель).
- *Осмотр статуи Моргена Арка* (ch. 53) → *Раскрытие тайны беременности
  Ян* (ch. 60): sharing a storyline isn't a link. *none*, unless something
  in the first scene sets up the second.
- A promise, a threat, a weapon or a secret shown early and used much later
  is предвестие even 40 chapters apart. These far links are what the run
  misses most, so take your time with them.

## Importance

*Which event matters more to the whole book?* Not to its chapter.

**On screen (compare):** two event cards. Their order on screen is random.

- Judge by consequence: how much later plot depends on it, how much it
  changes a main character, what it reveals.
- **equal** is allowed and useful.
- Chapter number and how much text the event takes don't count.
- Go fast: 300 pairs at 15–20 seconds each. If you need longer than
  that to decide, it's probably *equal* or *uncertain*.

**On screen (top):** one task, 100 candidate events in book order. Drag
the 30 that matter most to the whole book into the bucket on the right,
**most important first**; the order inside the bucket is the answer. Write
events missing from the candidates in the field, one per line, with the
chapter. Do it after compare: the 300 pairs will have warmed you up.

## Events (before M2)

*Is the run's event real, and where is it?*

**On screen:** the run's event card and about 13 paragraphs around the
highlighted one.

- **An event** is something that happens and changes the situation: an
  action, a decision, a revelation, a death, a fight, a meeting that
  matters. Not a description, a mood, or a habit («Жон часто
  тренировался» is not an event).
- **Two mentions are one event** if they describe one happening, even from
  two viewpoints.
- **correct**: real, and its title, who and where are right.
- **details wrong**: real, but a participant or the place is wrong.
- **not an event**: by the definition above.
- **not in this text**: the shown text doesn't contain it (the highlight
  missed, or the run invented it).
- **evidence**: the ids of the paragraphs where it happens, as few as show
  it: `ch001.p0042 ch001.p0043`.
- **mode**: *now* for the story's present; *flashback* when the narration
  moves to the past; *memory* when a character recalls it; *dream*,
  *prophecy*, *letter* as they say.
- **features**: tick each that holds.
- **missed**: events in the highlighted part the run doesn't have.

## Quotes (before M2)

*Who says the highlighted line?*

**On screen:** five paragraphs before the line and two after; the list is
the characters the run found in that chunk. Most lines (120 of 150) were
picked because they have no «сказал Жон» after them: those are the hard
ones stage 1b has to solve.

- Pick from the list; **unknown** if the text doesn't say; **not speech**
  if the line isn't spoken (a dash used otherwise, a thought, a sign).
- A name inside the quote is usually who is spoken *to*, not the speaker.
- **cue**: what decided it for you. Stage 1b's rules will be checked
  against these, so pick the strongest cue you used.
- If the speaker isn't in the list, type the name in the field.

## Tricky cases

- **Narrator versus character belief.** If a character believes something
  the narration doesn't confirm, it is not a fact: not a revelation, and no
  link built on it.
- **Setup versus foreshadowing.** A setup is concrete (a weapon shown, a
  promise made) and pays off; foreshadowing only hints. Both are
  предвестие here; say which in «how».
- **Relationship facts versus beliefs.** «She is his sister» is a fact;
  «he thinks she hates him» is a belief.
- **Canon RWBY and this book.** Answer for this book. If the fan fiction
  gives a canon character a new name, a new family or a new role, the book
  wins over canon.

## The repeat pass

Two weeks after finishing a task, make its repeat project: 15% of the
tasks, with the same ids, in a project of their own.

```bash
scripts/annotate.sh local projects alias-repeat
```

Answer them without looking at the first project or at your notes, then
import with `--repeat`:

```bash
.venv/bin/python -m bookgraph gold import slomannyj_mech ~/Downloads/....json --repeat
```

`eval` then prints `agree.TASK`: how often you agreed with yourself, and
Cohen's κ. Below about 80% agreement or κ 0.6, a rule is unclear: look at
the disagreements, write the ruling down below, and fix the first answers.

## When something looks wrong

- **Two of the listed places are one place, or two people in the roster are
  one person.** Answer, and say so in the text field: it is useful.
- **The task makes no sense** (a broken card, an empty context): *Skip*,
  and note its id (shown in the task's URL and in the project's list).
- **eval prints no number for a task after importing it**: the export
  didn't hold what the import expected. Check that `gold/slomannyj_mech/answers/TASK.jsonl`
  has lines, and report it; it's a bug, not your answers.

## Your rulings

Borderline cases you settled, so you settle them the same way next time.
One line each: the case, the answer, why.

- **One full name, several people** (alias-0005: «Жанна Арк» is Жон's
  mother in ch. 1 and the family's founder in ch. 36 and 53): *sometimes*,
  and say who is who in the note, with chapters. The gold set compares
  names, not mentions, so only the note records that the full name itself
  is shared; M2's paragraph ids will tell the mentions apart.
