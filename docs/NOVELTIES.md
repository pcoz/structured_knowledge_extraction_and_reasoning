# Novelties — what's architecturally different

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
| Causal state tracking | 11 rules over 1000-article KB; fixpoint dispatch with stratified negation-as-failure and disjunctive rules; 10 stress-test scenarios | richer rule library; semi-naive evaluation for scale |
| Bidirectional byte-exact | 17/17 phenocryst sentences + 25/25 full article | groundmass byte-exactness via trained LM |
| Provenance + reasoning + generation | 6 working interfaces (3 query + 3 cross-domain reasoners over Wikipedia, Moby-Dick, Git docs) | production-grade extraction at 100M-article scale |

The architecture is concrete and implementable at small scale. The
production-scale validation requires AI-driven extraction at 100M+
article scale maintaining the quality demonstrated at 1000-article
scale.
