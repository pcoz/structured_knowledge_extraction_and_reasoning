# Developer guide

> **See also**: [README](../README.md) ·
> [ARCHITECTURE](ARCHITECTURE.md) ·
> [USE_CASES](USE_CASES.md) ·
> [COMPARISONS](COMPARISONS.md) ·
> [NOVELTIES](NOVELTIES.md) ·
> [LICENSE](../LICENSE.md)

Practical reference for working with this codebase: code map, data
model, API quickref, recipes, performance notes, troubleshooting.

For the conceptual design see [ARCHITECTURE.md](ARCHITECTURE.md).
For where this sits relative to similar technology see
[COMPARISONS.md](COMPARISONS.md). For the prior-art positioning see
[NOVELTIES.md](NOVELTIES.md).

---

## Code map — what lives where

```
src/
├── wikipedia_utils.py    read Wikipedia XML, strip markup, split sentences
│
├── kb/                   the Wikipedia knowledge graph
│   ├── extract.py        regex + entity-span detection + curated patches
│   │                       → emits Triple records → serialises to JSON
│   │                     KEY CLASSES: Triple, KnowledgeGraph, VerbAnchor
│   │                     KEY FUNCS: extract_facts_from_article,
│   │                                find_entity_spans, resolve_pronouns
│   │
│   ├── query.py          load JSON KB; expose lookups + path + chain queries
│   │                     KEY CLASSES: KB, Triple
│   │                     KEY FUNCS: KB.load, KB.out_facts, KB.in_facts,
│   │                                KB.find_paths, KB.chain_query
│   │
│   ├── reason.py         Horn-clause inference; derive new facts with provenance
│   │                     KEY CLASSES: Derivation
│   │                     KEY FUNCS: apply_all_rules, individual r1..r7 rules
│   │
│   ├── kb_1000_articles.json           pre-built base KB (2,169 triples)
│   └── kb_1000_articles_extended.json  base + 3,469 derived facts
│
├── ahab/                 conversational demo over Moby-Dick
│   ├── utterances.py     35 curated Ahab quotes with metadata
│   │                     KEY CLASS: Utterance (text, chapter, themes,
│   │                                addressee, mood, speech_act)
│   │                     KEY DATA: AHAB_UTTERANCES list
│   │
│   └── talk.py           theme-extraction + scoring + rendering
│                         KEY FUNCS: extract_themes, score_utterance,
│                                    best_utterance, respond
│
└── git_rag/              enterprise RAG demo over Git docs
    ├── knowledge.py      37 structured Git knowledge items
    │                     KEY CLASS: KnowledgeItem (topic, subtopic,
    │                                intent, question_patterns,
    │                                commands, explanation, cautions,
    │                                source, related_items)
    │                     KEY DATA: GIT_KB list
    │
    └── query.py          intent + topic detection, scoring, rendering
                          KEY FUNCS: detect_intent, detect_topics,
                                     score_item, query, format_answer
```

---

## Data model

### Triple

The basic unit of the knowledge graph.

```python
@dataclass
class Triple:
    subject: str                    # e.g., "Aristotle"
    relation: str                   # e.g., "TUTORED_BY"
    object: str                     # e.g., "Plato"
    source_article: str             # e.g., "Aristotle"  (or "(derived)")
    source_sentence_idx: int        # 0-based index in the source article;
                                    # -1 for derived or curated facts
```

### KB JSON schema

```json
{
  "n_articles": 1000,
  "alias_map": {
    "Einstein": "Albert Einstein",
    "Albert": "Albert Einstein",
    "Plato": "Plato",
    ...
  },
  "triples": [
    {
      "subject": "Aristotle",
      "relation": "TUTORED_BY",
      "object": "Plato",
      "source_article": "Aristotle",
      "source_sentence_idx": 0
    },
    ...
  ]
}
```

The extended KB has the same schema; it just contains additional
triples (the derived facts) with `source_article` = `"(derived)"`
and `source_sentence_idx` = `-1`.

### Derivation (reasoning output)

```python
@dataclass
class Derivation:
    rule_name: str                  # e.g., "R1_intellectual_descent"
    output: Triple                  # the derived triple
    inputs: list[Triple]            # the antecedent triples
    explanation: str                # human-readable "since...therefore..."
```

### Utterance (conversational corpus)

```python
@dataclass
class Utterance:
    text: str                       # the verbatim quote
    chapter: int                    # source chapter number
    chapter_title: str
    themes: list[str]               # ["whale", "vengeance", ...]
    addressee: str                  # "crew", "Starbuck", "self", ...
    mood: str                       # "oratorical", "melancholy", ...
    speech_act: str                 # "oath", "monologue", "command", ...
```

### KnowledgeItem (RAG corpus)

```python
@dataclass
class KnowledgeItem:
    item_id: str                    # e.g., "commit.undo_last_unpushed"
    topic: str                      # e.g., "commit"
    subtopic: str                   # e.g., "undo"
    intent: str                     # "how-to" | "what-is" | "compare" | "why"
    question_patterns: list[str]    # paraphrases of typical user questions
    commands: list[str]             # shell commands to show in the answer
    explanation: str
    cautions: list[str]
    source: str                     # e.g., "git-scm.com/docs/git-reset"
    related_items: list[str]        # item_ids for follow-up navigation
```

