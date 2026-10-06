# Resources named in the report

Links as the report gives them; not checked.

## Russian

| resource | use | limit |
|---|---|---|
| [RuCoCo](https://arxiv.org/abs/2206.04925) | Russian coreference training data: ~1M words, ~150k mentions | news, not fiction |
| [RuCoCo-2023](https://github.com/dialogue-evaluation/RuCoCo-2023) | shared task code and baselines | news |
| [RuCo-BERT](https://github.com/gleb-skobinsky/RuCo-BERT) | open Russian coreference baseline (AllenNLP) | older architecture, domain mismatch |
| [NEREL](https://elar.urfu.ru/handle/10995/112238) | Russian nested named entities and relations | not novel-level coreference |
| [Razmecheno](https://ar5iv.labs.arxiv.org/html/2201.09997) | named entities in diaries from Prozhito, closer to literary language | not coreference |

## Literary, in English

| resource | use | limit |
|---|---|---|
| [BookNLP](https://github.com/booknlp/booknlp) | book pipeline: characters, coreference, quote attribution | English; a baseline, not gold |
| [LitBank](https://github.com/dbamman/litbank) | literary coreference schema and data, 100 works | English, passages not whole novels |
| [BookCoref](https://arxiv.org/html/2507.12075v1) | coreference across a whole book | needs adapting to Russian |
| [Corpus Novelties alias guidelines](https://arxiv.org/pdf/2410.00522.pdf) | how to annotate names, descriptions, titles, aliases | guidelines only |
| [Quotation attribution in novels](https://aclanthology.org/2023.acl-short.64.pdf) | who says each line | English |

## Retrieval

| resource | use | limit |
|---|---|---|
| [BGE-M3](https://github.com/FlagOpen/FlagEmbedding/tree/master/research/BGE_M3) | dense, sparse and multi-vector retrieval; 100+ languages; 8192-token input | check on Russian fiction and on event similarity |
| [multilingual-E5-large](https://huggingface.co/intfloat/multilingual-e5-large) | the alternative to compare against | |
| [GraphRAG](https://microsoft.github.io/graphrag/) | hierarchical communities, local and global graph search | not a judge of causality or literary meaning |

## Events, causality, time

| resource | use | limit |
|---|---|---|
| [MAVEN-ERE](https://github.com/THU-KEG/MAVEN-ERE) | event coreference, time, cause and sub-event relations: schemas, data, code | news; distances within a document, not a book |
| [Knowledge-guided binary QA for causality](https://aclanthology.org/2024.findings-emnlp.986.pdf) | breaks causal checks into yes/no questions | |
| [NarrativeTime](https://aclanthology.org/2024.lrec-main.1054.pdf) | dense timeline annotation and evaluation | doesn't cover every flashback distinction |
| MATRES, TimeBank-Dense, TDDiscourse | general time-relation benchmarks | |
| [Multi-event temporal ordering](https://openreview.net/pdf/a1438f77762043ae4fb182320bf0eb0b100fcfbe.pdf) | rank many events at once for a consistent order | |
| [Codified Foreshadowing–Payoff](https://arxiv.org/html/2601.07033v1) | foreshadow → trigger → payoff triples, a pool of open commitments | made for generation, needs adapting to detection |
| [Narratology-based storyline extraction](https://research.rug.nl/en/publications/a-narratology-based-framework-for-storyline-extraction/) | separates timelines, causelines, storylines | |

## Plot structure

| resource | use | limit |
|---|---|---|
| [TRIPOD](https://github.com/ppapalampidi/TRIPOD) | turning-point annotation and evaluation | film priors don't fit novels |
| [CHADPOD](https://arxiv.org/pdf/2405.07282.pdf) | character decision points | |
| [NarraBench](https://ar5iv.labs.arxiv.org/html/2510.09869) | taxonomy of narrative-understanding tasks | |
| [LitVISTA](https://aclanthology.org/2026.acl-long.1024.pdf) | benchmark for narrative orchestration in literary text (2026) | |

## Relationships and characters

| resource | use |
|---|---|
| [Dynamic relationships in novels](https://ar5iv.labs.arxiv.org/html/1511.09376) | relationships as changing sequences |
| [Unsupervised evolving relationships](https://people.cs.umass.edu/~miyyer/pubs/2017_relationships_aaai.pdf) | learned without full supervision |
| [Evolving relationships with LLMs (2025)](https://aclanthology.org/2025.wnu-1.12.pdf) | zero-shot prompting and error analysis |
| [EvolvTrip](https://ar5iv.labs.arxiv.org/html/2506.13641) | characters' beliefs, desires and intentions over time |

## Summaries and citations

| resource | use | limit |
|---|---|---|
| [FABLES](https://github.com/mungg/FABLES) | faithfulness and content selection in book summaries, public data | English, recent books; people still needed |
| [BooookScore](https://github.com/lilakk/BooookScore) | coherence of long summaries, open package | coherence is not faithfulness |
| [LongCite](https://github.com/THUDM/LongCite) | fine-grained citations in long contexts, benchmark | made for QA; adapt to fiction summaries |
| [Attribute or Abstain](https://aclanthology.org/2024.emnlp-main.463.pdf) | cite support or decline to answer | |

## Coreference scoring

- [Reference implementation of B³ and CEAF for predicted mentions](https://research.google/pubs/scoring-coreference-partitions-of-predicted-mentions-a-reference-implementation/)
- [LEA scorer](https://github.com/ns-moosavi/LEA-coreference-scorer)
