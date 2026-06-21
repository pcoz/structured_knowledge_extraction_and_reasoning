# SKEAR — Developer guide

> **See also**: [README](../README.md) ·
> [ARCHITECTURE](ARCHITECTURE.md) ·
> [USE_CASES](USE_CASES.md) ·
> [COMPARISONS](COMPARISONS.md) ·
> [NOVELTIES](NOVELTIES.md) ·
> [ORDERED_MICROTHEORIES](ORDERED_MICROTHEORIES.md) ·
> [LICENSE](../LICENSE.md)

Practical reference for working with the SKEAR codebase: code map,
data model, API quickref, recipes, performance notes, troubleshooting.

For the conceptual design see [ARCHITECTURE.md](ARCHITECTURE.md).
For where this sits relative to similar technology see
[COMPARISONS.md](COMPARISONS.md). For the prior-art positioning see
[NOVELTIES.md](NOVELTIES.md).

---

## First time? Try this

The fastest way to see SKEAR working is to run the demos and read
the output. They ship with their corpora; no setup beyond Python 3.

```bash
python src/kb/query.py        # Wikipedia knowledge graph queries
python src/ahab/talk.py       # 13-question conversation with Captain Ahab
python src/git_rag/query.py   # 15 Git documentation Q&A pairs
python src/kb/reason.py       # rule-based inference + 10 stress tests
```

Each prints human-inspectable output with provenance attached. The
first three take a few seconds; the fourth runs the full reasoning
suite over ~2,000 base facts.

When you want to read code, the natural entry points are:

- **`src/kb/query.py`** — `KB.load()`, `KB.out_facts()`,
  `KB.find_paths()`. The core query API; everything else builds on it.
- **`src/kb/reason.py`** — `apply_all_rules_to_fixpoint`. The rule
  engine. ~700 lines; the most important file in the codebase.
- **`src/ahab/reason.py`** — a worked example of applying the engine
  to a new domain. The cleanest reference if you're building your
  own reasoner.

