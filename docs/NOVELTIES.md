# SKEAR — Novelties

What's architecturally different about SKEAR (Structured Knowledge
Extraction And Reasoning).

> **See also**: [README](../README.md) ·
> [ARCHITECTURE](ARCHITECTURE.md) ·
> [DEVELOPER_GUIDE](DEVELOPER_GUIDE.md) ·
> [USE_CASES](USE_CASES.md) ·
> [COMPARISONS](COMPARISONS.md) ·
> [LICENSE](../LICENSE.md)

What this project contributes that isn't standard. Each item below
has prior art in adjacent fields; the contribution is the unification
into a working pipeline.

For a side-by-side with each comparable technology (vector RAG,
GraphRAG, Wikidata, OpenIE, FrameNet, CYC, ...) see
[COMPARISONS.md](COMPARISONS.md). For the design see
[ARCHITECTURE.md](ARCHITECTURE.md). For practical recipes see
[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).

## At a glance

Six architectural contributions, summarised in one sentence each:

1. **Cell-grammar with `shape × context × flavour`** — adds a third
   axis (flavour: speaker style / corpus voice) to frame-semantics,
   making phrase distributions condition on more than just the
   semantic frame.
2. **Interaction-type compact selectors** — encode (type + cells +
   phrase overrides) as a hierarchical arithmetic-coded path; adding
   a new surface variant costs ~0 bits on existing fires.
3. **Bidirectional structure ↔ text mapping** — the same artifact
   serves both as a queryable KG and a byte-exact compression target;
   one representation, two roles.
4. **Causal state-tracking for narrative compression** — runtime
   state of relational facts; subsequent events that follow from
   state cost ~0 bits to encode.
5. **Provenance + reasoning + grounded generation in one artifact** —
   a single persistent KB supports lookups, deductive inference (Horn
   + disjunctive + stratified negation + OWL DL via HermiT),
   conversational generation, and compression, all with per-fact
   provenance.
6. **Schema-as-data — preserving multiple incompatible framings of
   the same subject** — the IS_A classifications, organising
   relations, and conceptual apparatus that frame each fact are
   themselves first-class data with scope (temporal, ideological,
   methodological, traditional) and source attribution. The same
   subject can be structurally reassembled by different eras, schools
   of thought, ideologies, or communities — and the differences
   between framings are queryable rather than averaged away. This is
   the architectural feature most directly pointed at the failure
   mode of LLM-based AI, which trains on the union of all framings
   and produces a single smoothed answer with no internal structure
   for "this view vs that view."

Each is explained in detail below.

---

## 1. Cell-grammar with `shape × context × flavour` decomposition

**What it is**: structural decomposition of a sentence as a sequence
of typed cells (LOCATION, ACTOR, VERB, PATIENT, ...), each filled by
a phrase chosen from a context- and flavour-conditional library.

**Prior art**:
- FrameNet (Fillmore et al., 1998-) — semantic frames with role
  fillers. Has shape × context. Doesn't ship as a compression scheme
  or as an operational extraction pipeline.
- PropBank (Palmer, 2005-) — predicate-argument structure.
- AMR (2013-) — per-sentence semantic graphs.
- Construction grammar (Goldberg, 1995-) — theoretical framing.

**What's new here**:
- **Flavour conditioning as a third axis**. FrameNet's frames are
  universal across speakers; we add flavour (Einstein-style scientific
  vs Mick-Jagger-style music-celebrity vs Aristotle-style ancient-
  philosopher) as sub-context that conditions phrase distributions.
- **Compression role made explicit**. Most frame-semantics work is
  analytic, not generative. Here the structured form is provably
  shorter than the surface text under entropy coding.
- **Operational pipeline**. Extractor + matcher + encoder + decoder
  + queryable graph + reasoning engine, empirically validated.

---

## 2. Interaction-type compact selectors

**What it is**: a semantic event class (BORN, TUTORED, CONQUERED, ...)
that abstracts away from surface phrasings. Encoding an interaction
as `(type_id, slot_fillings)` plus optional phrase overrides collapses
many surface-form variants to one identifier.

**Prior art**:
- Event extraction (ACE, TAC KBP, BERT-based event taggers).
- Wikidata properties / OWL classes — typed predicates.

**What's new here**:
- **Structured entropy-coded selectors**. Standard KG work uses flat
  type IDs. We encode type + cell-sequence + phrase-choice overrides
  as a hierarchical path, arithmetic-coded under empirical
  distribution. Sublinear cost in template count.
- **Shared phrase library**. Adding a 5th variant of an existing
  interaction type costs ~0 bits on existing fires — only new fires
  pay. Standard KG work would allocate a new relation; we add a
  phrase entry.

