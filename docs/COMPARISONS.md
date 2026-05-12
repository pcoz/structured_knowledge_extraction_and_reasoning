# Comparisons — how this differs from similar technology

> **See also**: [README](../README.md) ·
> [ARCHITECTURE](ARCHITECTURE.md) ·
> [DEVELOPER_GUIDE](DEVELOPER_GUIDE.md) ·
> [USE_CASES](USE_CASES.md) ·
> [NOVELTIES](NOVELTIES.md) ·
> [LICENSE](../LICENSE.md)

A side-by-side with the main alternatives. Each section: what the
other system does, what it does well, where it falls short, how this
project differs.

For "what's new vs prior art" framed as architectural claims see
[NOVELTIES.md](NOVELTIES.md). For the architectural design itself
see [ARCHITECTURE.md](ARCHITECTURE.md). For the practical API and
recipes see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md). This doc is
the user-facing "how does this compare to X?" reference.

---

## Vector RAG (Pinecone, Weaviate, Chroma, Qdrant, LangChain, LlamaIndex)

**What it does**: chunk documents, embed each chunk into a vector
space, retrieve top-k chunks by cosine similarity given a query
embedding, feed retrieved chunks to an LLM for synthesis.

**What it does well**:
- Generic — works on any text without per-domain engineering
- Mature tooling, well-funded vendors, easy to deploy
- Handles surface-form variation through embedding similarity
- Good when "find me the most semantically similar chunk" is enough

**Where it falls short**:
- **Multi-hop failure**: facts in different chunks can't be bridged
  by the retriever. The LLM has to synthesise the connection, which
  is unreliable.
- **Hallucination during synthesis**: the LLM in the loop fabricates
  plausible-but-wrong details even when the retrieval is correct.
- **No fine-grained provenance**: a chunk is tens of lines. Tracing
  a specific claim to a specific source line requires manual effort.
- **Embedding storage cost**: chunks × dimensions × float32 ≈ GBs
  for large corpora.
- **Update lag**: re-embedding on doc updates is expensive.

**How this project differs**:
- Per-fact (not per-chunk) provenance. Every triple traces to a
  specific source sentence.
- Multi-hop is graph traversal, not retrieval-then-synthesis.
- No embedding storage; the KB is a JSON of structured records.
- Updates are JSON edits, picked up on next load.
- Trade-off: requires curation/extraction effort per domain that
  vector RAG sidesteps.

---

## GraphRAG (Microsoft, 2024)

**What it does**: use an LLM at indexing time to build a knowledge
graph from documents (entities, relationships, community summaries).
At query time, traverse the graph and use an LLM to synthesise the
final answer.

**What it does well**:
- Handles multi-hop better than vector RAG (graph is explicit)
- Captures cross-document relationships during indexing
- Good for thematic / "summarise what's in this corpus" queries

**Where it falls short**:
- **LLM at both ends**: noisy indexing + hallucinating synthesis.
  The graph is only as good as the LLM's extraction; the answer is
  only as faithful as the LLM's rendering.
- **Opaque graph quality**: hard to audit the auto-built graph
  without manual review of each node.
- **Synthesis hallucination preserved**: even with a clean graph,
  the LLM synthesising the answer can add unsourced details.

**How this project differs**:
- Indexing is regex + entity-span + curated patches (deterministic
  and inspectable), or AI extraction with the AI output verified
  against the source.
- Rendering is deterministic — no LLM in the synthesis path.
  Responses are the retrieved record formatted with provenance,
  not generated text.
- Inference is Horn-clause rules (plus declarative disjunctive
  rules and stratified negation-as-failure) run to fixpoint, with
  full proof trees — not LLM chain-of-thought.
- Trade-off: less fluent natural prose in responses; gain is full
  auditability.

---

## LLM-as-KB (GPT-4, Claude, Llama, Gemini)

**What it does**: store knowledge implicitly in model weights.
Answer questions by generating text conditioned on the question.

**What it does well**:
- Conversational fluency, instruction following, common-sense
  reasoning across vast topical range
- No explicit indexing or retrieval step needed
- Handles paraphrase, ambiguity, and creative requests well

**Where it falls short**:
- **Hallucination is fundamental**: facts come out of weights via
  stochastic sampling. RLHF mitigates but doesn't solve.
