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

- **Horn clause** — the basic shape of an inference rule here:
  `IF antecedents THEN consequent` where antecedents are existing
  triples and consequent is a new triple. The engine also supports
  declarative disjunction (`DisjunctiveRule` — alternative antecedent
  relations, one consequent) and stratified negation-as-failure
  (rules at stratum ≥ 1 that test absence via `kb_has`). What it
  does NOT do: full FOL theorem proving, description-logic
  subsumption, or unstratified negation.

- **Derivation** — a derived fact + the rule that derived it + the
  input triples it derived from + a human-readable
  "since...therefore..." explanation.

- **Fixpoint** — when no rule produces new facts on a fresh pass,
  the rule application has reached fixpoint. The engine iterates
  stratum-0 (monotonic Horn) rules until convergence, so a rule
  whose antecedents include another rule's consequent (e.g.,
  transitive closure of `INTELLECTUAL_DESCENDANT_OF`) keeps firing
  across rounds until the closure is complete.

- **Stratified negation** — negation-as-failure rules live in
  stratum 1 and run once after stratum-0 has converged. Stratified
  semantics keeps the result deterministic despite negation being
  non-monotonic; it's the standard discipline from stratified
  Datalog. Sound only under the closed-world assumption.

- **Disjunctive rule** — declarative shape where multiple
  alternative antecedent patterns map to one consequent. Lets a
  rule's structure stay inspectable (one named record with a
  relation list) instead of being hidden inside Python branches.

- **Interval** — a possibly-unbounded validity window on a triple,
  via the optional `valid_from` / `valid_to` slots. The engine
  intersects intervals when propagating temporal validity through
  derivations; the `src/kb/temporal.py` module also provides the
  full Allen algebra (13 atomic relations + composition table) for
  callers that need richer temporal reasoning.

- **Allen relation** — one of the 13 atomic relations from Allen's
  interval algebra (before, meets, overlaps, starts, during,
  finishes, equal, plus six converses). The standard formalism for
  reasoning about temporal intervals.

- **Confidence** — float in [0.0, 1.0] on each triple. Propagated
  through derivations via noisy-AND by default (configurable to
  min / noisy-OR / caller-supplied combiner). Semantic
  interpretation (probabilistic, fuzzy, Bayesian, partial-belief)
  is the caller's choice; the combinators are interpretation-
  neutral.

- **Conflict** — a set of triples that can't all be true under
  the active axioms. Surfaced by the OWL rule compiler via
  `CONFLICT_FUNCTIONAL`, `CONFLICT_INVERSE_FUNCTIONAL`, and
  `CONTRADICTION_DETECTED` markers.

- **Policy** — a strategy for resolving a conflict: which of the
  conflicting triples survives. Implementations include
  `LatestWinsPolicy`, `HighestConfidencePolicy`,
  `AuthorityWinsPolicy`, `KeepAllPolicy`, `SurfaceForReviewPolicy`,
  and `ChainPolicy` (try each in order until one narrows).

- **Ontology** — the declarative source of OWL-style axioms
  consumed by `src/kb/ontology_rules.py:compile_to_rules`. Captures
  classes, properties, hierarchy, characteristics (transitive,
  symmetric, functional, inverse-functional, inverse), equivalences,
  disjointness, and domain/range — the subset of OWL that maps to
  Horn + disjunctive + stratified-negation rules.

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

The extractor (in `src/kb/extract.py`) does:

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

On KB load (`src/kb/query.py:KB.load`):

1. Triples are read from JSON.
2. Adjacency indexes are built: `out_edges[subject]`,
   `in_edges[object]`, `by_relation[relation]`.

On reasoning (`src/kb/reason.py:apply_all_rules_to_fixpoint`):

1. Rules are grouped by `stratum`. Stratum 0 holds monotonic Horn
   rules (the default). Stratum 1+ holds rules that test absence
   via `kb_has` — negation-as-failure.
2. Within each stratum, rules iterate to fixpoint: each round runs
   every rule against the current KB; any new facts are folded in;
   iteration stops when no rule produces a new fact. A divergence
   guard raises `RuntimeError` if a stratum fails to converge in
   `max_iter` rounds.
