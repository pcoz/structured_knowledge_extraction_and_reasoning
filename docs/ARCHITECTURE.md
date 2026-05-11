# Architecture

> **See also**: [README](../README.md) ·
> [DEVELOPER_GUIDE](DEVELOPER_GUIDE.md) ·
> [USE_CASES](USE_CASES.md) ·
> [COMPARISONS](COMPARISONS.md) ·
> [NOVELTIES](NOVELTIES.md) ·
> [LICENSE](../LICENSE.md)

A pipeline that takes unstructured text in and produces a queryable,
inspectable, deductively reasonable, hallucination-free knowledge
graph.

## The three layers

```
   ┌─────────────────────────────────────────────────────────┐
   │  source text                                             │
   │  (Wikipedia article, novel chapter, manual page, ...)    │
   └────────────────────────┬────────────────────────────────┘
                            │
                            │ LAYER 1: EXTRACTION
                            │   • parse / strip markup
                            │   • detect entity spans
                            │   • match verb anchors
                            │   • resolve pronouns to article subject
                            │   • optional: AI-driven extraction
                            │     (Claude API per article) for high recall
                            │
   ┌────────────────────────▼────────────────────────────────┐
   │  structured triples                                      │
   │    (subject, relation, object, source_article,           │
   │     source_sentence_idx)                                 │
   │                                                          │
   │  persisted as JSON                                       │
   └────────────────────────┬────────────────────────────────┘
                            │
                            │ LAYER 2: INDEXING + INFERENCE
                            │   • adjacency indexes (out-edges,
                            │     in-edges, by-relation)
                            │   • alias map (Einstein ↔ Albert Einstein)
                            │   • inference rules (Horn clauses) derive
                            │     new triples; each derivation carries
                            │     its rule + inputs + explanation
                            │
   ┌────────────────────────▼────────────────────────────────┐
   │  populated knowledge graph                               │
   │    base facts + derived facts                            │
   │    persisted as JSON                                     │
   └────────────────────────┬────────────────────────────────┘
                            │
                            │ LAYER 3: SERVING
                            │   • entity-card lookups
                            │   • path queries (BFS)
                            │   • chain queries (sequence of relations)
                            │   • filter queries (by relation, by date, ...)
                            │   • "why?" queries (replay derivation chain)
                            │   • theme-matched retrieval for
                            │     conversational / RAG responses
                            │
   ┌────────────────────────▼────────────────────────────────┐
   │  grounded responses                                      │
   │    every claim traceable to source article + sentence    │
   │    no LLM in the loop at serve time                      │
   └─────────────────────────────────────────────────────────┘
```

Construction (layers 1+2): one-shot, AI-assisted, runs in
seconds-to-hours depending on corpus size.

Serving (layer 3): deterministic, sub-millisecond per query, no API
calls. The KB JSON is the only artifact that needs to be deployed.

---

## Why this works

Three properties not shared by other architectures:

1. **Bidirectional structure ↔ text mapping.** The extraction step is
   invertible: given a structured triple + the cell-grammar template
   it was extracted from, the surface text can be reconstructed.
2. **Per-fact provenance.** Every triple carries the source article
   and sentence index. Every derived fact carries the inference rule
   and the input triples that produced it. There is no "the model
   said so" claim anywhere.
3. **No LLM at serve time.** All queries are graph operations on the
   persisted JSON. Sub-ms latency, no API costs, no vendor lock-in,
   no hallucination — the response is a retrieved record, not a
   generated string.

---

## Terms used in this project (glossary)

Some of these terms come from a metaphor the broader project uses
(porphyritic rock — sentences are like rock fragments with different
internal structure). Others are standard linguistics / KG terms used
here in specific ways. Definitions:

### From the porphyritic-rock metaphor

- **Phenocryst** — a sentence that matches a template cleanly.
  Named after the large recognisable crystals in porphyritic rock.
  Example: *"Aristotle was tutored by Plato"* matches a known
  `TUTORED_BY` template; the extraction is high-confidence.

- **Groundmass** — the fine-grained connecting prose around the
  phenocrysts. Sentences that don't fit any template cleanly; they
  carry style and discourse-level information but not crisp facts.
  Example: *"Their philosophical disagreements would later inform
  much of Western thought"* — narrative, not template-shaped.