If you have a specific goal in mind, jump to the matching recipe in
the [Recipes](#recipes) section below.

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
│   ├── reason.py         Inference engine: fixpoint over Horn rules,
│   │                     declarative disjunctive rules, stratified
│   │                     negation-as-failure. Bundled stress-test suite
│   │                     (10 scenarios).
│   │                     KEY CLASSES: Rule, DisjunctiveRule, Derivation
│   │                     KEY FUNCS: apply_all_rules_to_fixpoint
│   │                                (propagate_confidence/temporal flags),
│   │                                kb_has, stress_test,
│   │                                individual r1..r11 rules
│   │
│   ├── execute.py        Executor faculty: run an ORDERED microtheory as a
│   │                     program (closed opcode set incl. CALL/EMIT/FETCH;
│   │                     FETCH takes a literal `subject|relation` OR a
│   │                     parametric `@var|relation` that resolves the subject
│   │                     from a frame variable — one rule over any entity;
│   │                     compile-once cache; termination + recursion guards).
│   │                     KEY CLASSES: ExecResult, ExecError
│   │                     KEY FUNCS: run, validate, OPCODES
│   │                     See docs/ORDERED_MICROTHEORIES.md.
│   │
│   ├── transpile.py      Compile an ordered-microtheory program to native
│   │                     Python (basic-block + SSA codegen) for ~native
│   │                     speed; interpreter fallback for the unsupported
│   │                     subset. The triples stay canonical; the Python is
│   │                     a derived, inspectable cache.
│   │                     KEY FUNCS: run_compiled, compile_program,
│   │                                to_python_source
│   │
│   ├── temporal.py       Interval algebra. The full 13-relation Allen
│   │                     calculus + composition table, plus the
│   │                     permissive `intersects` and interval
│   │                     intersection used by the engine to propagate
│   │                     validity through derivation chains.
│   │                     KEY CLASSES: Interval
│   │                     KEY FUNCS: intersects (permissive, incl. "meets"),
│   │                                strictly_overlaps (positive-duration,
│   │                                used by conflict detection), intersection,
│   │                                intersection_of_inputs, valid_at,
│   │                                before/after/meets/overlaps/...,
│   │                                compose, invert
│   │
│   ├── confidence.py     Uncertainty combinators. noisy-AND (default),
│   │                     min, noisy-OR, plus a callable hook for
│   │                     custom combiners. Interpretation-neutral —
│   │                     probabilistic, fuzzy, or subjective-Bayesian
│   │                     readings all use the same combinators.
│   │                     KEY FUNCS: noisy_and, noisy_or, min_confidence,
│   │                                derive_confidence, merge_confidence,
│   │                                drop_below
│   │
│   ├── ontology.py       Declarative OWL-style ontology DSL. A small
│   │                     dataclass for classes, properties, subClass /
│   │                     subProperty, equivalent / disjoint classes,
│   │                     transitive / symmetric / inverse / functional
│   │                     / inverse-functional properties, domain / range.
│   │                     Bundled stress-test suite (11 scenarios).
│   │                     KEY CLASSES: Ontology
│   │
│   ├── ontology_rules.py Compile an Ontology into Rule objects that the
│   │                     existing engine runs. Pure stdlib; closed-
│   │                     world. Functional / inverse-functional rules
│   │                     emit CONFLICT_* markers consumed by conflict.py.
│   │                     KEY FUNCS: compile_to_rules
│   │
│   ├── ontology_owl.py   HermiT (and Pellet) integration via owlready2.
│   │                     Construction-time enricher: translates our
│   │                     Ontology + KB to OWL/RDF, runs a real DL
│   │                     reasoner, converts inferences back into
│   │                     Triple / Derivation shape. Soft dependencies
│   │                     (owlready2 + Java JVM); adapter degrades
│   │                     cleanly with actionable messages if missing.
│   │                     Brings full DL: cardinality, complex class
│   │                     expressions (intersection / union /
│   │                     complement / someValuesFrom / allValuesFrom),
│   │                     inconsistency detection. Bundled 7-scenario
│   │                     stress-test suite.
│   │                     KEY FUNCS: hermit_enrich, hermit_rule
│   │
│   ├── conflict.py       Conflict detection (over CONFLICT_* markers)
│   │                     and resolution policies. Stress-test suite
│   │                     (11 scenarios) covering temporal overlap,
│   │                     authority-ranked sources, confidence-based
│   │                     resolution, and disjoint-class contradictions.
│   │                     KEY CLASSES: Conflict, Policy (LatestWins,
│   │                                  HighestConfidence, AuthorityWins,
│   │                                  KeepAll, SurfaceForReview,
│   │                                  ChainPolicy)
│   │                     KEY FUNCS: detect_conflicts, resolve_conflicts,
│   │                                apply_with_conflict_resolution
│   │
│   ├── kb_1000_articles.json           pre-built base KB (2,169 triples)
│   └── kb_1000_articles_extended.json  base + derived facts
│
├── ahab/                 conversational demo over Moby-Dick
│   ├── utterances.py     35 curated Ahab quotes with metadata
│   │                     KEY CLASS: Utterance (text, chapter, themes,
│   │                                addressee, mood, speech_act)
│   │                     KEY DATA: AHAB_UTTERANCES list
│   │
│   ├── talk.py           theme-extraction + scoring + rendering
│   │                     KEY FUNCS: extract_themes, score_utterance,
│   │                                best_utterance, respond
│   │
│   └── reason.py         apply the kb.reason engine to the utterance
│                         corpus: theme co-occurrence + transitive
│                         closure, disjunctive speech-label,
│                         confrontational/introspective classification,
│                         peaceful-addressee (negation over derived)
│
├── git_rag/              enterprise RAG demo over Git docs
│   ├── knowledge.py      37 structured Git knowledge items
│   │                     KEY CLASS: KnowledgeItem (topic, subtopic,
│   │                                intent, question_patterns,
│   │                                commands, explanation, cautions,
│   │                                source, related_items)
│   │                     KEY DATA: GIT_KB list
│   │
│   ├── query.py          intent + topic detection, scoring, rendering
│   │                     KEY FUNCS: detect_intent, detect_topics,
│   │                                score_item, query, format_answer
│   │
│   └── reason.py         apply the kb.reason engine to the Git docs:
│                         transitive RELATED_TO closure (via OWL),
│                         NEEDS_OPERATOR_ATTENTION (disjunctive over
│                         HAS_CAUTION ∪ USES_DESTRUCTIVE_COMMAND),
│                         SAFE_TO_AUTOMATE (negation over derived)
│
├── distill/              knowledge distillation / purification demo
│   ├── corpus.py         deliberately-noisy multi-source astronomical
│   │                     corpus exhibiting all four pathologies:
│   │                     corroboration, functional-property conflicts,
│   │                     outdated estimates, low-authority noise.
│   │                     ~65 facts from 7 sources of varying authority.
│   │                     KEY DATA: _RAW_FACTS, SOURCE_AUTHORITY
│   │
│   └── purify.py         the purification pipeline: OWL conflict
│                         detection → chain-policy resolution →
│                         multi-source corroboration boost (noisy-OR) →
│                         confidence-threshold pruning → marker cleanup.
│                         Bundled stress-test suite (6 scenarios).
│                         KEY FUNCS: purify, corroborate, prune_below
│
├── diachronic/           changing-patterns-of-thinking demo
    ├── corpus.py         the same subject (the atom) across six
    │                     historical eras — Greek atomism, Aristotelian
    │                     rejection, Newtonian, Daltonian, Rutherford/
    │                     Bohr, quantum. ~60 facts with temporal slots
    │                     and per-era source authority. Demonstrates
    │                     schema-as-data: the IS_A classification of
    │                     "atom" changes structurally across eras, not
    │                     just its properties.
    │                     KEY DATA: _RAW_FACTS, ERA_BOUNDARIES
    │
    └── analyse.py        diachronic analyzer: per-era snapshots,
                          schema-drift detection, property-reversal
                          tracking (e.g., "indivisible" affirmed for
                          2,000 years then rejected post-Rutherford),
                          vocabulary-drift measurement. Embeds prose
                          on why this matters for knowledge representation
                          and why LLMs struggle with the historical
                          structure. Bundled stress-test suite
                          (5 scenarios).
                          KEY FUNCS: main, _stress_test
│
└── microtheory/          non-temporal framing-scope demo (the scope
    │                     axis is a school of thought / framing, not an
    │                     era — the non-temporal counterpart of diachronic)
    ├── corpus.py         one recession under four incompatible schools
    │                     of economics (Keynesian / Austrian / monetarist
    │                     / MMT), each a Triple.scope microtheory.
    ├── analyse.py        reads each microtheory (KB.in_scope), shows the
    │                     four framings coexist without contradiction, and
    │                     that a within-school contradiction is still caught.
    ├── breakage.py       how OVERLAPPING microtheories break a body of
    │                     knowledge (globalised fact / merged contexts),
    │                     and how re-scoping repairs it.
    ├── test_scope.py     unit test for Triple.scope + Triple.seq semantics
    │                     + backward compatibility (ordered microtheories).
    ├── procedure.py      an ORDERED microtheory is a procedure: read in
    │                     seq order; procedures-as-framings (diff + scope-
    │                     aware conflict); precedence closure + cycle
    │                     detection via the real fixpoint reasoner.
    ├── program.py        an ordered microtheory as a SUBSTITUTE FOR CODE:
    │                     opcodes as steps, run by the core executor;
    │                     edit-behaviour-as-data; unknown opcode refused.
    ├── replicate.py      replicate real Python (Euclid GCD loop; branch
    │                     ladder) EXACTLY, and measure the honest
    │                     efficiency gain on a family of N rules.
    ├── showcase.py       the expanded opcodes: mutual recursion, recursion
    │                     (fib), composition (lcm CALLs gcd), and EMIT
    │                     (FizzBuzz, primes) — each matched to Python.
    ├── unified.py        no disconnect: a program FETCHes the KB's own
    │                     facts, its result re-enters as a fact (one store).
    ├── parametric.py     one rule, every entity: FETCH @var|relation reads
    │                     the subject from an input; the same program serves a
    │                     population, each answer cited to the resolved entity;
    │                     the FETCH surface is declarable in advance as data.
    ├── complexity.py     a polynomial speedup (O(M^2)->O(M)) on a 2-hop
    │                     join, from the KB's intrinsic index.
    ├── paradigm.py       capstone: facts, a rule, and programs in one KB —
    │                     query + reason + execute, provenance unbroken.
    └── fraud.py          applied capstone: fraud detection — query txns, a
                          data-defined risk score (FETCHes policy), and a
                          reasoned shared-device ring; every flag cited.
│
└── ingestion/           import-consistency demo: importing self-
    │                     contradictory data and locating the source's
    │                     own inconsistency (incl. a LATENT contradiction
    │                     that only appears in the logical closure).
    ├── corpus.py         four vendor/CMMS/audit exports for one asset,
    │                     with direct + derived contradictions, plus the
    │                     engineering taxonomy that makes the latent one fire.
    └── analyse.py        import audit: surfaces each contradiction with the
                          source sentences that produced it; shows the
                          difficulty (resolve-with-data-loss vs surface-for-
                          review) and why scoping would be the wrong fix.
```

---

## Data model

### Triple

The basic unit of the knowledge graph.

```python
@dataclass
class Triple:
    # Core schema — present since v1; all required.
    subject: str                    # e.g., "Aristotle"
    relation: str                   # e.g., "TUTORED_BY"
    object: str                     # e.g., "Plato"
    source_article: str             # e.g., "Aristotle"  (or "(derived)")
    source_sentence_idx: int        # 0-based index in the source article;
                                    # -1 for derived or curated facts

    # Schema extensions — optional, with defaults matching v1 semantics.
    valid_from: str | None = None   # ISO date; None = -infinity
    valid_to:   str | None = None   # ISO date; None = +infinity
    confidence: float = 1.0         # [0.0, 1.0]; default = certain
    scope:      str | None = None   # microtheory/framing; None = global
    seq:        int | None = None   # position in an ORDERED microtheory;
                                    # None = unordered set member (v1)
```

`scope` is a flat microtheory tag: `None` means the fact is global
(holds in every context — the v1 default), a non-None value confines it
to that named context (a legal framing, a standards interpretation, a
school of thought). Conflict detection is scope-aware — two functional
values in *different* non-global scopes don't conflict (different
microtheories), while global facts can conflict with anything. Query a
single microtheory with `KB.in_scope(scope)` (returns its facts plus the
global ones) and list the present microtheories with `KB.scopes()`. See
`src/microtheory/` for a worked example.

`seq` makes a microtheory **ordered** — a *sequence* instead of a set.
`None` (the default) preserves the v1 set semantics; a non-None `seq`
gives a fact its position in the scope's sequence. Read a procedure out
in order with `KB.in_scope(scope, ordered=True)` (seq-tagged members
ascend by `seq`, untagged/globals follow) or `KB.ordered_scope(scope)`
(the scope's own steps only, in order). This is how a procedure — recipe,
runbook, protocol, algorithm — is one microtheory whose members have an
intrinsic order. When the members are opcodes, the ordered microtheory is
an executable program: run it with the core executor —

```python
from kb.execute import run
result = run(kb, scope="my_program", inputs={"x": 10})
print(result.value, result.steps)   # value + a cited per-step trace
```

The executor (`kb.execute`) is a stack VM with a CLOSED opcode set
(PUSH/LOAD/STORE, arithmetic, comparison, JMP/JZ, RET), a step budget
that guarantees termination, and a refusal for any unknown opcode (no
`eval`, no host access). See `src/microtheory/{procedure,program,
replicate}.py` for worked examples, including exact replication of real
Python and the efficiency analysis.

Old JSON files (without the new fields) load unchanged via
`KB.load`, which filters unknown keys and applies defaults for
missing ones.

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

### Configure irreflexive relations for your corpus

Extraction rejects self-referential triples on **irreflexive** relations
— a thing cannot `WROTE` / `FOUNDED` / `TUTORED` / `DEFEAT` *itself*; such
a triple is a span-merge artefact, not knowledge. This set is **not
hardcoded to Wikipedia**. It is a parameter that defaults to
`DEFAULT_ASYMMETRIC_RELATIONS` and is supplied per corpus:

```python
from kb.extract import main, DEFAULT_ASYMMETRIC_RELATIONS

# augment the defaults for a chemistry corpus ...
main(asymmetric_relations=DEFAULT_ASYMMETRIC_RELATIONS | {"SYNTHESIZES", "CATALYSES"})

# ... or override entirely for a legal corpus
main(asymmetric_relations={"SUPERSEDES", "CITES", "AMENDS"})
```

Irreflexivity is a per-relation **schema** property, so it belongs to the
corpus/ontology, not to the extractor hardcode. Entity surface forms are
also normalised at this stage — `normalize_entity` strips possessive
clitics ("Aristotle's" → "Aristotle") and collapses duplicate-token spans
("Aristotle Aristotle" → "Aristotle"), and `strip_trailing_subject`
repairs greedy subject-merge ("Nicomachean Ethics Aristotle" →
"Nicomachean Ethics") — all before alias canonicalisation, and all
corpus-independent.

### Optional: dependency-parse extraction (spaCy)

The default extractor is regex + verb-anchors (no third-party NLP). If spaCy and
a model are installed:

```bash
pip install spacy && python -m spacy download en_core_web_sm
```

extraction automatically switches to a **dependency-parse SVO** path
(`extract_facts_spacy`): subject = `nsubj` of the verb, object = its `dobj` /
agent **in the same clause**. This fixes cross-clause object mis-binding
("Aristotle wrote treatises influencing Cicero" no longer yields a spurious
`Aristotle WROTE Cicero`) and handles passives ("X was tutored by Y" → `Y
TUTORED X`). Absent spaCy it falls back to the regex path, so the default
install stays light and deterministic. The verb→relation map is configurable,
like the irreflexive set:

```python
from kb.extract import DEFAULT_VERB_RELATIONS
vr = {**DEFAULT_VERB_RELATIONS, "synthesize": "SYNTHESIZES"}   # e.g. a chemistry corpus
```

### Add a new inference rule

In `src/kb/reason.py`, define a function returning a list of
`Derivation`s, then register it as a `Rule`:

```python
def r_authored_in_genre(kb: KB) -> list[Derivation]:
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
            out.append(Derivation("r_authored_in_genre", derived,
                                   [t1, t2], expl))
    return out

RULES.append(Rule("r_authored_in_genre", r_authored_in_genre))
```

The rule is picked up automatically on next `apply_all_rules(kb)`.

### Add a disjunctive rule

When several different relations should all produce the same
consequent, register a `DisjunctiveRule` instead of writing the
alternatives as Python branches — the structure stays inspectable:

```python
LEARNED_FROM = DisjunctiveRule(
    name="learned_from",
    alternatives=["TUTORED_BY", "INTELLECTUAL_DESCENDANT_OF",
                  "STUDIED_UNDER"],
    consequent="LEARNED_FROM",
    explanation_template=(
        "Since {subject} stands in relation {via} to {object}, "
        "therefore {subject} learned from {object}."
    ),
)
RULES.append(LEARNED_FROM.to_rule())
```

### Declare an OWL-style ontology

```python
from kb.ontology import Ontology
from kb.ontology_rules import compile_to_rules
from kb.reason import RULES, apply_all_rules_to_fixpoint

ont = (
    Ontology("biographical")
    .transitive_property("ANCESTOR_OF")
    .symmetric_property("SIBLING_OF")
    .inverse_properties("TUTORED", "TUTORED_BY")
    .sub_property_of("TUTORED_BY", "INFLUENCED_BY")
    .subclass_of("Philosopher", "Person")
    .subclass_of("Person", "Mortal")
    .equivalent_classes("Sage", "Wise_One")
    .disjoint_with("Living", "Deceased")
    .functional_property("BIRTH_DATE")
    .inverse_functional_property("HAS_DOI")
    .domain("CONQUERED", "Person")
    .range("CONQUERED", "Place")
)

owl_rules = compile_to_rules(ont)
combined = list(RULES) + owl_rules
kb_ext, derivations, stats = apply_all_rules_to_fixpoint(kb, rules=combined)
```

The compiled rules carry `owl:` / `rdfs:` prefixes in their names
so OWL-derived facts are distinguishable from hand-written rules
in derivation logs.

### Use temporal slots

Attach `valid_from` / `valid_to` to triples; the engine intersects
intervals when propagating temporal validity through derivations.
Temporally inconsistent inputs cause the derivation to be silently
suppressed.

```python
from kb.query import Triple
from kb.temporal import Interval, intersects, valid_at, compose

# Create a triple with a validity window.
t = Triple(
    "Plato", "TUTORED_BY", "Socrates",
    "Plato", -1,
    valid_from="407 BC", valid_to="399 BC",
)

# Check whether two facts coexist in time.
# `intersects` is permissive — it counts touching boundaries ("meets")
# as coexistence, which is what temporal PROPAGATION wants.
if intersects(Interval(t.valid_from, t.valid_to), other_interval):
    ...

# For CONFLICT detection use `strictly_overlaps` (positive-duration
# overlap): a value that ends exactly where its successor begins is a
# clean succession, not a contradiction. To model such a succession,
# give the two periods touching/adjacent windows (e.g. valid_to=
# "2018-12-31" then valid_from="2019-01-01") or leave the open side None.

# Point-in-time check.
if valid_at(t, "400 BC"):
    ...

# Compose Allen relations (for compound temporal reasoning).
possible = compose("before", "overlaps")  # frozenset of relations
```

### Use confidence

```python
from kb.confidence import (
    noisy_and, noisy_or, derive_confidence, drop_below,
)

# Combine input confidences.
derived_conf = derive_confidence([0.8, 0.5], mode="product")  # 0.40
derived_conf = derive_confidence([0.7, 0.6], mode="noisy_or") # 0.88

# Filter low-confidence triples out of an artifact before serialising.
solid = drop_below(kb.triples, threshold=0.5)
```

The engine propagates confidence automatically when
`apply_all_rules_to_fixpoint` is called with `propagate_confidence=True`
(the default). Each derivation gets confidence = noisy-AND of its
inputs.

### Use HermiT (full OWL DL reasoning)

For inference beyond what the compile-to-rules backend covers —
cardinality, complex class expressions, full DL classification —
attach the HermiT adapter at a high stratum:

```python
from kb.ontology import Ontology
from kb.ontology_owl import hermit_rule, hermit_enrich
from kb.reason import RULES, apply_all_rules_to_fixpoint

# Same DSL, plus the HermiT-only axioms:
ont = (Ontology("geometry")
       .declare_classes("Triangle", "Vertex")
       .cardinality("HAS_VERTEX", exactly=3)
       .domain("HAS_VERTEX", "Triangle")
       .class_intersection("EquilateralTriangle",
                           "Triangle", "AllSidesEqual"))

# One-shot enrichment:
enriched, derivs, info = hermit_enrich(kb, ont)
print(info["consistent"], info["n_inferred"])

# Or hook into the engine pipeline at stratum 5 (HermiT runs after
# stratum-0 closure + stratum-1 negation):
combined = list(RULES) + [hermit_rule(ont, stratum=5)]
kb_ext, derivs, stats = apply_all_rules_to_fixpoint(kb, rules=combined)
```

Soft dependencies: `pip install owlready2` and any Java 8+ JVM
(OpenJDK 17 recommended). The adapter degrades cleanly when missing
— callers see a clear ImportError / RuntimeError, not a crash.

### Detect and resolve conflicts

```python
from kb.conflict import (
    apply_with_conflict_resolution,
    LatestWinsPolicy, HighestConfidencePolicy, AuthorityWinsPolicy,
    SurfaceForReviewPolicy, ChainPolicy,
)
from kb.ontology import Ontology

ont = (
    Ontology()
    .functional_property("BIRTH_DATE")
    .functional_property("CURRENT_EMPLOYER")
    .disjoint_with("Living", "Deceased")
)

# Single policy.
resolved, derivs, conflicts, stats = apply_with_conflict_resolution(
    kb, ontology=ont, policy=LatestWinsPolicy(),
)

# Chain of policies — try each in order; first to narrow wins.
chain = ChainPolicy([
    AuthorityWinsPolicy(),
    LatestWinsPolicy(),
    HighestConfidencePolicy(),
    SurfaceForReviewPolicy(),
])
resolved, derivs, conflicts, stats = apply_with_conflict_resolution(
    kb, ontology=ont, policy=chain,
)
```

The resolved KB has dropped triples removed and CONFLICT_* markers
cleaned up. With `SurfaceForReviewPolicy`, `CONFLICT_UNRESOLVED`
triples are added in their place for human review.

### Add a negation-as-failure rule

Set `stratum=1` so the rule runs once on the converged positive
closure (stratified semantics). Use `kb_has(kb, subject, relation)`
to test for absence:

```python
def r_orphan(kb: KB) -> list[Derivation]:
    """X is born, but the KB records no parent for X → X IS_A ORPHAN.
    Closed-world: only sound when the KB has all known parents."""
    out = []
    for t in kb.triples:
        if t.relation != "BORN_DATE":
            continue
        if kb_has(kb, t.subject, "CHILD_OF"):
            continue
        derived = Triple(t.subject, "IS_A", "ORPHAN_OF_RECORD",
                         "(derived)", -1)
        out.append(Derivation("r_orphan", derived, [t],
                               f"{t.subject} has no recorded parent."))
    return out

RULES.append(Rule("r_orphan", r_orphan, stratum=1))
```

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

## AI-assisted maintenance — practical workflows

The architecture's runtime is AI-free. Construction and maintenance,
however, are exactly where an LLM coding assistant (Claude Code,
Cursor, GitHub Copilot Chat, Aider, etc.) is most useful. Below are
seven concrete workflows. Each shows what to feed the assistant,
what to ask, and what to do with the output.

These workflows replace the slow / manual / regex-tweaking parts of
maintaining the KB with one-shot AI passes. The artifact that
results is still inspectable JSON; the AI is the editor's assistant,
not part of the running system.

### 1. Find facts the extractor missed

**Goal**: increase recall on an article whose KB coverage looks
sparse.

**Input to the assistant**:
- The source article's cleaned prose (a few hundred lines)
- The triples that `src/kb/extract.py` already produced for that article
  (filter the JSON by `source_article`)

**Prompt template**:
> Here is the source text of the Wikipedia article on X.
> Here are the structured triples already extracted for it.
> Identify every additional fact in the source that should be in
> this list but isn't. For each, give: subject, relation (from this
> list: BORN_IN, BORN_DATE, ...), object, and the sentence index it
> came from. Use the same relation vocabulary as the existing
> triples. Skip facts you're uncertain about.

**Output handling**: paste the missing facts into `PATCH_FACTS` in
`src/kb/extract.py`. Re-run `query.py`; the entity card now has the
new facts.

---

### 2. Validate facts the extractor produced

**Goal**: find false-positive triples — facts that look reasonable
but don't actually appear in the source.

**Input to the assistant**:
- A random sample of N=20-50 triples
- For each, the source sentence (fetch by `source_article` +
  `source_sentence_idx`)

**Prompt template**:
> For each triple below, the source sentence is shown. For each,
> answer: (a) is the triple correctly extracted from this sentence?
> (b) if no, what went wrong? Possible answers: correct, wrong
> subject, wrong object, wrong relation, hallucinated (fact not in
> sentence at all), over-extended span (entity captured too much
> text).

**Output handling**: triples flagged as wrong/hallucinated get
removed from the JSON. Patterns of similar errors suggest extractor
improvements (e.g., a verb anchor matching too loosely).

---

### 3. Suggest new verb anchors

**Goal**: improve extractor recall by adding new patterns.

**Input to the assistant**:
- A sample of sentences from `wikipedia_utils.split_sentences` that
  contain biographical-keyword verbs (born, died, wrote, married,
  ...) but didn't yield any triples in the current extraction

**Prompt template**:
> Below are sentences that look like they should yield a fact but
> the regex extractor missed them. For each, identify the verb
> phrase that signals the relation, and propose a regex pattern
> (anchored as `\b...\b`) plus the relation name. Group similar
> patterns together. Output in the format of `VerbAnchor` entries
> from src/kb/extract.py.

**Output handling**: paste new entries into the `VERB_ANCHORS` list.
Re-run extraction; sentences that previously fell through now yield
triples.

---

### 4. Curate a corpus for a new domain

**Goal**: bootstrap an Ahab- or git_rag-style corpus for a new
domain (e.g., AWS CLI documentation, regulatory text, character
quotes from a different novel).

**Input to the assistant**:
- The source documentation (uploaded directly or section by section)
- The target schema (e.g., `KnowledgeItem` fields from
  `src/git_rag/knowledge.py`)

**Prompt template**:
> Here is the AWS CLI documentation for the `aws s3` command family.
> Produce one `KnowledgeItem` record per common operation. For each:
> populate item_id, topic, subtopic, intent, question_patterns (list
> of paraphrases a user might ask), commands (the actual aws s3 ...
> invocations), explanation (1-3 sentences), cautions (gotchas), and
> source (the AWS docs URL). Use the schema and conventions from
> src/git_rag/knowledge.py exactly.

**Output handling**: save as `src/aws_rag/knowledge.py`. Copy
`src/git_rag/query.py` to `src/aws_rag/query.py`, adjust
`TOPIC_KEYWORDS` and `DEMO_QUERIES`, and the new domain is live.

---

### 5. Generate stress-test queries

**Goal**: find weak points in matcher coverage or in the KB's
multi-hop reach.

**Input to the assistant**:
- The KB's relation distribution (output of `src/kb/query.py`'s "Top 10
  relations" section)
- A sample of entities (from "Top 25 most-connected entities")

**Prompt template**:
> Below are the relation types and most-connected entities in our
> KB. Propose 20 queries that should be answerable from this KB:
> - 5 single-hop factual lookups
> - 5 two-hop chain queries (e.g., "X's student's conquests")
> - 5 path queries between specific entity pairs
> - 5 filter/aggregate queries (e.g., "all entities born in century N")
> Mix easy and hard cases.

**Output handling**: run each query against the KB. Failures are
the prioritised work list — either KB coverage gaps (add patches)
or matcher gaps (add patterns).

---

### 6. Propose new inference rules

**Goal**: increase the KB's derived-fact yield by adding rules.

**Input to the assistant**:
- The list of existing relation types in the KB
- The list of existing inference rules in `src/kb/reason.py`

**Prompt template**:
> Given these relation types (TUTORED_BY, CHILD_OF, CONQUERED,
> SUCCEEDED, FOUNDED, RULER_OF, BORN_DATE, DIED_DATE, ...) and these
> existing rules in src/kb/reason.py, propose 5 new Horn-clause
> rules that derive useful new facts. For each: name, antecedents,
> consequent, and a "since...therefore..." explanation. Skip rules
> that produce noisy or trivially-true derivations.

**Output handling**: add proposed rules as functions in
`src/kb/reason.py`, register them in the `RULES` list. Re-run
`reason.py`; the extended KB now has the new derivations.

---

### 7. Detect bad entities (parser errors)

**Goal**: find entities that are extraction artifacts rather than
real names.

**Input to the assistant**:
- The top 50 entities by mention count (from "Most-connected
  entities" output)

**Prompt template**:
> Below are the 50 most-mentioned entities in our KB. For each,
> classify as: (a) real entity, (b) parsing artifact (sentence-
> initial word captured wrongly, adjective captured as part of
> name, conjunction phrase captured as entity), (c) ambiguous. For
> each artifact, suggest what stopword or pattern fix would
> prevent it.

**Output handling**: add identified artifact tokens to
`ADJECTIVE_STOPWORDS` in `src/kb/extract.py`. Re-run extraction;
spurious mentions drop out.

---

### Putting workflows together

A typical AI-assisted maintenance pass:

```
1. Generate stress-test queries (workflow 5)
2. Run them → identify failures
3. For each failure, root-cause:
   - Missing facts → workflow 1
   - Wrong facts → workflow 2
   - Missing patterns → workflow 3
   - Missing inference rules → workflow 6
4. Run workflow 7 to find parser artifacts
5. Re-extract / re-reason, re-run queries
6. Iterate until stress-test failures < threshold
```

The pass takes hours not weeks because each step is a single LLM
call. The KB artifact improves at each iteration; the runtime code
doesn't change.

This is the maintenance story: **AI extracts knowledge into a
consistent, structured format; the structured format is what runs.**
AI is a construction-time extractor, not a runtime dependency. The
cost of an LLM-assisted workflow is a flat per-pass API cost (or
one's own time with a coding assistant); the benefit is a
better-quality KB serving free, deterministic queries forever.

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

The demos ARE the human-inspectable test suite — each loads its
corpus, runs scripted queries, and prints results with provenance.
`src/kb/reason.py` additionally bundles an assertion-backed
stress-test suite that runs after the main demo.

To verify behaviour after a change:

```bash
python src/kb/query.py                 # entity cards + multi-hop chains
python src/kb/reason.py                # rule derivations + 10 stress tests
python src/kb/ontology.py              # OWL DSL demo + 11 stress tests
python src/kb/conflict.py              # conflict-resolution 11 stress tests
python src/ahab/talk.py                # 13 Q&A turns; chapter citations
python src/ahab/reason.py              # structured reasoning over utterances
python src/git_rag/query.py            # 15 Git Q&A; manual-section sources
python src/git_rag/reason.py           # structured reasoning over Git docs
python src/distill/purify.py           # knowledge distillation + 6 stress tests
python src/kb/ontology_owl.py          # HermiT DL reasoning + 7 stress tests
                                       #   (skips gracefully without owlready2 / Java)
python src/diachronic/analyse.py       # changing-patterns-of-thinking + 5 stress tests
# microtheory suite — run as modules from src/ (python -m):
python -m microtheory.analyse          # four schools of economics, one recession
python -m microtheory.breakage         # how overlapping microtheories break knowledge
python -m microtheory.test_scope       # scope unit test (10 checks)
python -m ingestion.analyse            # importing self-contradictory data (incl. latent)
```

Three assertion-backed stress suites pin engine properties:

- `kb/reason.py:stress_test` — ten scenarios covering deep-chain
  transitive closure, disjunctive-rule firing across alternatives,
  stratified negation, cycle convergence, empty-KB safety, alias
  canonicalisation, ordering invariance, run-to-run determinism,
  divergence detection, and arbitrary-stratum dispatch.

- `kb/ontology.py:_stress_test` — eleven scenarios exercising the
  full OWL DSL: TransitiveProperty, SymmetricProperty,
  InverseProperties, SubPropertyOf chains, SubClassOf chains,
  EquivalentProperties, EquivalentClasses, DisjointWith
  (contradiction detection), domain/range, composed axioms, and
  determinism.

- `kb/conflict.py:_stress_test` — eleven scenarios covering
  functional-property violations (with temporal-overlap scoping),
  inverse-functional-property violations, every resolution policy
  (LatestWins, HighestConfidence, AuthorityWins, SurfaceForReview,
  ChainPolicy), confidence propagation through derivations,
  temporal-validity propagation, and backward compatibility with
  v1 triple shapes.

- `distill/purify.py:_stress_test` — six scenarios verifying the
  knowledge-distillation pipeline: noisy-OR corroboration boost,
  confidence-threshold pruning, marker preservation, end-to-end
  purification of the bundled noisy corpus, temporal scoping of
  classification changes, and authority-driven conflict resolution.

- `kb/ontology_owl.py:_stress_test` — seven scenarios verifying the
  HermiT (DL reasoner) integration: subclass-chain DL classification,
  cardinality enforcement (violation + satisfaction), class
  intersection inference, disjoint-class inconsistency detection,
  someValuesFrom inference, and per-call World isolation. Skips
  gracefully if owlready2 or Java are unavailable.

- `diachronic/analyse.py:_stress_test` — five scenarios verifying the
  changing-patterns-of-thinking analysis: multi-era corpus coverage,
  per-era schema-drift detection (distinct IS_A class sets), the
  affirmed-then-rejected trajectory for the "indivisible" property,
  temporal scoping preventing classification flattening, and
  vocabulary drift across eras.

If any assertion fails, the script exits non-zero — that's the
regression signal.

For automated regression on the demo output: pipe to files and diff
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