---

## 3. Bidirectional structure ↔ text mapping with byte-exact reconstruction

**What it is**: the same structured representation serves as (a) a
queryable KG and (b) a compression target that reconstructs surface
text byte-exactly.

**Prior art**:
- Compression literature (CMIX, NNCP, PAQ family) — byte-exact, no
  KG integration.
- Knowledge graphs (Wikidata, FrameNet) — structured, no text
  reconstruction.
- OpenIE / KG embeddings — extract structured, discard surface text.
- GraphRAG / vector RAG — graph for retrieval, LLM for synthesis;
  synthesis loses byte-exactness and introduces hallucination.

**What's new here**:
- **Same artifact for both directions**. The cell-grammar template is
  invertible: text → structured (extraction), structured → text
  (rendering, byte-exact for full-template matches). One representation
  serves both roles.
- **Deterministic rendering**. No LLM in the rendering loop.
  Hallucination is structurally impossible — the renderer can only
  output text consistent with the grammar + slot fillings.

---

## 4. Causal state-tracking for narrative compression

**What it is**: a runtime model that maintains relational state as
events are encoded; subsequent events that follow from the state
cost ~0 bits because the decoder can derive them.

**Prior art**:
- Discourse Representation Theory (Kamp, 1981-).
- Dynamic Predicate Logic (Groenendijk-Stokhof, 1991).
- Knowledge graphs in chatbots maintain dialog state but not full
  relational models.

**What's new here**:
- **Operational implementation of state-update as a compression
  mechanism**. Empirically reduces explicit fact count by ~60%
  (3,515 facts derived from 2,169 base facts in the demo KB by
  Horn + disjunctive + stratified-negation rules run to fixpoint).
- **State predictor instead of byte predictor**. A small auxiliary
  model predicts SELECTORS (which phrase / dictionary to sample
  from) given the running state. Much narrower and more learnable
  than byte prediction.

---

## 5. Provenance + deductive reasoning + grounded generation in one artifact

**What it is**: a single persistent artifact (populated graph + rules
+ cell grammar) supporting lookups, deductive inference, conversational
generation, and compression — all grounded with per-fact provenance.

**Prior art**:
- Symbolic AI / CYC — reasoning + provenance, but hand-curated KB,
  no extraction, no generation.
- Wikidata + SPARQL — lookups + some inference, no generation, no
  compression role.
- LLM + RAG hybrids — generation but lose provenance during synthesis.
- OWL reasoners — deductive inference, but KB construction is the
  bottleneck.

**What's new here**:
- **Unified pipeline**. Each property exists separately in adjacent
  systems; the combination into one artifact has not been the focus
  of any major effort. Our pipeline:
  - Extracts the graph (AI-driven at construction time)
  - Stores it persistently (~465 KB JSON for 1000 articles)
  - Supports lookups (graph traversal, sub-ms)
  - Supports inference (11 rules — Horn, disjunctive, and stratified
    negation-as-failure — run to fixpoint, deriving thousands of facts)
  - Supports text generation (deterministic, no LLM at serve time)
  - Maintains provenance everywhere (rule → inputs → source text)
  - Is itself compression-grade (structured form is ~5-10× smaller
    than surface text on template-matching content)

---

## 6. Schema-as-data: preserving multiple incompatible framings

**What it is**: the IS_A classifications, organising relations, and
conceptual apparatus that frame a fact are themselves first-class
data — they carry their own scope (temporal, ideological,
methodological, traditional) and source attribution. The same
subject can be structurally reassembled by different communities of
thought, and the differences between framings are queryable rather
than averaged away.

The atom is a worked example: the SAME word carries IS_A
`IndivisiblePrinciple` (Greek atomism), `RejectedHypothesis`
(Aristotelians), `SmallHardSphere` (Newtonian), `ChemicalElement`
(Daltonian), `CompositeStructure` (Rutherford / Bohr), and
`QuantumSystem` (modern). Property `indivisible` is affirmed
across four eras then rejected; the reversal is a queryable
event, not narrative summary.

**Prior art**:
- CYC microtheories (Lenat 1991-) — contextual logic for facts
  that hold in some contexts but not others. The closest direct
  ancestor.
- Description Logic with versioning extensions (OWL-Time, named
  graphs) — schema-as-data is partial in RDF/OWL ecosystems but
  not the central design point.
- Formal Concept Analysis (Wille 1982-) — extensional vs
  intensional definition; an entity can belong to multiple
  concept lattices simultaneously.

