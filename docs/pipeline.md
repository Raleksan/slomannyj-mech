# How the pipeline should work

The target pipeline from [PLAN.md](../PLAN.md), drawn as three diagrams:

1. the whole pipeline;
2. the pattern of the two hardest stages (merging names and linking events);
3. which file each stage reads and writes.

Colours show the milestone that builds or changes each step. Steps with a
thick red border call the 27B model; blue dashed ones run small models
(embeddings, reranker); the rest need no model.

## 1. The whole pipeline

```mermaid
flowchart TB
    classDef m0 fill:#fde7c8,stroke:#b7791f,color:#222
    classDef m1 fill:#d6ecff,stroke:#2b6cb0,color:#222
    classDef m2 fill:#d9f2dc,stroke:#2f855a,color:#222
    classDef m3 fill:#eadcf8,stroke:#6b46c1,color:#222
    classDef m4 fill:#fbd5e0,stroke:#b83280,color:#222
    classDef same fill:#eeeeee,stroke:#777,color:#222
    classDef file fill:#ffffff,stroke:#999,color:#333,stroke-dasharray:3 3
    classDef llm stroke:#c53030,stroke-width:3px
    classDef small stroke:#3182ce,stroke-width:2px,stroke-dasharray:6 3

    book[/"books/NAME.fb2.zip"/]:::file

    subgraph SRC["Source layer: exact text with addresses"]
        parse["parse<br/>chapters, scenes, paragraphs<br/>stable IDs ch007.p0142, offsets<br/>speech / epigraph / letter marks"]:::m2
        quotes["quotes<br/>rules: tag, pronoun, addressee,<br/>turn-taking, roster, verb gender<br/>LLM for the rest"]:::m2
        chunk["chunk<br/>~6k tokens at scene breaks<br/>numbered paragraphs<br/>~1.5k tokens of previous text"]:::m2
    end

    subgraph LOCAL["Local pass: one chunk at a time, in parallel"]
        extract["extract<br/>events + evidence + features + mode<br/>characters, places with 'inside', groups<br/>open threads, relationship changes<br/>no importance, zero events allowed"]:::m2
    end

    subgraph RET["Retrieval layer"]
        embed["embed<br/>entity profiles, event cards<br/>USER2 / Qwen3-Emb / Giga, on CPU"]:::m1
        rerank["reranker<br/>Qwen3-Reranker-0.6B<br/>30–50 candidates → 5–12"]:::m1
    end

    subgraph GLOBAL["Book passes: see the whole book, decide late"]
        hand[/"merges.json<br/>bookgraph merge / split"/]:::file
        resolve["resolve<br/>names, places, groups<br/>→ one entity each"]:::m1
        story["6a storylines<br/>merge tags into lines<br/>levels: main, sub, arc"]:::same
        links["6b links<br/>back to causes, forward to payoffs<br/>setup → trigger → payoff"]:::m1
        rank["6c rank<br/>graph prior → pairwise tournament<br/>→ Bradley–Terry → levels 1–3"]:::m1
        time["time<br/>flashbacks, dreams, prophecies<br/>reading order vs story order"]:::m4
        rel["relations<br/>timeline per pair of characters"]:::m4
    end

    subgraph OUT["Output"]
        summarize["summarize<br/>top-ranked events + evidence<br/>→ cited claims → claim check"]:::m3
        render["render / site / graph.html<br/>quotes on event pages<br/>new link types, place tree"]:::m3
    end

    subgraph EVAL["Measuring"]
        gold[/"gold/NAME/<br/>Label Studio packets"/]:::file
        evalx["eval<br/>coreference, places, link recall,<br/>link precision, importance"]:::m0
        ab["model A/B<br/>abliterated vs original"]:::m0
    end

    book --> parse
    parse --> chunk
    parse --> quotes
    chunk --> extract
    extract --> embed
    embed --> resolve
    rerank -.-> resolve
    quotes -- "speaker: weighted signal" --> resolve
    hand -- "hand decisions win" --> resolve
    resolve --> story
    resolve --> links
    embed --> links
    rerank -.-> links
    story -- "shared line raises a candidate" --> links
    extract -- "open threads" --> links
    links -- "causal weight" --> rank
    story -- "rank within each line" --> rank
    extract -- "mode" --> time
    extract -- "relationship changes" --> rel
    resolve --> rel
    rank --> summarize
    links --> summarize
    time --> summarize
    rel --> summarize
    parse -- "evidence paragraphs" --> summarize
    summarize --> render
    rank --> render

    gold --> evalx
    resolve -.-> evalx
    links -.-> evalx
    rank -.-> evalx
    quotes -.-> evalx
    gold --> ab
    resolve -. "review list" .-> hand

    class quotes,extract,resolve,story,links,rank,summarize,ab llm
    class embed,rerank small
```

