# SKEAR — Release Notes

> **See also**: [README](README.md) ·
> [docs/ARCHITECTURE](docs/ARCHITECTURE.md) ·
> [docs/DEVELOPER_GUIDE](docs/DEVELOPER_GUIDE.md) ·
> [docs/USE_CASES](docs/USE_CASES.md) ·
> [docs/COMPARISONS](docs/COMPARISONS.md) ·
> [docs/NOVELTIES](docs/NOVELTIES.md) ·
> [LICENSE](LICENSE.md)

Datetime-stamped record of significant work. Times are local
(Europe/Athens, UTC+3).

---

## 2026-05-12

### Project name: SKEAR

The project now goes by SKEAR (Structured Knowledge Extraction And
Reasoning) — a short, pronounceable acronym derived from the full
name. The repository slug remains
`structured_knowledge_extraction_and_reasoning`; only the doc-
visible naming changed.

The acronym foregrounds the architectural posture the docs already
described: AI optionally augments construction (extraction,
curation, OWL DL reasoning via the HermiT adapter), and no AI is in
the loop at query time. README and every doc heading were updated.

### HermiT (OWL DL) integration shipped

Pattern A from `docs/COMPARISONS.md` (CYC / OWL DL section), made
real. A construction-time enricher that translates our `Ontology` +
`KB` into OWL/RDF, invokes a real description-logic reasoner (HermiT
by default, Pellet alternative via `owlready2`), and converts
inferred facts back to our `Triple` / `Derivation` shape. Runtime is
unchanged — the shipped artifact is still pure JSON.

**Soft dependencies** — adapter loads cleanly without them and
raises actionable errors only when invoked:
  - `owlready2` (Python, `pip install owlready2`)
  - Java JVM (system, OpenJDK 17 recommended)

**What HermiT adds** (over the existing compile-to-rules backend):
  - Cardinality restrictions (`min/max/exactCardinality` axioms,
    qualified or unqualified).
  - Complex class expressions (intersection, union, complement,
    someValuesFrom, allValuesFrom).
  - Full DL classification — inferred class hierarchies that
    closed-world Horn rules can't compute.
  - Inconsistency detection — HermiT throws on unsatisfiable
    axioms + ABox; we catch and surface as `CONTRADICTION_DETECTED`.

**Ontology DSL extensions** (`src/kb/ontology.py`):
  - `.cardinality(prop, exactly=N, min=N, max=N, of=ClassName)`
  - `.class_intersection(name, *parts)`
  - `.class_union(name, *parts)`
  - `.class_complement(name, of)`
  - `.class_some_values(name, prop, target)`
  - `.class_all_values(name, prop, target)`

These methods are captured by the `Ontology` dataclass but
deliberately not compiled by `ontology_rules.py` — they require
open-world DL semantics and are consumed exclusively by
`ontology_owl.hermit_enrich`.

**Adapter implementation** (`src/kb/ontology_owl.py`, ~480 LoC):
  - Translation layer: classes, properties, axioms, individuals.
  - Bidirectional name sanitisation (entities with spaces /
    punctuation / Unicode → valid Python identifiers → original
    names restored on the way back).
  - Per-call `owlready2.World()` for namespace isolation across
    successive invocations.
  - `AllDifferent` asserted by default (unique-name posture) so
    cardinality constraints aren't trivially satisfied by name
    coalescing.
  - `INDIRECT_is_a` used to read inferences (vs the asserted
    `is_a`).
  - Public API: `hermit_enrich(kb, ontology) → (kb, derivs, info)`
    and `hermit_rule(ontology, stratum=5)` for engine integration.

**Seven assertion-backed stress scenarios** in
`src/kb/ontology_owl.py:_stress_test()`, verified against the real
HermiT reasoner on a t3.medium EC2:
  1. Subclass-chain DL classification.
  2. Cardinality violation (4 vertices vs exactly=3 → inconsistent).
  3. Cardinality satisfied.
  4. Class intersection inference.
  5. Disjoint-class inconsistency.
  6. someValuesFrom inference.
  7. Per-call World isolation (no state leak across invocations).