**What's new here**:
- **Schema lives in the same triple shape as the facts**. IS_A is
  a relation like any other, with the same temporal scope,
  confidence, source-authority, and provenance treatment. No
  separate metalanguage. No "schema layer" outside the data.
- **Multi-framing without contradiction at any single time**. The
  temporal-scoping in `src/kb/temporal.py` (Allen interval algebra
  + the `intersects` predicate) means functional-property axioms
  on IS_A flag conflicts only WITHIN a single scope. The same
  subject's five different IS_A classes across eras don't trip
  the conflict detector.
- **Framings as a general capability, not just historical scoping**.
  The diachronic suite uses temporal scope (eras). The same
  machinery works for any scope axis: ideological position,
  methodological tradition, school of thought, cultural community,
  practitioner discipline. The schema slot doesn't care whether
  the scope is "Newtonian-era" or "Keynesian-school" or
  "phenomenological-tradition."
- **Architecturally pointed at LLM failure mode**. LLMs train on
  the union of all framings and produce a single smoothed answer.
  There's no internal switch for "restrict to framing X." SKEAR
  has that switch as a scope query — the difference shows up as
  structure preserved, not narrative averaged.

---

## Why no one has built this before

For each novelty above, parts have been attempted multiple times.
The unification requires:

1. **Modern LLMs as construction-time extractor**. The CYC era tried
   symbolic KBs by hand. The OpenIE era tried automatic extraction
   with weak NLU. Both failed at corpus scale. AI-driven extraction
   (LLMs reading articles and emitting structured facts) is a recent
   capability.
2. **Crossing the compression / KG / linguistics divide**. Compression
   people don't think about KGs. KG people don't think about
   compression. Frame-semantics linguists don't ship code. The
   unification is not the focus of any single lab.
3. **The scale-only consensus 2017-2024**. "Just bigger transformers"
   dominated. Architectural alternatives were marginalised.
4. **Wins compound at scale**. At 10 articles the architectural
   advantage is small. The compounding payoffs (decompressor size,
   hallucination resistance, multi-hop reasoning, edge deployment)
   show up at 1M-1B articles, where the upfront cost is meaningful.
5. **The vector-RAG local optimum**. Once vector RAG worked "well
   enough" for enterprise use, the field locked in.

The technical preconditions are now in place. The cracks in pure
scaling are visible. Regulated industries are demanding what this
architecture provides.

---

## What's demonstrated vs what's claimed at scale

| claim | demonstrated on | gap to production |
|---|---|---|
| Cell-grammar shape × context × flavour | 8/8 byte-exact across 2 contexts | scaling to ~20 contexts × ~50 flavours |
| Interaction-type compact selectors | 8 sentences, ~5% bit-cost reduction | corpus-scale empirical distributions; arithmetic coder integration |
| Causal state tracking | 11 hand rules + an OWL DSL (transitive / symmetric / inverse / functional / inverse-functional, sub-class / sub-property, equivalent / disjoint, domain / range) over 1000-article KB; fixpoint dispatch with stratified negation-as-failure and disjunctive rules; 32 stress-test scenarios across three suites | richer rule library; semi-naive evaluation for scale |
| Bidirectional byte-exact | 17/17 phenocryst sentences + 25/25 full article | groundmass byte-exactness via trained LM |
| Provenance + reasoning + generation | 10 working interfaces (3 query + 5 cross-domain reasoners over Wikipedia, Moby-Dick, Git docs, multi-source distillation, diachronic analysis — plus the HermiT adapter as an optional 6th) | production-grade extraction at 100M-article scale |
| Temporal validity | Full Allen interval algebra (13 atomic relations + composition table); engine propagates intervals through derivation chains | constraint propagation (AC-3) over Allen networks at scale |
| Uncertainty | Confidence slot on every triple; noisy-AND / noisy-OR / min / pluggable combiners; engine propagates through derivations | full probabilistic Datalog (ProbLog-style inclusion-exclusion) |
| Conflict resolution | Six policies (LatestWins / HighestConfidence / AuthorityWins / KeepAll / SurfaceForReview / ChainPolicy) over OWL-detected violations | per-tenant authority models; reviewer-UI integration |
| Schema-as-data / multi-framing preservation | Atom across 2,500 years of natural philosophy in `src/diachronic/`: 6 paradigms with distinct IS_A classifications, the famous indivisibility reversal queryable as a structural event, 5 assertion-backed scenarios | scope axes beyond temporal (ideology, methodology, school of thought, legal perspective, cultural tradition) implemented as the same mechanism; tooling for browsing the framing graph |

The architecture is concrete and implementable at small scale. The
production-scale validation requires AI-driven extraction at 100M+
article scale maintaining the quality demonstrated at 1000-article
scale.
