# SKEAR — Novelties

What's architecturally different about SKEAR (Structured Knowledge
Extraction And Reasoning).

> **See also**: [README](../README.md) ·
> [ARCHITECTURE](ARCHITECTURE.md) ·
> [DEVELOPER_GUIDE](DEVELOPER_GUIDE.md) ·
> [USE_CASES](USE_CASES.md) ·
> [COMPARISONS](COMPARISONS.md) ·
> [ORDERED_MICROTHEORIES](ORDERED_MICROTHEORIES.md) ·
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

Seven architectural contributions, summarised in one sentence each:

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
7. **Computation-as-data — ordered microtheories and an executor.** An
   optional order slot (`Triple.seq`) makes a microtheory a *sequence* —
   a procedure, or, when its members are opcodes, an executable program
   run by a closed-instruction-set executor (`kb.execute`). Algorithms
   then live in the same scoped, cited triple shape as facts and rules,
   so one engine queries, reasons over, AND executes them, with
   provenance unbroken from input data through computation to derived
   facts; a transpiler (`kb.transpile`) compiles the canonical triples to
   native Python as a derived cache. The database, the schema, the rules,
   and the code become one inspectable, auditable medium.

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

## 7. Computation-as-data: ordered microtheories and an executor

**What it is**: a microtheory (a scoped set of facts) gains an optional
order via `Triple.seq`, becoming a *sequence*. A sequence of steps is a
procedure; a sequence of operations is a program. SKEAR's executor
(`src/kb/execute.py`) runs such a program over a closed instruction set
(arithmetic, comparison, bitwise `AND`/`OR`/`XOR`/`NOT`/`SHL`/`SHR` for
flags/masks/sets, higher-order `MAP`/`FILTER`/`FOLD` that apply a microtheory
across a bounded range — reduce/map/filter as composition, `OPAQUE` — a
declared, run-refused black box that lets a whole *system* (incl. its
unverified parts) be modelled honestly, load/store, stack ops, `JMP`/`JZ`,
`CALL`, `DISPATCH` — a computed call whose target microtheory is chosen by a
popped selector from a jump table (vtable / interpreter-opcode-table / state
machine; dispatch as data, not branches), `RET`, `EMIT`, and `FETCH` — which reads the KB's own facts, by a
literal subject or a parametric `@var` so one rule serves any entity), and a
transpiler (`src/kb/transpile.py`) compiles it to native Python.

**Prior art**:
- Lisp / homoiconicity (McCarthy 1960) — code as data, but as
  S-expressions, without provenance, scope, or a reasoning layer.
- Datalog / logic programming — rules as data, but not imperative
  procedures with control flow, nor a queryable instruction stream.
- Stored procedures / rules engines — logic stored near the data, but in
  a separate language opaque to the query and reasoning layer.

**What's new here**:
- **Code, data, schema, and rules share one representation** — scoped,
  ordered, cited triples — so the boundary between the database, the
  schema, the rules engine, and the application code disappears.
- **The system reasons about its own algorithms.** Because a procedure is
  data, the machinery that derives facts can prove properties of programs
  (precedence closure, cycle/linearizability, data dependencies):
  computation is an object of inquiry, not an opaque verb. A parametric
  `FETCH @var|relation` makes this concrete — a rule's per-entity data
  dependencies are inspectable triples, declarable in advance and provably
  equal to what execution reads (`microtheory/parametric.py`).
- **Unbroken provenance through computation.** `FETCH` reads cited facts;
  the result re-enters as a cited fact the next rule consumes — end-to-end
  auditability no code-over-database stack provides.
- **Multi-framed, versioned algorithms.** Two versions of a procedure are
  two microtheories that coexist and are diffable, exactly as for
  contested facts.
- **Meaning and performance separated.** The triples are the canonical,
  inspectable source; speed (interpret → transpile → native) is a derived,
  regenerable cache — auditability is never traded for speed.
- **Safe by construction.** A closed opcode set (no `eval`, no host
  access), refusal of unknown opcodes, and step/recursion budgets that
  guarantee termination.