---

## KB API quickref

```python
from kb.query import KB, Triple

kb = KB.load("src/kb/kb_1000_articles_extended.json")

# Entity-level
kb.entities()                              # set of all entity names
kb.canonicalize("Einstein")                # → "Albert Einstein"
kb.neighbours("Aristotle")                 # set of directly-connected entities

# Relation-level
kb.out_facts("Aristotle")                  # all outgoing triples
kb.out_facts("Aristotle", "TUTORED_BY")    # filtered by relation
kb.in_facts("Socrates")                    # all incoming triples
kb.in_facts("Socrates", "TUTORED_BY")      # who is tutored BY Socrates

# Multi-hop
kb.find_paths("Alexander the Great", "Socrates", max_hops=4)
# → list of paths; each path is a list of Triple records

kb.chain_query("Aristotle", ["TUTORED", "CONQUERED"])
# → [(end_entity, [Triple, Triple]), ...]

# Direct relation index
kb.by_relation["TUTORED_BY"]               # list of indices into kb.triples
```

`fmt_path(path)` pretty-prints a path:

```python
from kb.query import fmt_path
print(fmt_path(paths[0]))
# Alexander the Great <--TUTORED-- Aristotle --TUTORED_BY--> Plato
```

---

## Recipes

### Add a single fact

```python
import json

with open("src/kb/kb_1000_articles.json", "r", encoding="utf-8") as f:
    payload = json.load(f)

payload["triples"].append({
    "subject": "Marie Curie",
    "relation": "DISCOVERED",
    "object": "Radium",
    "source_article": "Marie Curie",
    "source_sentence_idx": -1
})

with open("src/kb/kb_1000_articles.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
```

Picked up on next `KB.load(...)`. No restart of anything needed.

### Add a new relation type via verb anchors

In `src/kb/extract.py`, append to `VERB_ANCHORS`:

```python
VerbAnchor(
    "INFLUENCED_BY",
    re.compile(r"\bwas\s+(?:strongly\s+)?influenced\s+by\b"),
    "forward",
),
```

The next time `extract.py` is run, sentences matching this anchor
emit `INFLUENCED_BY` triples. Existing query and reasoning code
needs no changes.

### Add a new inference rule

In `src/kb/reason.py`, define a function returning a list of
`Derivation`s, then register it:

```python
def r8_authored_in_genre(kb: KB) -> list[Derivation]:
    """X WROTE Y, Y IN_GENRE Z → X WROTE_IN_GENRE Z"""
    out = []
    for t1 in kb.triples:
        if t1.relation != "WROTE":
            continue
        for t2 in kb.out_facts(t1.object, "IN_GENRE"):
            derived = Triple(
                t1.subject, "WROTE_IN_GENRE", t2.object,
                "(derived)", -1,
            )
            expl = (
                f"Since {t1.subject} wrote {t1.object}, and {t1.object} "
                f"is in genre {t2.object}, therefore {t1.subject} wrote "
                f"in the {t2.object} genre."
            )
            out.append(Derivation("r8_authored_in_genre", derived,
                                   [t1, t2], expl))
    return out

RULES.append(("r8_authored_in_genre", r8_authored_in_genre))
```

The rule is picked up automatically on next `apply_all_rules(kb)`.

### Add a new conversational character (Ahab-style)

Make a new folder `src/<character>/` with:

1. `utterances.py` — a list of `Utterance` records.
2. `talk.py` — copy `src/ahab/talk.py` and adjust:
   - Change the import (`from utterances import ...`)
   - Update `THEME_KEYWORDS` and `QUESTION_TO_MOOD` for the new
     character's themes
   - Update `DEMO_QUESTIONS` if you want a scripted demo

### Add a new enterprise RAG domain

Make a new folder `src/<domain>_rag/` with:

1. `knowledge.py` — list of `KnowledgeItem` records.
2. `query.py` — copy `src/git_rag/query.py` and adjust:
   - `TOPIC_KEYWORDS` (which topics exist in the new domain)
   - `INTENT_PATTERNS` (if domain has different question shapes)
   - `DEMO_QUERIES` (sample queries for the demo)
   - `STOPWORDS` (domain-specific stopwords if any)

### Build a fresh KB from your own text corpus