**All four example suites augmented** with optional HermiT sections
that demonstrate DL-only capability while soft-failing on hosts
without owlready2 / Java:
  - `src/kb/reason.py`: ClassicalPhilosopher ≡ Philosopher ⊓
    AncientGreek; Aristotle and Plato inferred, Descartes correctly
    excluded.
  - `src/ahab/reason.py`: ConfrontationalUtterance disjoint with
    IntrospectiveUtterance; 30 utterances verified consistent.
  - `src/git_rag/reason.py`: SafeOp disjoint with RiskyOp; 21 + 16
    items verified coherent.
  - `src/distill/purify.py`: atemporal Pluto edge case — HermiT
    proves inconsistency without temporal scoping, validating the
    main pipeline's temporal-layer design.

**Documentation**: `docs/DEVELOPER_GUIDE.md` (code map + recipe +
testing section), `docs/ARCHITECTURE.md` (Layer-2 description),
`docs/COMPARISONS.md` (CYC OWL DL adapter section — "planned" →
"shipped" + verified capability list).

### New example suite: knowledge distillation / purification

Added `src/distill/` — a fourth demo suite focused on the canonical
"noisy in, clean out" workflow that the temporal + confidence +
conflict capabilities now enable end-to-end.

  - `src/distill/corpus.py` — a deliberately-noisy multi-source
    astronomical-facts corpus (~65 facts from seven fictional sources
    of varying authority: IAU_2023, NASA_factsheet, peer-reviewed
    paper, britannica_1985, old_encyclopedia_1965, textbook_2010,
    blog_post). The corpus is engineered to exhibit every pathology
    the purification pipeline targets — corroborated multi-source
    agreement, functional-property conflicts (different masses for
    the same body), outdated measurements (Andromeda's distance
    progressively revised from 1.0e6 to 2.5e6 light-years), and
    low-authority noise standing alone.

  - `src/distill/purify.py` — the full pipeline: OWL conflict
    detection → ChainPolicy resolution (Authority → Latest →
    HighestConfidence → SurfaceForReview) → multi-source
    corroboration boost (noisy-OR) → confidence-threshold pruning →
    marker cleanup. Returns a clean canonical KB plus a
    `PurificationReport` describing what was changed and why. Six
    assertion-backed stress scenarios.

End-to-end on the bundled corpus: 66 → 29 triples, 28 functional-
property conflicts detected, 15 multi-source groups merged, 3
standalone low-confidence facts pruned. The famous Pluto edge case
behaves correctly: classifications Planet (valid until 2006-08-23)
and DwarfPlanet (valid from 2006-08-24) are temporally disjoint and
NOT flagged as a conflict — both survive as facts of different eras.

Documentation updated:
  - `README.md`: new demo description; three new "Who this is for"
    rows covering multi-source reconciliation, time-varying facts,
    and disputed-information audit trails.
  - `docs/ARCHITECTURE.md`: distillation row added to the
    "Extending to new domains" table.
  - `docs/DEVELOPER_GUIDE.md`: distill/ added to the code map; the
    six stress scenarios listed in the testing section.

### General-purpose engine extensions: OWL DSL, temporal, uncertainty, conflicts

Closed three architectural gaps that mattered for the engine being a
general-purpose reasoning facility rather than a narrow demo. Schema-
compatible throughout — existing JSON KBs load unchanged.

**OWL ontology DSL (`src/kb/ontology.py`, `src/kb/ontology_rules.py`):**
A small declarative DSL for OWL-style axioms — classes, properties,
sub-class / sub-property hierarchy, transitive / symmetric / inverse
/ functional / inverse-functional properties, equivalent / disjoint
classes, domain / range. The compiler emits standard `Rule` objects
into the existing engine; closed-world; no external DL reasoner.
Functional / inverse-functional axioms emit `CONFLICT_*` markers
consumed by the conflict module. Eleven stress-test scenarios pin
the compiler's behaviour. Earlier in the day the OWL DSL was
introduced without functional/inverse-functional axioms — those are
added now.