3. Strata are processed in ascending order. A stratum-1 rule sees
   the converged stratum-0 closure but not its own peers'
   in-progress derivations — that's what makes the result
   deterministic despite negation being non-monotonic.
4. The extended KB is serialised to its own JSON file. Each
   derivation carries its rule name, input triples, and a
   "since X therefore Y" explanation for "why?" queries.

Three rule shapes are supported:

- **`Rule`** — wraps a Python function `KB → list[Derivation]`. The
  general form; can express any antecedent pattern including
  negation-as-failure when placed at stratum ≥ 1.
- **`DisjunctiveRule`** — declarative form for the
  "alternative-antecedent-relations" case (one consequent reachable
  via several relation names). Compiles to a `Rule`.
- Function-form disjunction over object values is expressed as a
  plain `Rule` whose body checks `t.object in {…}` — natural
  Python idiom, no extra abstraction needed.

Triple schema carries optional temporal and uncertainty slots:

- **`valid_from` / `valid_to`** — ISO-8601-ish date strings (or
  None for unbounded). The engine intersects input intervals when
  propagating validity through derivation chains. A derivation
  whose inputs are temporally inconsistent (empty intersection)
  is silently suppressed. See `src/kb/temporal.py` for the
  full Allen interval algebra (13 atomic relations + composition
  table) and the lenient `intersects` predicate.

- **`confidence`** — float in [0.0, 1.0], default 1.0. The engine
  combines input confidences via noisy-AND (product) when
  propagating through derivations. `src/kb/confidence.py` also
  exposes `min`, `noisy_or`, and a callable hook for caller-
  supplied combiners. Multiple semantic interpretations of the
  number (probabilistic, fuzzy, subjective-Bayesian, partial-
  belief) are equally well-supported; the combinators don't
  prescribe a reading.

OWL DSL and rule compiler:

- `src/kb/ontology.py` declares a small OWL-compatible ontology
  (classes, properties, sub-class / sub-property hierarchy,
  equivalent / disjoint classes, transitive / symmetric / inverse
  / functional / inverse-functional properties, domain / range).