- **No provenance**: claims aren't tagged to sources; citations are
  often hallucinated post-hoc.
- **Knowledge cutoff**: frozen at training time, stale within months.
- **Update cost**: re-training a frontier model is ~$100M and
  6+ months.
- **Auditability**: zero. Cannot ask "where did the model learn X?"
- **Cost per query**: $0.01-0.10 (cloud API).
- **Latency**: 1-10 seconds per query.

**How this project differs**:
- Knowledge is explicit. The KB JSON is human-readable.
- Hallucination is structurally impossible at serve time (response
  is retrieved, not generated).
- Updates are JSON edits, instant.
- Auditability is automatic — every claim carries source provenance.
- ~$0 per query, sub-millisecond latency.
- Trade-off: bounded by the curated/extracted corpus; can't
  extemporise on topics outside the KB.

---

## Wikidata / DBpedia / Freebase (large-scale curated KGs)

**What it does**: massive knowledge graph (~100M entities, ~1B
statements in Wikidata) built from a mix of human curation and
automated extraction from Wikipedia.

**What it does well**:
- Coverage of named entities and their basic properties (dates,
  places, relationships) is enormous
- Stable identifiers (QIDs) enable cross-system linking
- SPARQL queryable, well-documented schema
- Free, open data

**Where it falls short**:
- **No surface text generation**: Wikidata is a destination, not a
  representation of how facts are stated in prose. You can't go
  "render this fact as a Wikipedia-style sentence" from Wikidata.
- **No compression role**: facts and their natural-language sources
  are separate artifacts.
- **Schema friction**: contributors must learn Wikidata's property
  system; not a drop-in for a new domain.
- **Incompleteness on long-tail entities** and obscure relations.

**How this project differs**:
- Bidirectional: structure ↔ text. The same artifact serves both
  query and surface reconstruction.
- Per-fact provenance includes the source SENTENCE (not just the
  source article).
- Cell-grammar layer makes surface phrasing variants explicit,
  enabling natural-prose rendering.
- Trade-off: this project's KB is 6 orders of magnitude smaller
  than Wikidata. Different problem scales.

**Could be combined**: Wikidata facts could be loaded into this
project's KB format and rendered through the cell grammar. The
reverse is also true.

---

## OpenIE / TextRunner / ReVerb / Stanford OpenIE

**What it does**: automatic relation extraction from text. Produces
(subject, relation, object) triples from unstructured prose, usually
via pattern matching, dependency parsing, or BERT-fine-tuned models.

**What it does well**:
- Open vocabulary — no fixed schema, captures any relation expressed
  in text
- Scales to large corpora
- Useful as input to downstream KG construction

**Where it falls short**:
- **Precision is low** (~30-50% on Wikipedia at scale)
- **Relation names are surface-form-y**: same semantic relation
  gets multiple labels ("was born in", "is from", "originated in")
- **No structural typing**: an entity in subject position is just
  a string; no Person / Place / Date discrimination
- **Hallucinated triples**: the extractor produces facts that look
  plausible but aren't supported by the source

**How this project differs**:
- Schema-constrained extraction: facts that don't fit a registered
  interaction type are flagged as residual, not silently included.
- Typed slots: subjects and objects flow through a typed entity
  dictionary.
- Verb-anchor matching is high-precision (the cost is recall — we
  miss some facts). Curated patches close the gap.
- Trade-off: less open-domain than OpenIE; more reliable on covered
  domains.

**Could be combined**: OpenIE as a first-pass extractor with this
project's schema as a validator. Only emit OpenIE triples that fit a
known interaction type.

---

## FrameNet / PropBank / AMR (semantic role labelling)

**What they do**: analyse sentences into semantic frames or role
structures. FrameNet has ~1,000 frames with typed role fillers
(e.g., the COMMERCE_BUY frame has Buyer, Seller, Goods, Money
roles). AMR builds per-sentence semantic graphs.

**What they do well**:
- Linguistically principled — built on decades of frame-semantics
  and predicate-argument research
- Precise relational typing at the sentence level
- Cover a wide range of predicates

**Where they fall short**:
- **Analytic, not generative**: tell you what a sentence MEANS, not
  how to compress it or render it back
- **No discourse-level state**: per-sentence only, no article- or
  conversation-level state tracking