**Temporal slots + Allen algebra (`src/kb/temporal.py`):**
Optional `valid_from` / `valid_to` fields on every Triple (ISO date
strings; None = unbounded). Full Allen interval algebra (13 atomic
relations + composition table + relation inversion). The lenient
`intersects` predicate is used by the engine and the conflict
detector for "do these triples coexist in time?" tests. The engine
intersects input intervals when propagating temporal validity
through derivations; temporally inconsistent inputs silently
suppress the derivation. Date parser handles full ISO, year-month,
year-only, and BC forms.

**Confidence / uncertainty (`src/kb/confidence.py`):**
Optional `confidence` field on every Triple (float in [0.0, 1.0],
default 1.0). Combinators: `noisy_and` (default, product), `min`
(weakest-link), `noisy_or` (independent-evidence). `derive_confidence`
accepts a mode string or a caller-supplied callable. Engine
propagates input confidences through derivations via noisy-AND when
its `propagate_confidence` flag is set (default on). Multiple
semantic interpretations of the number — probabilistic, fuzzy,
subjective-Bayesian, partial-belief — equally well-supported; the
combinators don't prescribe a reading.

**Conflict detection + resolution (`src/kb/conflict.py`):**
`detect_conflicts` reads the `CONFLICT_*` and `CONTRADICTION_DETECTED`
markers produced by the OWL rules. Six pluggable policies:
`LatestWinsPolicy` (latest `valid_from`), `HighestConfidencePolicy`,
`AuthorityWinsPolicy` (uses `KB.source_authority`), `KeepAllPolicy`,
`SurfaceForReviewPolicy` (keeps everything + emits
`CONFLICT_UNRESOLVED` markers), `ChainPolicy` (try each in order;
first to narrow wins). `apply_with_conflict_resolution` orchestrates
the full pipeline: fixpoint inference → conflict detection →
resolution → clean resolved KB. Eleven stress-test scenarios pin
behaviour across temporal overlap, source-authority ranking,
confidence-based resolution, and disjoint-class contradiction.

**Engine wiring (`src/kb/reason.py`):**
`apply_all_rules_to_fixpoint` gained two opt-in flags
(`propagate_confidence=True`, `propagate_temporal=True`, both
default on) and a `confidence_mode` parameter. Propagation is a
dispatcher-level wrapper — existing rules require no changes. With
default-confidence (1.0) and unbounded-temporal (None/None) inputs
the propagation is a no-op, so v1 triples flow through unchanged.
`KB.source_authority` was added (default empty dict) and `KB.load`
preserves it across the fixpoint rebuild. `KB.load` is also more
forgiving — filters unknown keys and applies defaults for missing
optional fields, so old JSON keeps working forever.

**Schema (`src/kb/query.py`):**
`Triple` gained optional `valid_from`, `valid_to`, `confidence`
fields. `KB` gained an optional `source_authority` dict. Both
backward-compatible via defaults; old JSON files load unchanged.

**Documentation:**
- `docs/ARCHITECTURE.md`: extended Layer-2 description with the
  temporal / uncertainty / conflict mechanisms; new glossary
  entries for Interval, Allen relation, Confidence, Conflict,
  Policy, Ontology.
- `docs/DEVELOPER_GUIDE.md`: code map adds temporal.py,
  confidence.py, ontology.py, ontology_rules.py, conflict.py;
  four new recipes (OWL ontology, temporal slots, confidence,
  conflict resolution); testing section names all three
  stress-test suites (32 assertions total).
- `docs/COMPARISONS.md`: CYC inference-power bullet rewritten;
  summary-table "Formal reasoning" cell now reflects the full
  capability surface.
- `docs/NOVELTIES.md`: "demonstrated vs claimed" table adds rows
  for temporal validity, uncertainty, and conflict resolution.
- `README.md`: capability bullets reflect time-aware queries and
  conflict-resolution policies.

### Reasoning-engine extension

Extended `src/kb/reason.py` beyond single-pass Horn to cover the three
capabilities flagged as missing in the CYC comparison
(`docs/COMPARISONS.md`):