Milestones: <span style="background:#fde7c8">M0 measuring</span> ·
<span style="background:#d6ecff">M1 no new extraction</span> ·
<span style="background:#d9f2dc">M2 new extraction</span> ·
<span style="background:#eadcf8">M3 grounded notes</span> ·
<span style="background:#fbd5e0">M4 deeper layers</span> ·
<span style="background:#eeeeee">kept as now</span>

### Reading it

- **Source layer.** Everything later points back here. Generated text is
  never evidence; only paragraphs are.
- **Local pass.** Each chunk is read once, for recall. It records what is
  in the text and does not judge importance or identity: those need the
  whole book.
- **Retrieval layer.** Cheap models narrow thousands of candidates to tens,
  so the 27B model only decides between a few.
- **Book passes.** Every decision that needs the whole book: who is who,
  what caused what, what matters most. Decisions stay reversible: hand
  merges in `merges.json` override the model, and close calls go to a
  review list.
- **Output.** Notes are built from ranked, cited events, then each claim is
  checked against its paragraphs.
- **Measuring.** `eval` scores each book pass against the gold set after
  every change; the A/B test picks the model.

## 2. The candidate funnel (stages 5 and 6b)

Merging names and linking events follow the same pattern: find many
candidates cheaply, cut them, rule some out without a model, ask the model
about the rest, then decide globally.

```mermaid
flowchart TB
    classDef cheap fill:#d6ecff,stroke:#2b6cb0,color:#222
    classDef rule fill:#eeeeee,stroke:#777,color:#222
    classDef llm fill:#fde7c8,stroke:#c53030,stroke-width:3px,color:#222
    classDef out fill:#d9f2dc,stroke:#2f855a,color:#222

    subgraph R5["resolve: is A the same as B?"]
        direction LR
        c5["candidates<br/>shared name word · char n-grams<br/>learned inflections · RWBY lexicon<br/>profile embeddings"]:::cheap
        r5["reranker<br/>keep 5–12<br/>gate: gold recall@10 ≥ 98%"]:::cheap
        h5["ruled out<br/>different kind · both in one event<br/>talk to each other · gender only<br/>if pymorphy knows the word"]:::rule
        l5["LLM, both orders<br/>same / different / uncertain<br/>picks name from seen forms<br/>names the deciding evidence"]:::llm
        k5["clustering<br/>must-merge first · CP-SAT ≤ 100 nodes<br/>Pivot + local search above<br/>close calls → review list"]:::out
        c5 --> r5 --> h5 --> l5 --> k5
    end

    subgraph R6["links: did A lead to B?"]
        direction LR
        c6["candidates, both directions<br/>event-card embeddings · shared<br/>characters, objects, places, line<br/>open threads that fit"]:::cheap
        r6["reranker<br/>keep 5–12<br/>no distance limit"]:::cheap
        h6["ruled out<br/>wrong order in the book<br/>dream or prophecy as a cause"]:::rule
        l6["LLM per target event<br/>type · mechanism · evidence at<br/>both ends · holds without<br/>chronology? · 'none' allowed"]:::llm
        k6["edges<br/>причина · условие · мотив<br/>продолжение · развязка<br/>предвестие · вопрос → ответ · параллель"]:::out
        c6 --> r6 --> h6 --> l6 --> k6
    end

    R5 ~~~ R6
```

`eval` measures each funnel at two points: how many gold pairs survive to
the LLM (recall of the candidate steps), and how many of the LLM's answers
are right (precision of the check). Mixing the two hides which half fails.

## 3. Files

```mermaid
flowchart LR
    classDef st fill:#eeeeee,stroke:#777,color:#222
    classDef f fill:#ffffff,stroke:#999,color:#333
    classDef nf fill:#d9f2dc,stroke:#2f855a,color:#222

    parse:::st --> ch["chapters.json"]:::f
    ch --> quotes:::st --> q["quotes.json"]:::nf
    ch --> chunk:::st --> cj["chunks.json"]:::f
    cj --> extract:::st --> ex["extract/*.json"]:::f
    ex --> embed:::st --> v["vectors.npz<br/>cards.json"]:::nf
    ex --> resolve:::st
    v --> resolve
    q --> resolve
    mj["merges.json"]:::nf --> resolve
    resolve --> en["entities.json"]:::f
    en --> thread:::st
    v --> thread
    ex --> thread
    thread --> th["threads.json"]:::f
    thread --> sa["salience.json"]:::nf
    th --> summarize:::st
    sa --> summarize
    ch --> summarize
    summarize --> no["notes/"]:::f
    no --> render:::st
    th --> render
    gj["graph.json"]:::f --> render
    render --> out["out/NAME/"]:::f
```

White: files that exist now (some gain fields). Green: new files.