- **No compression role**: the frame analysis IS the destination
- **No flavour conditioning**: a frame is universal across speakers
  and domains

**How this project differs**:
- The cell-grammar's shape × context structure is FrameNet-like
- Adds flavour as a third axis (Aristotle vs Einstein vs Mick Jagger
  prose share frames but use different phrase distributions)
- Adds the rendering direction (frames → surface text)
- Adds discourse/article-level state via the alias map and
  pronoun-resolution step
- Trade-off: smaller frame inventory than FrameNet's ~1,000;
  domain-specific rather than universal

---

## CYC / OWL / Description Logic (symbolic AI)

**What they do**: hand-built ontologies + formal inference engines.
CYC has been built since the 1980s with millions of curated facts.
OWL is the W3C standard for description-logic ontologies.

CYC is the closest architectural relative to this project — both
reject "LLM-as-database" in favour of an inspectable, hand-curatable,
formally-reasonable knowledge artifact. As the inference plumbing
in this project has matured, the meaningful comparison has shifted:
not "what can each do?" but "where do their architectures actually
sit relative to each other?" The three tables below frame that.

### What's now matched

| CYC capability | This project's equivalent |
|---|---|
| Class hierarchies, subsumption, equivalence, disjointness | OWL DSL: `subclass_of`, `equivalent_classes`, `disjoint_with`. Transitive subclass closure via fixpoint. |
| Property characteristics (transitive, symmetric, inverse, functional, inverse-functional, sub-property) | All seven implemented in `src/kb/ontology.py`. Compiler emits rules into the same engine. |
| Domain / range typing | `ontology.domain(...)`, `ontology.range(...)` — compiled rules emit `IS_A` facts. |
| Forward-chaining inference over rules | `apply_all_rules_to_fixpoint` with stratified semantics. |
| Per-fact provenance | Every Triple carries `source_article` + `source_sentence_idx`; every Derivation carries rule + inputs + "since X therefore Y" explanation. **Stronger** than CYC here — sentence-level vs CYC's microtheory-level. |
| Temporal reasoning | Full Allen interval algebra (13 relations + composition + inversion) in `src/kb/temporal.py`. Engine propagates intervals through derivation chains. |
| Confidence / certainty tracking | Confidence slot on every triple; noisy-AND/OR/min combinators; engine propagation automatic. |
| Contradiction detection | Functional / inverse-functional / disjoint-class axioms surface `CONFLICT_*` markers. |
| Conflict resolution | Six pluggable policies (Authority, Latest, HighestConfidence, KeepAll, SurfaceForReview, Chain). CYC's microtheory-based resolution and our policy-based resolution achieve similar outcomes through different means. |
| Knowledge curation / purification | `src/distill/` suite — full noisy-in-clean-out pipeline. CYC has this only as a manual editorial process; ours is programmable. |

### What CYC still has that we don't

| CYC capability | Why we can't match without new machinery |
|---|---|
| **Higher-order logic** (predicates over predicates, predicates as arguments) | Our schema is first-order Datalog. Real HOL needs a different rule language. |
| **Microtheories / context logic** | Facts holding in some contexts but not others. We have no first-class "context" slot — facts are global. Temporal scoping is the closest analogue but it's one specific kind of context. General microtheories are their own architectural change. |
| **Defeasible reasoning with explicit defaults** | "Birds fly, unless penguin" with proper override semantics. We can approximate via stratification (override rule at stratum 1) but not cleanly. CYC has it as a first-class construct. |
| **Modal operators beyond time** (knows / believes / desires) | We have temporal modality only. Epistemic and doxastic modality aren't represented. |
| **~25 million curated common-sense assertions** | CYC's actual KB content. We have demo-scale data plus the 1000-article Wikipedia slice. The architectural bet — that modern AI extraction closes this gap — remains an open hypothesis at scale. |
| **Production-grade theorem prover** | Decades of optimisation on real workloads. Our engine is small, clean, and 38-assertion-tested but not industrially battle-hardened. |
| **Cardinality / complex class restrictions** (full OWL DL) | `min/maxCardinality`, `someValuesFrom` under open-world semantics. We have the closed-world subset; full DL needs an external reasoner like HermiT. |

### What we now have that CYC doesn't