- **Fixpoint iteration** via `apply_all_rules_to_fixpoint`. Rules run
  in ascending stratum order; within each stratum, iteration
  continues until no new facts are derived. Includes a divergence
  guard that raises `RuntimeError` rather than silently truncating
  at `max_iter`.
- **Disjunctive rules** via the new `DisjunctiveRule` dataclass —
  declarative form for the "alternative antecedent relations, one
  consequent" pattern. Compiles to a standard `Rule`.
- **Stratified negation-as-failure** via the `kb_has` helper and the
  `stratum` field on `Rule`. Rules at stratum ≥ 1 see only the
  closure of lower strata, keeping the result deterministic despite
  negation being non-monotonic. Arbitrary stratum depths supported.

Rules added: R8 transitive intellectual descent, R9 disjunctive
`INFLUENCED_BY` (`TUTORED_BY ∪ INTELLECTUAL_DESCENDANT_OF`), R10
stratified `FAMILY_PROGENITOR`, R11 descent-extension bridge
(introduced after stress-test scenario 1 caught a transitive-closure
gap in R1 + R8 alone).

### Stress-test suite

Added `stress_test()` to `src/kb/reason.py`: 10 assertion-backed
synthetic scenarios covering deep chains, cycles, empty KB, alias
variants, ordering invariance, determinism, divergence detection,
multi-stratum dispatch. Five bugs caught and fixed:

- R1 + R8 alone underdetermine transitive IDO closure on chains
  longer than 3 (fixed with R11).
- `kb_has` did not canonicalise its subject (fixed).
- `r10_progenitor` could emit duplicate progenitors via alias
  variants (fixed by canonicalising the parent before dedupe).
- Stratum ≥ 2 silently ignored by the hardcoded 0/1 dispatcher
  (fixed by generalising to all strata in ascending order).
- No divergence guard — runaway rules would silently truncate at
  `max_iter` (fixed with a `for…else` raise).

### Cross-domain reasoners

Two new files demonstrating that the same engine generalises across
data shapes without modification:

- `src/ahab/reason.py` — applies the engine to the 35-utterance
  Moby-Dick corpus. Theme co-occurrence and transitive thematic
  reach (fixpoint over 4 rounds, 552 derivations), `HAS_SPEECH_LABEL`
  unifying speech-act ∪ mood (`DisjunctiveRule`), confrontational vs
  introspective classification (function-form disjunction over
  object values), peaceful-addressee derivation (negation over a
  derived predicate — `self` and `other captain` qualify).
- `src/git_rag/reason.py` — applies the engine to the 37-item Git
  knowledge base. Transitive `RELATED_TO` closure for multi-hop
  topic navigation, `NEEDS_OPERATOR_ATTENTION` via
  `HAS_CAUTION ∪ USES_DESTRUCTIVE_COMMAND` (`DisjunctiveRule`),
  `RECOVERY_OPERATION` classification, `SAFE_TO_AUTOMATE`
  (negation-as-failure over the derived attention flag — 21 items
  qualify).

### Documentation

- `docs/COMPARISONS.md`: CYC inference-power bullet rewritten to
  reflect the engine's actual capability set (fixpoint + disjunction
  + stratified negation, no DL subsumption, no full FOL).
- `docs/ARCHITECTURE.md`: glossary entries added for *Fixpoint*,
  *Stratified Negation*, *Disjunctive Rule*; Layer-2 inference
  description updated to reflect fixpoint dispatch.
- `docs/DEVELOPER_GUIDE.md`: rule-adding recipes use the `Rule`
  dataclass; new recipes for `DisjunctiveRule` and
  negation-as-failure; code map extended with the new reasoner
  files; testing section notes the stress-test suite.

---

## 2026-05-11

### Upstream research (source research repository) — 12:48 – 15:00

Work in the upstream research repository that produced the
components later extracted into this public release:

- **12:48–13:33** — Foundational primitives: interaction-type
  encoder; flavour-detection prototype (7/7 article classification);
  cell-grammar extended to 17/17 phenocrysts; cross-context
  cell-grammar combining flavour and interaction-type.
