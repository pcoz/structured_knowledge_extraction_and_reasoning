# structured_knowledge_extraction_and_reasoning

A pipeline that takes unstructured text in and produces a queryable
knowledge graph: extract structured facts, persist them, apply
inference rules, serve grounded queries. No LLM in the runtime loop.
Every response traces to its source text.

> **Copyright © Edward Chalk.** The architecture and source code are
> the original work of Edward Chalk; copyright protection is asserted
> to the extent permitted by law. Free for non-commercial use; for
> commercial licensing see [LICENSE.md](LICENSE.md).

## Project layout

```
.
├── README.md          (this file)
├── LICENSE.md
├── docs/
│   ├── ARCHITECTURE.md     ← the method, with a glossary of all terms
│   └── NOVELTIES.md        ← what's new vs prior art (FrameNet, OpenIE, ...)
└── src/
    ├── wikipedia_utils.py  ← read Wikipedia XML, strip markup, split sentences
    ├── kb/                 ← Wikipedia-extracted knowledge graph
    │   ├── extract.py      (extraction pipeline)
    │   ├── query.py        (load + lookup + path + chain queries)
    │   ├── reason.py       (inference rules + derived facts)
    │   ├── kb_1000_articles.json           (pre-built base KB)
    │   └── kb_1000_articles_extended.json  (base + derived facts)
    ├── ahab/               ← conversational demo (Moby-Dick / Captain Ahab)
    │   ├── utterances.py   (curated quote corpus)
    │   └── talk.py         (theme-matched retrieval)
    └── git_rag/            ← enterprise RAG demo (Git manual)
        ├── knowledge.py    (curated KB items)
        └── query.py        (intent + topic matching)
```

## Quick start

```bash
# Wikipedia KB — query the pre-built graph
python src/kb/query.py

# Wikipedia KB — derive new facts via inference rules, then query
python src/kb/reason.py

# Talk to Captain Ahab — 13 questions answered with verbatim Melville quotes
python src/ahab/talk.py

# Enterprise RAG — 15 Git developer questions answered from the manual
python src/git_rag/query.py
```

Each runs in a few seconds. Standard-library Python only; no
external dependencies.

## How to read the docs

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — the three-layer
  pipeline (extraction → indexing/inference → serving), the
  rationale, and a glossary explaining every in-house term used in
  the code: *phenocryst*, *groundmass*, *xenolith*, *cell*, *shape*,
  *context*, *flavour*, *interaction type*, *triple*, *entity*,
  *alias map*, *Horn clause*, *fixpoint*, *provenance*,
  *construction time*, *AI-cheating*, *theme*, *speech act*, etc.
- **[docs/NOVELTIES.md](docs/NOVELTIES.md)** — what this contributes
  that isn't standard in the literature, with prior art and the
  specific contribution per item.
- **[LICENSE.md](LICENSE.md)** — free for non-commercial use; for
  commercial licensing contact licensing@sapientronic.ai.

## How to set up the knowledge representation

Three layers, built in this order:

### Layer 1 — Extract structured facts from text

```python
from wikipedia_utils import read_articles
from kb.extract import extract_facts_from_article, KnowledgeGraph

articles = read_articles(n=1000)       # needs a Wikipedia XML dump
graph = KnowledgeGraph()
for title, raw in articles:
    for triple in extract_facts_from_article(title, raw):
        graph.add(triple)

graph.save("kb_1000_articles.json")
```

Patterns are defined in `src/kb/extract.py` (verb-anchored regex
with entity-span detection). Coverage is bounded by the patterns;
expect ~2 facts per article from the default library. The production
path uses Claude API to extract per article; same JSON output.

### Layer 2 — Apply inference rules

`src/kb/reason.py` defines Horn-clause rules:

```
R1: X TUTORED_BY Y, Y TUTORED_BY Z   → X INTELLECTUAL_DESCENDANT_OF Z
R2: X TUTORED Y, Y CONQUERED Z       → X TAUGHT_CONQUEROR_OF Z
R3: X CHILD_OF Y, Y CHILD_OF Z       → X GRANDCHILD_OF Z
R4: X BORN_DATE D                     → X LIVED_IN era_tag
R5: X BORN_DATE B, X DIED_DATE D     → X LIVED_FOR years
R6: X CONQUERED Y, X CONQUERED Z (Y≠Z) → X IS_A MULTI_CONQUEROR
R7: |X.born - Y.born| ≤ 50            → X CONTEMPORARY_OF Y
```

Each derived fact carries its rule name + input triples + a
"since...therefore..." explanation for provenance.

### Layer 3 — Query and serve

```python
from kb.query import KB
kb = KB.load("src/kb/kb_1000_articles_extended.json")

# Entity card
for t in kb.out_facts("Aristotle"):
    print(t.relation, t.object)

# Multi-hop chain: Aristotle's student's conquests
for end, path in kb.chain_query("Aristotle", ["TUTORED", "CONQUERED"]):
    print(end)        # → Persia, Egypt, Empire

# Path query: connect any two entities
paths = kb.find_paths("Alexander the Great", "Socrates", max_hops=4)
# → Alexander ← Aristotle ← Plato ← Socrates

# Reasoning queries — derived facts available like base facts
kb.in_facts("Socrates", "INTELLECTUAL_DESCENDANT_OF")    # → [Aristotle]
```

## How to extend

### Add facts directly to the JSON

Append to `src/kb/kb_1000_articles.json`:

```json
{
  "subject": "Marie Curie",
  "relation": "DISCOVERED",
  "object": "Radium",
  "source_article": "Marie Curie",
  "source_sentence_idx": -1
}
```

Picked up on next load. No code change needed for queries.

### Add a new relation type

1. Pick a relation name (e.g., `INFLUENCED_BY`).
2. Optional: add a verb-anchor in `src/kb/extract.py` for auto-mining.
3. Optional: add an inference rule in `src/kb/reason.py`.

### Add a new domain

Mirror `src/ahab/` or `src/git_rag/`:

1. `<domain>/knowledge.py` — curated structured records.
2. `<domain>/query.py` — load + topic-match retrieval.

The query side is ~50 lines; the work is curating the corpus.

### Tweak the matcher's scoring

`src/git_rag/query.py:score_item` (~30 lines). Common tweaks: weight
distinctive tokens higher, add stemming, add bigram matching, add
fuzzy matching.

## Where AI is in the loop

| phase | AI involvement | cost |
|---|---|---|
| Extraction / curation | Yes — Claude API, or hand | one-shot |
| Persistence (JSON) | No | ms |
| Loading + indexing | No | ms per MB |
| Query | No | <1ms |
| Reasoning | No | seconds (fixpoint) |
| Rendering | No | <1ms |

The hand-curated facts in `src/kb/extract.py` and the curated corpora
in `src/ahab/utterances.py` and `src/git_rag/knowledge.py` are
stand-ins for production AI-driven extraction. They make the demos
runnable without an API key while illustrating the
construction-time-AI / runtime-no-AI split.

## Constraints

- Keyword-based matcher (not embedding-based). Add patterns to cover
  expected surface variation.
- KB JSON loads fully into memory. For >10M triples, switch to a
  SQLite index.
- Inference rules are Horn clauses only — no disjunction, no
  negation.