| Our capability | Why this matters |
|---|---|
| **Per-sentence textual provenance** | CYC tracks microtheory; we track the exact source sentence. Stronger audit trail. |
| **Bidirectional structure ↔ text** | CYC's KB is divorced from prose. Ours can render structured facts back to natural language via the cell-grammar layer. |
| **Inspectable, plain-text JSON artifact** | Open in a text editor, grep it, diff it. CYC's runtime form is harder to spot-check. |
| **Sub-millisecond serving with no runtime AI/network** | CYC's reasoner is meant for query-time inference. Ours separates construction from serving — runtime is dictionary lookups. |
| **Edge-deployable, stdlib-only runtime** | CYC needs the CYC runtime. We need Python. |
| **Cross-domain demonstrated** | Wikipedia, Moby-Dick utterance corpus, Git docs, astronomical multi-source purification — same engine, four shapes. CYC is one big general-purpose KB. |
| **Programmable distillation pipeline** | Noisy multi-source corpus → clean canonical KB in one orchestrated call (`apply_with_conflict_resolution`). CYC has manual editorial processes. |
| **Allen interval algebra as a first-class primitive** | Standard temporal formalism, exposed as named predicates + composition table. CYC has temporal reasoning but its representation is more ad hoc and the algebra isn't surfaced as cleanly. |
| **38 assertion-backed stress scenarios across four test suites** | Pinning engine properties. Reproducibility check is `python src/kb/reason.py && python src/kb/ontology.py && python src/kb/conflict.py && python src/distill/purify.py`. |

### Where the gap actually sits now

The **inference machinery gap** has narrowed to three things: higher-
order logic, microtheories, and defeasibility. Those are deep
semantic features, not just plumbing — closing each is a real
architectural project.

The **knowledge volume gap** is unchanged. CYC has 25M curated
assertions; we have tens of thousands. The architectural bet — that
modern AI as a construction-time extractor closes this at scale —
remains an open hypothesis, not a demonstrated outcome.

The **production maturity gap** is also unchanged. Different points
on the curve: CYC is industrially battle-hardened; ours is small,
clean, deterministic, and assertion-tested.

What's *new* is that we now have **operational primitives CYC
doesn't focus on**: deterministic conflict resolution as a first-
class pipeline step, Allen algebra exposed as the temporal API,
programmable distillation of noisy corpora, and per-sentence
provenance throughout. These aren't substitutes for CYC's strengths
— they're capabilities that emerge from the "AI extracts,
deterministic code serves" architectural bet, and they're things
CYC-the-product doesn't have because CYC was designed for a
different problem (handcrafted common-sense reasoning over a single
big KB) than we're designed for (programmable multi-source knowledge
processing across diverse corpora).

One-line summary: **CYC is deeper in inference and content; we're
broader in pipeline mechanics and cleaner in the construction-time /
serve-time split.** The architectures aren't converging — they're
occupying different positions in the same design space, and what's
narrowed is the gap on the dimensions where they overlap.

**Could be combined**: this project's KB could be exported as OWL
for use with formal reasoners. OWL inference (description-logic
subsumption, transitive/symmetric/inverse-property axioms beyond
what our DSL already covers, cardinality restrictions) could augment
the Horn + disjunctive + stratified-negation rules already in
`src/kb/reason.py`. CYC-style microtheories could be added as a
context slot on the Triple schema — that's a separable extension
the current architecture would accept cleanly.

---

## Neo4j / Amazon Neptune / generic graph databases

**What they do**: store and query property graphs at scale.
Cypher / Gremlin / SPARQL query languages.

**What they do well**:
- Operationally mature — scale to billions of edges
- Rich query languages with built-in graph algorithms (shortest
  path, PageRank, community detection)
- ACID transactions, replication, the usual enterprise database
  features

**Where they fall short**:
- **They're stores, not pipelines**: ingest is your problem;
  rendering is your problem; reasoning is your problem
- **Setup cost**: deploying a Neo4j cluster is real infrastructure
- **No native text integration**: a graph database doesn't know
  anything about Wikipedia or natural language

**How this project differs**:
- A complete pipeline (extract → store → reason → render) rather
  than just a store
- In-memory JSON ships with the demos; no infrastructure setup
- For larger-scale deployment, the KB JSON could be exported to
  Neo4j and queried with Cypher. This project's value is the
  pipeline; the storage layer is interchangeable.