```python
from wikipedia_utils import read_articles
from kb.extract import (
    extract_facts_from_article, KnowledgeGraph, PATCH_FACTS, Triple,
)
import json

# 1. Load articles
articles = read_articles(n=5000)   # set WIKIPEDIA_DUMP_PATH first

# 2. Extract
graph = KnowledgeGraph()
for title, raw in articles:
    for triple in extract_facts_from_article(title, raw):
        graph.add(triple)

# 3. Apply curated patches
for subj, rel, obj, src in PATCH_FACTS:
    graph.add(Triple(subj, rel, obj, src, -1))

# 4. Build alias map (optional — for canonicalisation)
alias_map = {}
for title, _ in articles:
    tokens = title.split()
    if len(tokens) >= 2:
        if tokens[-1] not in alias_map: alias_map[tokens[-1]] = title
        if tokens[0] not in alias_map: alias_map[tokens[0]] = title

# 5. Save
payload = {
    "n_articles": len(articles),
    "alias_map": alias_map,
    "triples": [
        {
            "subject": t.subject,
            "relation": t.relation,
            "object": t.object,
            "source_article": t.source_article,
            "source_sentence_idx": t.source_sentence_idx,
        }
        for t in graph.triples
    ],
}
with open("my_kb.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)
```

### Customise the RAG matcher's scoring

In `src/git_rag/query.py`, `score_item` is ~30 lines. Common tweaks:

```python
# Boost topic match
if item.topic in topics:
    score += 5.0    # was 3.0

# Penalise non-canonical phrasing
if item.intent != intent:
    score -= 1.0

# Reward token rarity (TF-IDF style)
for tok in overlap:
    score += 1.0 / (token_doc_freq.get(tok, 1))

# Add bigram match
q_bigrams = set(zip(q_tokens, q_tokens[1:]))
p_bigrams = set(zip(p_tokens, p_tokens[1:]))
score += 5.0 * len(q_bigrams & p_bigrams)
```

---

## Performance notes

- **KB load**: ~50 ms per MB of JSON. The 465 KB base KB loads in
  ~25 ms; the 1.1 MB extended KB in ~60 ms.
- **Query latency**: O(1) for entity lookups (dict access).
  O(out-degree) for `out_facts`/`in_facts`. O(k·b) for `find_paths`
  with k hops, average branching b.
- **Reasoning**: O(N²) worst case for pairwise rules (R7
  contemporary). For the 1000-article KB this is ~3,500 derivations
  in ~2 seconds.
- **Memory**: ~50 bytes per triple in-RAM after indexing. 1 M triples
  ≈ 50 MB.
- **Scale ceiling**: at ~10 M triples consider migrating from
  in-memory JSON to SQLite with B-tree indexes on (subject, relation)
  and (object, relation).

---

## Testing approach

There are no unit tests in this repo by design — the demos ARE the
test suite. Each demo script:

- Loads its corpus
- Runs a scripted set of queries
- Prints the results in a verifiable form (with provenance)

To verify behaviour after a change:

```bash
python src/kb/query.py                 # entity cards + multi-hop chains
python src/kb/reason.py                # rule derivations + compound queries
python src/ahab/talk.py                # 13 Q&A turns; chapter citations
python src/git_rag/query.py            # 15 Git Q&A; manual-section sources
```

Each output is human-inspectable. If a Q gets the wrong A, the bug
is visible in seconds.

For automated regression: pipe the demos' output to files and diff
against a known-good baseline.

---

## Troubleshooting

**`KB file not found: kb_1000_articles.json`**
The query/reason scripts look for the JSON next to themselves. Either
run them from the project root (paths resolve relative to the file)
or pass an absolute path to `KB.load(...)`.

**`FileNotFoundError: Wikipedia dump not found at ...`**
`src/kb/extract.py` needs a Wikipedia XML dump. Set
`WIKIPEDIA_DUMP_PATH` env var or place a dump file at
`./data/wikipedia_dump.xml`. You don't need this to run the
pre-built query/reason/ahab/git_rag demos — they ship with the KB.

**No matches for an obvious question**
The matcher is keyword-based. Either:
- Add the user's phrasing to the relevant
  `question_patterns` / theme keyword list
- Add a stemming step (the git_rag matcher has a `_stem` helper as
  an example)
- Lower the scoring threshold

**An "entity" comes out wrong (e.g., "Aristotle Greek")**
The entity-span extractor over-extended. Add the offending word to
`ADJECTIVE_STOPWORDS` in `src/kb/extract.py`. Re-run extraction.

**A derivation rule fires spuriously**
Each rule is a Python function in `src/kb/reason.py`. Tighten its
predicate (e.g., add type checks on subject/object) and re-run.

**Pronoun resolution mis-attributes a fact**
The article-subject bias in `extract.py` aggressively substitutes
pronouns with the article title. For sentences where the actual
subject is different (e.g., "Plato wrote about..." in Aristotle's
article), this can mis-attribute. Mitigation: pre-filter sentences,
or add explicit "exception" patterns.

---

## Style and conventions

- **No comments that just restate the code.** Comments explain the
  why or a non-obvious constraint.
- **Module docstrings are 1-3 lines.** Detailed design goes in
  `docs/`.
- **Use `dataclass` for record types** (Triple, Utterance,
  KnowledgeItem, Derivation). They serialise cleanly to JSON.
- **No external dependencies** beyond the Python standard library.
  Keeps the project portable and edge-deployable.
- **Imports**: each entry-point script adds the project's `src/`
  directory to `sys.path` so sibling-folder imports work when run
  directly (e.g., `python src/ahab/talk.py`).