- **13:22** — Aristotle generalisation test (honest negative result
  that informed the later combinatorial-construction framing).
- **14:30–14:33** — `kb_scale_experiment` at 1,000 Wikipedia
  articles: canonicalisation of entities, modern-date handling,
  richer queries. Output: the canonical 1,000-article KB used in
  this repo (`src/kb/kb_1000_articles.json`).
- **14:36** — KB persistence layer + query CLI + manual patches
  bringing the base graph to 2,169 triples and 2,561 entities.
- **14:39** — `kb_reasoning.py`: deductive inference with Horn-clause
  rules and `since A therefore B` provenance trails. Output: derived
  facts dataset (`src/kb/kb_1000_articles_extended.json`).
- **14:51** — `moby_dick_ahab/`: conversational generation grounded
  in Melville's corpus. 35 curated quotes, theme-matched retrieval.
- **14:58** — `enterprise_rag/`: Git-manual RAG demo. 37 curated KB
  items, intent + topic matching. NOVELTIES.md added.
- **15:00** — Documentation scrub: removed hedging phrases and
  dated work references.

### This repository — 15:23 – 18:13

Extraction of the above into a clean, public-facing release plus
iterative documentation work.

- **15:23** — `e889bf3` — Initial commit. Code under `src/` with
  three runnable demonstrations (Wikipedia KB, Captain Ahab, Git
  manual RAG). Pre-built KB JSON files included.
- **15:28** — `a291b0d` — Added `docs/DEVELOPER_GUIDE.md`: code map,
  data model, API quickref, recipes, troubleshooting.
- **15:36** — `572700a`, `1f73e70` — Added `docs/COMPARISONS.md`
  (side-by-side with vector RAG, GraphRAG, LLM-as-KB, Wikidata,
  OpenIE, FrameNet, CYC, Neo4j, BERT event extraction). Scrubbed
  residual jargon from `docs/NOVELTIES.md`.
- **15:39** — `8302ac3` — Cross-linked all documents with a
  consistent `See also` navigation block.
- **15:44** — `cb8525c` — Added `docs/USE_CASES.md`: 21 use cases
  grouped by criticality (regulated, technical, customer-facing,
  internal knowledge, research, brand), each with current approach
  / where it falls short / how this addresses it / implementation
  sketch / what's gained. Plus an explicit "where this does NOT
  replace LLMs" section.
- **15:48** — `c65db4c` — README H1 title-cased.
- **17:35** — `8989346` — `docs/ARCHITECTURE.md` extended with an
  explanation of the combinatorial construction pattern (regex +
  curated patches + AI extraction) and why imperfection in any
  single component does not matter.
- **17:37** — `80085e8` — `docs/DEVELOPER_GUIDE.md` extended with
  seven AI-assisted maintenance workflows (coverage review, drift
  audit, alias-map curation, inference-rule mining, ambiguity
  triage, schema migration, regression testing).
- **17:39** — `0f43d55` — `docs/ARCHITECTURE.md` extended with an
  explanation of how the system remains auditable, deterministic
  and non-hallucinatory even though AI is used at construction time.
- **17:41** — `b0c6919` — Reframed AI's role across documentation
  as *knowledge extractor into a consistent, structured format* —
  not *editor of the runtime*.
- **17:52** — `e0574e8` — Consistency pass: standardised paths
  (everything relative to repo root, `src/` prefixed), unified
  terminology, fixed `PROJECT_ROOT` resolution in
  `src/wikipedia_utils.py`.
- **18:10** — `0e2cd2e` — README rewritten for a business audience.
  Opens with the problem (hallucination, no audit trail,
  non-determinism), states the value proposition in plain language,
  describes the three demos at a high level, routes technical
  readers to `docs/`.
- **18:13** — `33fafca` — Obfuscated the licensing contact address
  in README and LICENSE to deter scrapers.

---

## Release-note conventions

- One H2 section per date.
- Local time (UTC+3) for ordering; commit hashes for traceability.
- Group entries by repository scope when multiple are involved.
- Free-form prose; no semantic-versioning bumps until the project
  has a stable external API.