- **Xenolith** — foreign content embedded in text. Verbatim quotes,
  citations, markup blocks, original-language transliterations. Named
  after the foreign rock fragments occasionally embedded in
  porphyritic host rock. Example: *"Plutarch wrote (Alexander 3.1,3)
  that..."* — the parenthetical citation is a xenolith.

### Cell-grammar terms

- **Cell** — a slot in a sentence's predicate-argument frame.
  Common cells: `LOCATION`, `TEMPORAL`, `ACTOR`, `VERB`, `PATIENT`,
  `CONSEQUENCE`.

- **Shape** — the sequence of cells that makes up a frame.
  Example: `[ACTOR][VERB][PATIENT]` is the "actor-verb-patient"
  shape; battle-event sentences use a longer shape with
  `[LOCATION][TEMPORAL]` prefix and `[CONSEQUENCE]` suffix.

- **Context** — the broad domain. Example: `military_historic`,
  `biographical`, `scientific_concept`. Context selects which phrase
  library to use within each cell.

- **Flavour** — sub-context conditioning. Within `biographical`,
  flavours like `biographical.ancient_philosopher` (Aristotle's
  prose) and `biographical.scientific` (Einstein's prose) have
  different phrase distributions. Detected once per article and
  used to route phrase-library selection.

- **Interaction type** — a semantic event class abstracted from
  surface phrasings. `BORN`, `DIED`, `TUTORED`, `MARRIED`,
  `CONQUERED`, `FOUNDED`, `WROTE`, `DEFEATED`, etc. Each interaction
  type maps to a (shape, context) pair with a canonical phrase
  signature.

- **Phrase** — a specific surface realisation of a cell.
  Example: under `VERB` cell with `military_historic` context, the
  phrases include "defeated", "decisively defeated", "captured",
  "accepted the surrender of", "to victory at", etc.

- **Slot** — a typed gap in a cell-phrase that's filled with an
  entity reference. Example: in `at the Battle of {place}`, `{place}`
  is a slot of type `Place.Battle`.

### Knowledge-graph terms

- **Triple** — a single fact `(subject, relation, object)` plus
  provenance metadata.

- **Entity** — anything that can be a subject or object in a triple.
  People (`Aristotle`), places (`Macedon`), abstract concepts
  (`philosophy`), works (`Nicomachean Ethics`), etc.

- **Relation** — a typed link between two entities. Examples:
  `TUTORED_BY`, `BORN_IN`, `CONQUERED`, `WROTE`, `INTELLECTUAL_DESCENDANT_OF`.

- **Provenance** — for base facts: `source_article` +
  `source_sentence_idx`. For derived facts: the rule name + input
  triples that produced the fact. Used in "why?" queries.

- **Alias map** — a dictionary of entity name variants mapped to
  their canonical form. Example: `{"Einstein": "Albert Einstein",
  "Albert": "Albert Einstein"}`. Applied at triple-creation time so
  graph nodes don't fragment across name variants.

- **Adjacency index** — out-edges + in-edges + by-relation lookup
  tables built when the KB is loaded. Enables O(1) neighbour lookups
  and fast BFS traversal.

### Inference / reasoning terms

- **Horn clause** — the form of inference rule used here. `IF
  antecedents THEN consequent` where antecedents are existing
  triples and consequent is a new triple. The reasoning engine
  doesn't currently handle disjunction or negation; Horn-only.

- **Derivation** — a derived fact + the rule that derived it + the
  input triples it derived from + a human-readable
  "since...therefore..." explanation.

- **Fixpoint** — when no rule produces new facts on a fresh pass,
  the rule application has reached fixpoint. The current engine
  runs a single pass plus one re-application to catch
  derived-on-derived chains.

### Construction / serving terms

- **Construction time** — when the KB is built. AI is involved
  here (extraction, optional curation). One-shot, slow,
  comparatively expensive.

- **Runtime / serve time** — when queries are answered. No AI
  involved. Sub-ms, deterministic, cheap.

- **AI-cheating** — the architectural principle that AI is fine
  to use at construction time provided the resulting artifact is
  self-contained and AI-free at runtime. Distinguishes this from
  "LLM + tools at runtime" architectures.

- **Theme** — a tag used for matching user queries against
  conversational utterances or RAG knowledge items. Example:
  Ahab's utterances are tagged with themes like `whale`,
  `vengeance`, `fate`, `weariness`, `madness`.

- **Speech act** — for conversational corpora: the rhetorical
  type of an utterance (`oath`, `command`, `monologue`,
  `declaration`, `prayer`).

- **Cell-phrase library** — the dictionary of phrases per (cell,
  context, flavour). Adding a new surface phrasing of an existing
  interaction type is a phrase-library entry, not a new template.

---

## Layer 1: extraction (in detail)

The extractor (in `kb/extract.py`) does:

1. **Markup stripping** (`wikipedia_utils.strip_markup`): converts
   raw XML article body to clean prose.
2. **Sentence splitting** (`wikipedia_utils.split_sentences`):
   yields one sentence at a time.
3. **Entity-span detection**: tokenize sentence; find maximal runs
   of capitalised words (with connectors like "the", "of", "von");
   truncate at adjective-stopwords ("Greek", "Roman", etc. don't
   extend names).
4. **Pronoun resolution**: when the sentence's subject is a pronoun
   ("he", "she", "who"), substitute the article title.
5. **Verb-anchor matching**: for each verb anchor pattern (e.g.,
   `\bwas tutored by\b`), find matches in the sentence. Look for
   entity spans to the left (subject) and right (object) of the
   anchor.
6. **Article-subject bias**: if the article's title (or first name)
   appears in the sentence, prefer it as the subject. Catches
   multi-clause sentences where "he/she" is implicit between
   clauses.
7. **Lifespan parenthetical detection**: separately, look for "Name
   (... YYY BC – ZZZ BC ...)" patterns and emit BORN_DATE +
   DIED_DATE triples.
8. **Curated patches**: hand-added or AI-extracted facts for gaps
   in the regex coverage. Same JSON output format.
9. **Canonicalisation**: at the end of extraction, every triple's
   subject and object are mapped through the alias map.

Output: a list of `Triple` records, serialised to JSON.

---

## Layer 2: indexing + inference (in detail)

On KB load (`kb/query.py:KB.load`):

1. Triples are read from JSON.
2. Adjacency indexes are built: `out_edges[subject]`,
   `in_edges[object]`, `by_relation[relation]`.

On reasoning (`kb/reason.py:apply_all_rules`):

1. Each rule iterates over the KB's triples (or specific relation
   subsets) and emits `Derivation` objects.