- `src/kb/ontology_rules.py` compiles an ontology to standard
  `Rule` objects that plug into the same dispatcher as hand-written
  rules. The compiler is pure stdlib and closed-world (matching
  the engine's negation semantics).
- Functional / inverse-functional axioms emit `CONFLICT_*` marker
  facts when violated; the conflict module consumes them.
- `src/kb/ontology_owl.py` (soft-dep: `owlready2` + Java JVM) is
  the alternative backend for the same Ontology DSL — translates
  axioms + KB into OWL/RDF and runs a real description-logic
  reasoner (HermiT by default, Pellet alternative). Handles axioms
  the rule compiler can't express: cardinality restrictions,
  complex class expressions (intersection / union / complement /
  someValuesFrom / allValuesFrom), full DL classification, and
  inconsistency detection. Degrades cleanly when the soft
  dependencies are absent; runs at high stratum so the Horn /
  negation rules close first.

Conflict detection and resolution:

- `src/kb/conflict.py` reads `CONFLICT_*` and `CONTRADICTION_DETECTED`
  markers produced by the OWL rules and reconstructs the
  conflicting triples.
- Six policies decide which triple in a conflict survives:
  `LatestWinsPolicy`, `HighestConfidencePolicy`, `AuthorityWinsPolicy`,
  `KeepAllPolicy`, `SurfaceForReviewPolicy`, plus `ChainPolicy` for
  ordered fallback.
- `apply_with_conflict_resolution` orchestrates fixpoint inference
  + conflict detection + resolution into one pipeline that returns
  a clean resolved KB along with the conflicts found.

---

## Layer 3: serving (in detail)

Query types supported by `src/kb/query.py:KB`:

- `out_facts(entity, relation=None)` — all outgoing triples
- `in_facts(entity, relation=None)` — all incoming triples
- `neighbours(entity)` — set of all directly-connected entities
- `find_paths(start, end, max_hops, max_paths)` — BFS shortest paths
- `chain_query(start, [rel1, rel2, ...])` — follow a fixed sequence
  of relations

The conversational and RAG demos (`src/ahab/talk.py`,
`src/git_rag/query.py`) wrap the same KB-style retrieval with
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

## The combinatorial construction pattern

The deterministic extractor in `src/kb/extract.py` doesn't have to be
perfect — and intentionally isn't. Pattern-matching extractors always
miss things, and that's fine. The construction step is **combinatorial**:
imperfect automated extraction is combined with AI-driven curation,
and together they produce the artifact that ships.

The advantage: AI does the difficult, fuzzy work at construction
time, and the *output of that work* (a JSON KB or a structured
corpus) is what serves queries. No AI is needed at runtime.

Three places in this repo where the combinatorial pattern is
visible:

### `src/kb/extract.py` — automated extraction + curated patches

The bulk of facts comes from regex + entity-span + verb-anchor
matching. The known gaps are filled by a hand-curated `PATCH_FACTS`
list (`src/kb/extract.py:909`) — facts like *Einstein's wikilinked
birth date*, *the Plato ← Socrates tutoring relation*, *Aristotle's
canonical facts* — that the regex missed but which an AI-driven
review identified and supplied. In production this curation step is
done by a Claude API pass per article; here it ships as a static
list for the demo.

The combined output (automatic + patched) is `kb_1000_articles.json`.
No further AI involvement is needed to query or reason over it.

### `src/ahab/utterances.py` — fully AI-curated corpus

The 35 Captain Ahab utterances aren't extracted by any automated
extractor in this repo — they were curated directly (AI reading
Moby-Dick, identifying Ahab's lines, tagging them with chapter /
themes / addressee / mood / speech-act metadata). The shipped
artifact is the `AHAB_UTTERANCES` list (`src/ahab/utterances.py:32+`).

At runtime, `src/ahab/talk.py` matches user input themes against
the corpus and returns verbatim quotes with chapter citations —
zero AI calls.

### `src/git_rag/knowledge.py` — fully AI-curated corpus

The 37 Git knowledge items (topic, subtopic, intent,
question_patterns, commands, explanation, cautions, source,
related_items) were curated from the Git manual by AI reading the
documentation. The shipped artifact is the `GIT_KB` list
(`src/git_rag/knowledge.py:34+`).

At runtime, `src/git_rag/query.py` does intent + topic matching
against the corpus and returns the matched record — zero AI calls.

## Why this matters

The construction step can use whatever AI capability is available
(Claude API, GPT-4, hand-curation, a fine-tuned local model) without
locking the runtime into any of them. The artifact that ships is
plain JSON or plain Python data, queryable with stdlib only.

This is the **construction-time AI / runtime no-AI** split:

- **Construction**: one-shot, slow, expensive, AI-assisted. Quality
  is bounded by the AI's extraction capability. Errors at this
  stage are detectable and fixable (you can read the JSON).
- **Runtime**: per-query, fast, free, deterministic. Quality is
  bounded by what's in the artifact. The artifact never silently
  drifts.

Consequence: the imperfect extractor in `extract.py` is the right
shape — it doesn't need to be perfect because AI augments what it
misses at construction time, and the artifact that results is then
self-sufficient.

## Why the extractor's imperfection does not matter

Six reasons, each one sufficient on its own:

1. **What ships is the output, not the extractor.** Users of the
   system run `query.py` / `reason.py` / `talk.py` / `src/git_rag/query.py`
   against a prebuilt artifact. They never run the extractor. The
   extractor's quality matters only at construction time, in the
   developer's environment, where mistakes are reviewable.

2. **Errors are visible.** If the extractor misses a fact, you can
   open the JSON and see what's missing. If a fact is wrong, you can
   read it and verify against the source article. This is the
   opposite of LLM-as-KB, where errors are hidden in weights and
   only surface as occasional wrong answers under specific queries.

3. **Errors are localised.** A missed fact is one missing line in a
   JSON. A wrong fact is one wrong line. Fixing it doesn't affect
   anything else. With an LLM, "fixing" a wrong fact means
   re-training or retrieval-augmenting around it — global cost for
   a local problem.

4. **The marginal cost of fixing a gap is small.** Each missed fact
   is a one-line addition to `PATCH_FACTS` or to the curated corpus.
   Each new surface phrasing is one new verb-anchor in extract.py.
   No model re-training, no embedding re-indexing, no infrastructure
   change.

5. **The extractor is replaceable.** You can swap regex for
   dependency parsing, for a BERT-fine-tuned event extractor, for
   Claude API calls, for hand-curation, or any combination. The
   downstream code (`query.py`, `reason.py`, `talk.py`) doesn't
   change because the artifact format is what they consume —
   not the extractor.

6. **The system improves monotonically.** Add a patch fact: the KB
   knows one more thing. Add a verb anchor: the next extraction run
   catches more facts. Nothing regresses; old facts stay valid. An
   LLM you retrain might newly forget facts it previously knew.

The architectural bet is that bounded, fixable imperfection beats
unbounded, hidden imperfection. The extractor's coverage gaps are
visible and addressable; an LLM's coverage gaps are not.

## Why the system stays auditable, deterministic, and non-hallucinatory

The natural objection: *"If AI is involved in construction, how can
the runtime claim to be auditable, deterministic, and
hallucination-free?"*

The answer is that AI's involvement is bounded to construction time
and its output is a recordable artifact. That artifact is then
frozen and shipped, and every property below follows from the
artifact's nature plus the runtime mechanics — not from anything
about AI.

### Auditable — because the artifact is plain data

What ships is JSON for the KB demos and Python lists of dataclasses
for the conversational and RAG demos. You can open any of these in
a text editor and read every fact. There's no hidden state. There's
no compiled binary form of "what the model knows."

Per-fact provenance is encoded in the artifact itself:

- `Triple.source_article` and `Triple.source_sentence_idx` for every
  KB fact
- `Utterance.chapter` and `Utterance.chapter_title` for every
  Ahab utterance
- `KnowledgeItem.source` for every Git knowledge item
- `Derivation.rule_name` + `Derivation.inputs` + `Derivation.explanation`
  for every derived fact

If a served response is wrong, you can trace it to the exact
triple in the JSON, then to the exact source article + sentence,
then to the inference rule (if derived) and to the input triples
that fed the rule. Nothing is hidden in weights.

AI's *contribution* to the artifact is itself auditable:

- `PATCH_FACTS` in `src/kb/extract.py:909` is a list. You can read
  every patched fact in version control. If a patch is wrong, it's
  visible.
- The curated utterances in `src/ahab/utterances.py` are 35
  human-readable records.
- The curated knowledge items in `src/git_rag/knowledge.py` are 37
  human-readable records.

Each was authored by AI at construction time, but each is then a
plain-text record in the codebase. A reviewer can spot-check the
AI's work against the source material in seconds.

### Deterministic — because the runtime is pure data operations

Once the artifact is built, every runtime operation is one of:

- A dictionary lookup (`kb.out_edges["Aristotle"]`)
- A set intersection (`overlap = p_tokens & q_tokens`)
- A breadth-first graph traversal (`find_paths`)
- A scoring function summing fixed-weight contributions
- A `string.format()` call on a template with slot fillings

None of these involves sampling, randomness, temperature, or
beam search. Given the same artifact and the same query, you get
the same answer every time, byte-for-byte.

Horn-clause inference is deterministic by definition: given the
same facts and the same rules, the same derivations are produced
in the same order. The reasoning engine is a fixpoint iteration
over pure functions, not a stochastic search.

There is no place in the runtime where "the model might decide
differently this time" can happen. The runtime simply doesn't have
a model.

### Non-hallucinatory — because there is no generative step

For a system to hallucinate, it has to *generate text that wasn't
in its inputs*. This runtime has no such step:

- The retriever picks the highest-scoring record from a fixed list.
  It can pick the *wrong* record (if the matcher is poorly tuned),
  but it cannot return a record that doesn't exist.
- The renderer formats the picked record into a string by filling
  slots with values from the record. The values come from the
  record. The template is fixed code.
- The reasoning engine derives new facts by applying named rules
  to existing facts. It cannot derive facts whose ingredients
  aren't already present.

There is no autoregressive text generator. There is no "the model
synthesises an answer based on context." The output is *retrieved
data formatted by deterministic code*. The output cannot contain
claims that aren't in the artifact.

The strongest form of this argument: if a query returns no good
match, the system returns *"no results"*. It doesn't fabricate. An
LLM would generate plausible-sounding text whether the answer is
in the corpus or not; this system simply has no path to do that.

### Why AI involvement at construction time doesn't contaminate

The crucial structural point: AI's contribution at construction
time produces *recordable, inspectable, editable data*. That data
is then frozen.

```
construction time  →  AI generates candidate facts/records
                  →  human review (read the JSON, accept/reject)
                  →  artifact is FROZEN
                  →  ────────────────────
runtime          ←  artifact is consulted
                 ←  pure-code operations only
                 ←  no AI invocation
```

The horizontal line is the boundary. AI lives above it. Runtime
lives below it. Mistakes above the line are visible and fixable
because they're encoded as plain data. Below the line, there's no
AI to make mistakes.

Compare to an LLM-as-KB or LLM+RAG-with-synthesis system:

```
construction time  →  train the model
                  →  weights become the artifact (opaque)
                  →  ────────────────────
runtime          ←  query invokes the model
                 ←  stochastic generation
                 ←  may hallucinate
                 ←  no provenance
```

In an LLM system, AI's contribution at construction time is encoded
into weights you can't inspect, and AI is re-invoked at every
query. Errors are invisible at construction time and re-introduced
at every query. Neither auditability nor determinism nor
hallucination-resistance survives.

The architectural bet here is that *AI used to extract knowledge
into a consistent, structured, queryable format* combined with
*deterministic serving code* produces a system with all three
properties, while *AI used as the runtime* loses all three. AI's
value is the format conversion — unstructured source text becomes
a typed, provenance-tagged record set. The shipped artifact is
the result of that conversion; the runtime serves it.

### What's actually trusted in the running system

Trust in the running system reduces to trusting two things:

1. **The artifact** (the JSON KB, the curated corpora). Anyone can
   read it. Errors are visible in plain text.
2. **The runtime code** (~1,500 lines across `src/kb/`, `src/ahab/`,
   `src/git_rag/`). Anyone can read it. Bugs are testable.

No trust is required in:

- A model's weights
- The AI vendor's policies, uptime, or future API changes
- Training data the AI was exposed to that you can't see
- The model's "values" or alignment
- Stochastic sampling parameters

This is the practical case for using AI to extract, but not to run.
AI's role is to convert unstructured source text into a consistent,
queryable structured format — that converted format is what ships
and what the runtime serves.

---

## Extending to new domains

Three demos in this repo cover three source-text types:

| domain | source text | query/serve | structured reasoner |
|---|---|---|---|
| Encyclopedic | Wikipedia article dump | `src/kb/query.py` | `src/kb/reason.py` |
| Fictional / conversational | Moby-Dick (Ahab's quotes) | `src/ahab/talk.py` | `src/ahab/reason.py` |
| Software documentation | Git manual | `src/git_rag/query.py` | `src/git_rag/reason.py` |
| Knowledge distillation | multi-source noisy corpus | — | `src/distill/purify.py` |

The same reasoning engine drives all four reasoners — only the
projection from domain records into Triple form (and the choice of
ontology axioms) differs. `src/ahab/reason.py` derives theme
co-occurrence networks and classifies utterances. `src/git_rag/reason.py`
derives transitive topic-navigation and an automation-safety flag.
`src/distill/purify.py` runs the full purification sweep over a
deliberately-noisy multi-source corpus: detect conflicts, resolve via
a chain policy, corroborate multi-source agreement via noisy-OR, prune
below threshold, strip markers. All four reuse the engine in
`src/kb/reason.py` unchanged.

To add a new domain (e.g., medical guidelines, legal codes,
scientific literature):

1. Create a new subfolder.
2. Write a `knowledge.py` (or `utterances.py`) that defines the
   structured records for that domain. Fields typical to most
   domains: source, topic / theme, content, optional cautions /
   tags / metadata.
3. Write a query/serve script that does theme/topic matching and
   rendering with provenance.
4. *(Optional)* Write a `reason.py` that projects records into the
   Triple form, declares domain-specific rules (Horn /
   `DisjunctiveRule` / negation-as-failure), and calls
   `apply_all_rules_to_fixpoint`. See `src/ahab/reason.py` and
   `src/git_rag/reason.py` for working templates.

The architecture is domain-agnostic. Each domain just needs its own
corpus (or its own extractor + AI-extraction prompt) and optionally
its own rule set.