**Could be combined**: production deployments at scale should
probably back the KB with Neo4j (or similar). Keep this project's
extraction and reasoning layers; swap the JSON for Neo4j.

---

## BERT-based event extraction (ACE, TAC KBP, DyGIE++, etc.)

**What it does**: fine-tune a transformer to extract events from
text, where events have typed triggers, argument roles, and entity
mentions.

**What it does well**:
- Higher precision than OpenIE on covered event types
- Captures argument-role structure (not just subject-relation-object)
- Trained on benchmark datasets with defined evaluation

**Where it falls short**:
- **Schema constrained to training data**: extending to new event
  types requires fine-tuning
- **Inference cost**: per-sentence GPU pass at indexing time
- **Output is structured but not bidirectional** (no rendering)

**How this project differs**:
- Schema is explicit code (you can read and edit it) rather than
  implicit in model weights
- Rendering direction is supported
- Construction is regex-fast or AI-extraction-fast, not transformer-
  inference-bound
- Trade-off: lower recall than a well-trained event extractor on
  the domains it was trained for

---

## Summary table

| feature | Vector RAG | GraphRAG | LLM-as-KB | Wikidata | OpenIE | FrameNet | CYC/OWL | Neo4j | **This** |
|---|---|---|---|---|---|---|---|---|---|
| Multi-hop reasoning | poor | partial | implicit (CoT) | yes (SPARQL) | post-hoc | n/a | yes (DL) | yes (Cypher) | **yes (BFS/chain)** |
| Hallucination resistance | mitigated | partial | none | n/a | low precision | n/a | yes | n/a | **structural** |
| Per-fact provenance | chunk-level | weak | none | per-statement | source span | per-frame | per-axiom | optional | **per-sentence** |
| Surface text rendering | n/a | LLM synthesis | generative | none | none | none | none | none | **deterministic** |
| Auditable | weak | weak | none | yes | partial | yes | yes | yes | **yes** |
| Update lag | re-embed | re-index | retrain | edit | re-extract | n/a | edit | edit | **instant** |
| Latency per query | 0.5-2s | 1-5s | 1-10s | <1s | n/a | n/a | varies | <1s | **<1ms** |
| Edge-deployable | partial | no | no | partial | n/a | n/a | yes | partial | **yes** |
| Construction effort | low | medium (LLM) | training | huge (curation) | low (auto) | huge (curation) | huge | low | medium (curate or AI-extract) |
| Open vocabulary | yes | yes | yes | partial | yes | no | no | n/a | partial |
| Formal reasoning | no | weak | no | weak | no | no | yes (DL) | weak | **yes (Horn + disjunction + stratified negation + OWL DSL + Allen temporal algebra + uncertainty combinators, all at fixpoint)** |

---

## What this project is NOT

To set expectations:

- **Not a general-purpose LLM replacement**. For open-ended creative
  generation, code generation, or fluent conversational charm, use
  GPT-4 / Claude / Llama.
- **Not a vector RAG replacement** for use cases where "find me
  similar chunks" is the right behaviour (search, recommendation,
  semantic browse).
- **Not at scale yet**. The demos use 1,000 articles. Production
  validation at 100M+ scale is open work.
- **Not a graph database**. For >10M-triple deployments use Neo4j /
  similar; this project's pipeline can populate them.
- **Not a frontier-model architecture**. The architectural claims in
  NOVELTIES.md about frontier LLMs are *implications*, not
  demonstrations. The frontier-scale validation is open work.

---

## When this is the right choice

The structured-retrieval architecture wins when one or more of these
matter:

1. **Hallucination is unacceptable**. Regulated industries (legal,
   medical, financial, compliance), high-stakes technical
   documentation, safety-critical systems.
2. **Audit trails are required**. Every claim must trace to its
   source line.
3. **Multi-hop reasoning is core**. Questions that require combining
   facts from different parts of the corpus.
4. **Edge / on-prem deployment**. No cloud LLM API calls.
5. **Cost per query matters**. Serving millions of queries per day at
   ~$0 each instead of $10K/day in API fees.
6. **The corpus is bounded and curatable**. Software manuals,
   regulatory texts, character-specific dialogue, scientific
   literature. Not all of the open web.
7. **Update latency matters**. Add a fact in seconds, not retrain
   in months.

For these cases this architecture is the better profile.