2. New derivations are added to the KB; transitive rules can fire
   on derived facts in a second pass.
3. The extended KB is serialised to its own JSON file.

---

## Layer 3: serving (in detail)

Query types supported by `kb/query.py:KB`:

- `out_facts(entity, relation=None)` — all outgoing triples
- `in_facts(entity, relation=None)` — all incoming triples
- `neighbours(entity)` — set of all directly-connected entities
- `find_paths(start, end, max_hops, max_paths)` — BFS shortest paths
- `chain_query(start, [rel1, rel2, ...])` — follow a fixed sequence
  of relations

The conversational and RAG demos (`ahab/talk.py`,
`git_rag/query.py`) wrap the same KB-style retrieval with
theme/intent matching:

1. Extract themes/topics/intent from user input
2. Score each item in the corpus by topic match + phrase overlap
   + intent match + freshness (avoid recent repeats)
3. Return the top-scoring item, rendered with provenance

---

## Where AI is in the loop

| phase | AI involvement |
|---|---|
| Layer 1 extraction | YES — Claude API per article, or hand-curation |
| Layer 1 markup stripping / regex matching | no — pure code |
| Layer 2 indexing | no — pure code |
| Layer 2 inference rule application | no — pure code |
| Layer 3 query | no — pure code |
| Layer 3 rendering | no — pure code |

The hard-coded extraction patterns in `kb/extract.py` plus the
curated `PATCH_FACTS` are stand-ins for the production AI-driven
extraction pipeline. They make the demos runnable without an API
key while still illustrating the architecture.

---

## Extending to new domains

Three demos in this repo cover three source-text types:

| domain | source text | demo |
|---|---|---|
| Encyclopedic | Wikipedia article dump | `kb/` |
| Fictional / conversational | Moby-Dick (Ahab's quotes) | `ahab/` |
| Software documentation | Git manual | `git_rag/` |

To add a new domain (e.g., medical guidelines, legal codes,
scientific literature):

1. Create a new subfolder.
2. Write a `knowledge.py` (or `utterances.py`) that defines the
   structured records for that domain. Fields typical to most
   domains: source, topic / theme, content, optional cautions /
   tags / metadata.
3. Write a query/serve script that does theme/topic matching and
   rendering with provenance.

The architecture is domain-agnostic. Each domain just needs its own
corpus (or its own extractor + AI-extraction prompt).