Eight assertion-backed worked examples (#3–#10) live in `src/microtheory/`
(`procedure`, `program`, `replicate`, `showcase`, `unified`, `complexity`,
`paradigm`, `fraud`), including exact replication of real Python, an
O(M²)→O(M) join, a provenance-native capstone, and end-to-end fraud
detection. Full guide:
[ORDERED_MICROTHEORIES.md](ORDERED_MICROTHEORIES.md).

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
| Schema-as-data / multi-framing preservation | Atom across 2,500 years of natural philosophy in `src/diachronic/` (temporal scope axis): 6 paradigms with distinct IS_A classifications, the famous indivisibility reversal queryable as a structural event. **Non-temporal** framing now first-class via the `Triple.scope` slot with scope-aware conflict detection — `src/microtheory/` carries one recession under four schools of economics at once, plus a worked example of how overlapping microtheories break a body of knowledge | nested/inheriting microtheory lattice (contexts that specialise parents); tooling for browsing the framing graph |
| Computation-as-data (ordered microtheories + executor) | `Triple.seq` makes a microtheory an ordered sequence; `kb.execute` runs it as a program (closed opcode set incl. `CALL`/`EMIT`/`FETCH`; termination + recursion guards); `kb.transpile` compiles to native Python (~32× the interpreter) with interpreter fallback; eight worked examples in `src/microtheory/` (#3–#10) incl. exact replication of real Python, a polynomial-speedup join, the provenance-native capstone, and end-to-end fraud detection | strings/collections in the VM; full Relooper for irreducible CFGs; native (C/LLVM/WASM) lowering |

The architecture is concrete and implementable at small scale. The
production-scale validation requires AI-driven extraction at 100M+
article scale maintaining the quality demonstrated at 1000-article
scale.

---

## What SKEAR contributes to the field of knowledge representation

A meta-positioning of everything above against the intellectual
history of KR, and against the current LLM moment in particular.

### The intellectual lineage

Knowledge representation has been a 60-year argument with itself
about how to balance two requirements that pull in opposite
directions: **inspectability and formal reasoning** on one side,
**scale and natural-language coverage** on the other.

Major attempts have lined up on one pole or the other:

  - **Frame systems** (Minsky 1974) and **conceptual graphs**
    (Sowa 1976) — inspectable structure, hand-built, didn't scale.
  - **CYC** (Lenat 1984-) — bet on hand-curation of common-sense
    knowledge. 40 years in, has ~25M assertions and remarkable
    inference power, but is constitutionally slow to build and
    expensive to license.
  - **Description Logic / OWL** (Brachman 1980s → W3C 2004) —
    formal foundations, decidable inference, no native path to
    construction at corpus scale.
  - **Wikidata / DBpedia / Freebase** (2000s-) — scale via
    community curation + automatic Wikipedia extraction; but
    one fixed schema, no multi-framing, no native reasoning.
  - **Knowledge graphs at scale** (Google 2012 et al.) —
    industrial production deployment, but mostly opaque pipelines
    and proprietary schemas.
  - **Vector embeddings / RAG** (word2vec 2013 → transformers
    2017 → vector DBs 2020+) — scale via learned representations,
    cheap to ingest, but no inspectability, no formal reasoning,
    and chunks rather than facts as the unit of retrieval.
  - **LLM-as-KB** (GPT-3 era, 2020+) — radical scale, fluent
    output, but knowledge stored in opaque weights with no audit
    trail, no provenance, no formal reasoning, and structural
    averaging across all training-data framings.

Each of these is a real contribution. None is a satisfactory
answer to the original question — how do we build a knowledge
artifact that is *inspectable, formally reasonable, audit-rich,
multi-framing-capable, AND practical to build at scale*?

### Where SKEAR sits

SKEAR is a synthesis position. It doesn't replace any of the
systems above; it takes a structural commitment that lets it use
their good parts without inheriting their limitations.

That commitment is the **construction-time AI / serve-time
deterministic split**, applied to KR as a primary architectural
move rather than as a side effect.

  - **At construction time**, AI does what AI is genuinely good
    at: reading unstructured text and producing structured facts.
    The output is plain JSON triples with provenance back to
    source sentences.
  - **At serving time**, the runtime is dictionary lookups and
    graph traversals over the materialized JSON. No AI in the
    loop. Sub-millisecond per query. Edge-deployable. No GPU,
    no JVM at query time.

Everything else SKEAR has — temporal validity, confidence,
conflict resolution, OWL DL via HermiT, schema-as-data,
multi-framing — is a feature added to this two-phase architecture
without disturbing it. The architectural promise doesn't degrade
as the capability surface grows; each new feature lives inside
the construction half.

### The seven things SKEAR contributes

Reading the seven numbered novelties above as a single body of
work, seven specific contributions to KR-as-a-field stand out:

  1. **A reconciliation of symbolic and sub-symbolic KR.** The
     construction/runtime split lets AI carry the load LLMs are
     actually good at (extraction, surface-form coverage) while
     keeping symbolic, inspectable, formally-reasonable artifacts
     at the serving layer. This isn't "use both"; it's a clean
     division of labour with a hard architectural boundary
     between them.

  2. **The CYC destination, reached differently.** CYC's
     architectural bet — that structured, inspectable, formally-
     reasonable artifacts beat opaque-weights generation when
     audit trails matter — was right and remains right. CYC's
     limitation was the construction cost (decades of hand-
     curation). SKEAR demonstrates that modern AI extraction
     closes that bottleneck. Same destination, modern path.

  3. **Schema-as-data with general scope axes.** The most
     architecturally novel contribution. Rather than committing
     to one schema and living within it (the historical KR
     posture), SKEAR puts the schema *in the same triple shape
     as the facts*, carrying its own scope (temporal, ideological,
     methodological, legal-perspectival, cultural, school-of-
     thought) and source attribution. The same subject can be
     structurally reassembled across framings. This is the
     structural answer to a problem nothing else in the field
     has cleanly addressed: multi-framing as a first-class
     capability, not a workaround.

  4. **A union of cross-cutting capabilities normally separate.**
     Per-fact provenance + Horn-clause + disjunctive + stratified
     negation + OWL DL via HermiT + Allen temporal algebra +
     uncertainty combinators + conflict resolution + distillation
     pipeline + bidirectional structure↔text. Specialists have
     each of these individually; SKEAR has them all coexisting in
     one Triple shape, each one composable with the others.

  5. **Cross-domain demonstrated on one engine.** Five fundamentally
     different data shapes (encyclopedic, conversational metadata,
     technical docs, noisy multi-source data, historical schema
     drift) reasoned over by exactly the same engine. The claim
     "KR is domain-agnostic when the architecture is right"
     becomes verifiable rather than aspirational.

  6. **A specific structural answer to LLM averaging.** The
     architectural feature most directly pointed at the failure
     mode of current AI. LLMs union all framings into one
     probability distribution and have no internal switch for
     "restrict to framing X." SKEAR has that switch as a scope
     query — and the switch operates on first-class data, not
     prompt-engineering. This is the dimension where no amount
     of RLHF, retrieval augmentation, or system-prompt
     scaffolding closes the gap.

  7. **Computation as first-class, auditable knowledge.** With
     ordered microtheories and the executor, an algorithm is not
     opaque code beside the data — it is scoped, ordered, cited
     triples in the same store, so one engine queries, reasons
     over, and executes it, with provenance unbroken from inputs
     through computation to derived facts. The database, the
     schema, the rules, and the code become one inspectable
     medium — the structural counter to both the code/data split
     and the LLM black box.

### What remains genuinely hard

Honest about what's open:

  - **Common-sense reasoning at CYC scale.** Some of CYC's content
    is physical-world and social-conventional knowledge that
    nobody writes down anywhere. You can elicit it from an LLM,
    but with quality issues. SKEAR could plug into CYC for this
    layer (the Pattern A integration described in
    `docs/COMPARISONS.md`); it doesn't replicate it natively.

  - **Higher-order logic.** CYC's CycL is HOL. SKEAR is first-
    order Datalog. Closing this would require a different rule
    language and a different reasoner; it's its own project.

  - **Microtheories as fully first-class contexts.** The scope-
    axis mechanism is a partial answer — it handles temporal,
    ideological, methodological, and similar axes. Full CYC-style
    nested context lattices with import / inheritance / inter-
    context logic would be its own architectural extension. Ordered
    microtheories (`Triple.seq`) and the executor's `CALL` (one
    procedure invoking another) are a concrete step toward this —
    procedure composition *is* microtheory composition — but full
    inheritance / lifting between contexts remains future work. See
    [ORDERED_MICROTHEORIES.md](ORDERED_MICROTHEORIES.md).

  - **Defeasible reasoning.** Defaults with exceptions ("birds
    fly, unless penguin") as a first-class construct. Stratified
    negation approximates; doesn't match.

  - **Industrial-grade production maturity.** SKEAR is small,
    clean, 50-stress-test-verified. Not the same as decades of
    industrial hardening that real production deployments
    eventually need.

  - **Scale validation.** All demonstrations are at the 1,000-
    article / 65-fact / 60-fact corpus scale. The claim that AI
    extraction closes the volume gap at 100M+ scale is plausible
    but not demonstrated.

### The architectural bet, in the field's terms

If knowledge representation is to remain useful in the LLM era,
it has to do five things at once:

  1. Use AI for the parts AI is good at — extraction, fluency,
     paraphrase coverage.
  2. Keep deterministic, inspectable artifacts at the serving
     layer — provenance, audit trail, sub-millisecond latency.
  3. Treat multi-framing — perspective, era, ideology, methodology,
     school of thought — as first-class data, not narrative.
  4. Scale without years of hand-curation.
  5. Stay edge-deployable, license-able, and cheap at query time.

SKEAR demonstrates that all five are simultaneously achievable
with current technology. The 60+ stress assertions and seven cross-
domain demos are the evidence; the architectural commitments
(construction/runtime split, schema-as-data, per-fact provenance,
soft-dependency adapter for full DL) are the mechanism.

The historical claim, then: **the future of practical knowledge
representation is neither LLMs alone nor symbolic KR alone, but
the construction-time-AI / serve-time-deterministic split, with
schema-as-data added to handle the multi-framing realities of
contested knowledge.** SKEAR is one working implementation of
that pattern, intended as a proof that the pattern is doable —
and an invitation to other implementations.

The field has needed this synthesis for at least a decade. The
LLM moment has made the synthesis both possible (AI extraction
is now cheap enough) and urgent (LLM averaging is doing real
damage in contested domains). What SKEAR shows is that the
synthesis is concrete, implementable, and already running.
