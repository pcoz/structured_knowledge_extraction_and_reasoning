# SKEAR — Structured Knowledge Extraction And Reasoning

**Answers your customers, regulators, and staff can trust — sourced
from your own documents, with every claim traceable to the sentence
it came from.**

*SKEAR* /ˈskɪər/ — a small, deterministic reasoning engine that
turns unstructured documents into a queryable, inspectable,
provably-traceable knowledge artifact. Optional AI augmentation at
construction time (extraction, curation); zero AI in the loop at
query time.

> **Copyright © Edward Chalk.** The architecture and source code are
> the original work of Edward Chalk, released under the
> [MIT License](LICENSE.md).

> **Repository:** *SKEAR* is the project's short name. The repository
> slug stays `structured_knowledge_extraction_and_reasoning` — the
> long form is search-discoverable and the existing clone URL,
> forks, and issue links keep working.

## At a glance

A representative interaction with a SKEAR-backed system over the
demo Wikipedia corpus:

> **You:** *Who tutored Alexander the Great?*
> **System:** Aristotle. *(Source: article "Aristotle", sentence 0.)*

> **You:** *How are Alexander the Great and Socrates connected?*
> **System:** Alexander ← (TUTORED) ← Aristotle ← (TUTORED_BY) ←
> Plato ← (TUTORED_BY) ← Socrates. *(All three relations sourced
> to the original articles.)*

> **You:** *What did Aristotle's student conquer?*
> **System:** Persia, Egypt, the Persian Empire. *(Each conquest
> sourced to the article "Alexander the Great".)*

Every answer points back to the sentence it came from. Every
derivation has a "since X therefore Y" trail. Every query runs in
under a millisecond, with no AI in the loop. If the answer isn't in
your documents, the system says so rather than fabricating one.

## The problem with today's AI answers

Large language models are remarkable, but they have three habits that
make them hard to deploy in serious settings:

- **They make things up.** A confidently worded answer can be wholly
  invented, and there is no built-in way to tell the difference.
- **They can't show their working.** When a model gives an answer,
  it can't point to the specific document, page, or sentence it came
  from.
- **They change their mind.** Ask the same question twice and you can
  get two different answers.

For a marketing chatbot, those are quirks. For a bank, a hospital, a
law firm, a regulator, or anyone whose answers have to stand up to
scrutiny, they are blockers.

## What this project offers

A different way of putting AI to work: **use AI once, up front, to
read your documents and extract the knowledge into a clean,
structured form. After that, the system answers from the structured
knowledge — no AI in the loop, no hallucinations, every answer
traceable.**

The result is a system that:

- **Won't invent facts.** If the answer isn't in your documents, it
  says so.
- **Shows its working.** Every answer points back to the exact source
  sentence.
- **Gives the same answer every time.** Deterministic and auditable.
- **Runs cheaply at query time.** No API calls, no GPU bills — a
  query takes under a millisecond.
- **Can reason, not just retrieve.** It chains facts across
  documents to answer questions whose answers no single document
  contains — transitive lineages, multi-relation aliasing,
  closed-world "what's missing?" queries, time-aware "when did this
  hold?" queries, paradigm-shift detection across historical eras
  — each derived fact carrying a complete proof trail.
- **Knows what it doesn't know.** Facts can carry validity windows
  and confidence scores. Sources can be ranked by authority. When
  sources contradict, a pluggable resolution policy (latest-wins,
  highest-confidence, authority-wins, or surface-for-review)
  decides what to do — deterministically, at construction time.
- **Preserves multiple ways the same thing has been understood.**
  The schema itself — classifications, organising relations, which
  properties count, what counts as a fact at all — is data with a
  scope and a source. The same subject can be assembled differently
  by different eras, legal or jurisprudential perspectives,
  ideologies, methodologies, schools of thought, cultural
  traditions, or practitioner communities; the differences are
  queryable rather than averaged away. LLMs blend every framing
  into one synthesised answer; SKEAR preserves the structural
  disagreement. **This is the architectural feature most directly
  pointed at the failure mode of current AI.**

## Scope: what SKEAR is, what it isn't, and why that's the point

SKEAR is, by design, a **crystal**: a small, deterministic knowledge engine
whose every fact is traceable to the sentence it came from, whose reasoning
shows its working, and which **refuses rather than guesses** at the edge of what
it knows. Its standout virtues — provenance on facts *and* derivations, full
determinism, refusal at the edge, and a transparent end-to-end pipeline in one
readable codebase — are rare even among peers, and the extraction layer is now
sharper still: clean facets, no possessive/duplicate fuzz, no self-referential
triples, unambiguous aliasing, and clause-correct (optionally dependency-parsed)
extraction.

**What it is trying to be:** bounded, auditable, reproducible — a foundation you
can fully inspect and trust within its limits.

**What it is *not* trying to be:** a web-scale knowledge graph (Wikidata), a
maximal-coverage neural extractor, a full first-order / OWL reasoner (Cyc), or a
fluent general conversationalist (an LLM). It does not chase scale, coverage, or
eloquence.

**Why:** those goals are bought with statistical approximation, and
approximation has no edges. A system optimised to always produce a plausible
answer cannot also tell you, reliably, when it has *none*. A crystal is defined
by its edges; blur them for breadth and it stops being a crystal.

**Why that makes it useful — because it knows what it isn't.** A tool that knows
its own boundary can be trusted *within* it: when SKEAR answers, the answer is
sourced and reproducible; when it doesn't know, it says so, in a well-defined
way. That is exactly what lets it be deployed where confident-but-wrong is
unacceptable (law, medicine, finance, compliance, audit), and what makes it a
sound foundation for softer layers built on top — because a foundation must be
definite. Systems that try to be everything end up trustworthy nowhere; SKEAR
is deliberately good at being *something*, and honest about the rest. Its worth
comes from being definite, not big.

## Who this is for

| If you... | This helps because... |
|---|---|
| Run a regulated business (finance, legal, medical, pharma) | Every answer is sourced and reproducible — audit-ready by construction |
| Have a deep technical product or manual | Customers and staff get instant, accurate answers from your own documentation |
| Field the same questions over and over in support | Answers come from your knowledge base, not a model's training data |
| Want a brand-safe conversational assistant | The assistant can only say things that exist in the corpus you curated |
| Worry about hallucination, data leakage, or AI cost at scale | None of those apply at query time, because there is no AI at query time |
| Need to reconcile facts from many sources — internal wikis, regulatory filings, vendor docs, legacy databases | The distillation pipeline detects contradictions, weighs sources by authority, corroborates multi-source agreement, and produces one clean canonical artifact |
| Need an audit trail of facts that change over time — policies, regulations, product specs, employment records, drug labels | Triples carry validity windows; "what was true on date X" is a deterministic query |
| Need to flag uncertain or disputed information rather than pretend it's settled | Confidence scores propagate through reasoning chains; disputed facts surface with their conflict signature attached |
| Need to preserve multiple ways the same subject has been framed — different perspectives, eras, ideologies, methodologies, schools of thought, schools of practice | Each framing is preserved as structured data with its own schema, sources, and validity scope; the differences between framings are queryable rather than smoothed into one narrative |
| Need a procedure, business rule, or calculation that is auditable, versionable, and runs deterministically | It becomes an *ordered microtheory* — scoped, cited, ordered triples — run by the executor; algorithm and data share one store and one provenance trail, and a transpiler compiles it to native code as a cache. See [docs/ORDERED_MICROTHEORIES.md](docs/ORDERED_MICROTHEORIES.md) |

## What's in the repository

Seven cross-domain working demonstrations — each runnable in a few
seconds without any setup, API keys, or external dependencies — plus a
suite on **ordered microtheories** (procedures and programs as data):

### A Wikipedia knowledge graph

A graph built from 1,000 Wikipedia articles, containing 2,169 facts
and 2,561 entities. You can ask it questions like:

- "Who tutored Alexander the Great?"  →  *Aristotle*
- "What were Aristotle's student's conquests?"  →  *Persia, Egypt, the
  Persian Empire*
- "How are Alexander the Great and Socrates connected?"  →  *Alexander
  ← Aristotle ← Plato ← Socrates*

It can also **infer new facts** from existing ones — for example,
deducing that Socrates is an intellectual ancestor of Alexander even
though no single article says so directly. The reasoner runs eleven
rules to fixpoint (transitive closure, disjunctive antecedents, and
stratified absence-checks), turning 2,169 base facts into 5,684 —
each derived fact tagged with the rule, inputs, and "since X
therefore Y" explanation that produced it.

### A conversational demo (Captain Ahab)

Ask 13 questions about whales, the sea, and obsession, and receive
verbatim answers from Melville's *Moby-Dick*. The point isn't the
literary content — it's that the assistant **physically cannot
fabricate**, because it can only return text from the curated source.

### An enterprise documentation assistant (Git manual)

Ask 15 developer questions about Git, get accurate, source-grounded
answers from the manual. A miniature of how a real product would
serve customer or internal support: feed it the manual, get an
assistant that answers from it and nothing else.

### A diachronic-analysis demo

A new fifth suite that tracks **how the same subject material has
been assembled differently across time** — using the atom across
2,500 years as the worked example. The same word "atom" gets
structured as an indivisible philosophical principle (Greeks), a
rejected hypothesis (Aristotelians), a small hard sphere (Newton),
a chemical accounting unit (Dalton), a composite structure with
parts (Rutherford / Bohr), and a quantum wave function
(Schrödinger / Heisenberg). At each era the IS_A class changes,
the properties change, the organising vocabulary changes — the
schema itself is part of the historical record.

The analyzer surfaces schema drift, property reversals (Rutherford
1911 making "indivisible" wrong after 2,000 years of consensus),
vocabulary drift, and authorial lineages. Embeds prose on why this
kind of representation matters for knowledge management and why
LLMs — which blend every era into one trained distribution —
struggle with it specifically. *(See `src/diachronic/`.)*

### A knowledge-distillation pipeline

A deliberately-noisy astronomical-facts corpus (the same physical
data described by seven sources of varying authority: IAU,
NASA, peer-reviewed papers, a 1985 Britannica, a 1965 encyclopedia,
a blog post, and a textbook) is purified end-to-end. The pipeline
detects 28 functional-property conflicts (different masses, different
classifications), resolves them by a chain of policies (authority,
then recency, then confidence), boosts confidence on facts
corroborated by multiple independent sources, prunes low-authority
noise, and produces one clean canonical KB with every change
auditable. Handles the famous edge case correctly: Pluto's two
classifications (Planet before 2006-08-24, Dwarf Planet from
2006-08-24) are temporally disjoint and so NOT flagged as a conflict
— both survive as valid facts of different eras.

### A multi-framing demo (microtheories)

A sixth suite for **non-temporal** framing — where the scope axis is a
school of thought or legal framing rather than a historical era. The
worked example carries one recession under **four incompatible schools
of economics at once** (Keynesian, Austrian, monetarist, MMT): each is a
microtheory with its own classification, cause, prescription, and unit of
analysis, all on the same subject. Because conflict detection is
scope-aware, the four incompatible classifications **coexist without being
flagged as contradictions** — yet a contradiction asserted *within* a
single school is still caught. A companion demo (`breakage.py`) shows the
pathology: when microtheories **overlap** — a context-specific fact
mis-scoped to global, or two contexts merged into one — the coherent body
of knowledge collapses into contradiction, and re-separating the scopes
repairs it. *(See `src/microtheory/`; uses the `Triple.scope` slot.)*

### Ordered microtheories — procedures, programs, and code-as-data

`Triple.seq` makes a microtheory an *ordered sequence*: a procedure, or —
when its members are opcodes — an executable program. SKEAR's executor
(`src/kb/execute.py`) runs it over a closed instruction set (including
`CALL` for composition/recursion, `EMIT` for sequence output, and
`FETCH` to read the KB's own facts), and a transpiler
(`src/kb/transpile.py`) compiles it to native Python as a derived cache.
Algorithms then live as scoped, cited triples beside the facts and rules,
so the same engine queries, reasons over, and executes them with
provenance intact. Eight worked examples in `src/microtheory/`
(`procedure`, `program`, `replicate`, `showcase`, `unified`, `complexity`,
`paradigm`, `fraud`) range from replicating real Python exactly to a
polynomial-speedup join, a provenance-native capstone, and end-to-end
fraud detection. Full guide:
**[docs/ORDERED_MICROTHEORIES.md](docs/ORDERED_MICROTHEORIES.md)**.

### An ingestion / import-consistency demo

A seventh suite for the **import** problem: what happens when you merge data
from several "authoritative" sources into one record and the result is
self-contradictory. Four vendor/CMMS/audit exports for a single pump load
without error and look individually fine — but computing the logical closure
on import surfaces **three contradictions**, each traced back to the exact
source sentences. One is **latent**: no single triple is wrong, yet the
taxonomy's subclass closure proves the pump is classified as *both* a
rotodynamic and a positive-displacement machine (physically impossible). The
demo then shows the real difficulty — a consistent merge must discard sourced
facts, or surface them for review — and notes that scoping these as
microtheories would be wrong, because they are data errors, not legitimate
framings. *(See `src/ingestion/`.)*

### Same reasoning engine, seven different data shapes

Each demo above ships with a companion reasoning script
(`src/kb/reason.py`, `src/ahab/reason.py`, `src/git_rag/reason.py`,
`src/distill/purify.py`) that runs the same engine — fixpoint
iteration, OWL-style declarative axioms, disjunctive rules,
stratified negation-as-failure, temporal validity intervals,
confidence propagation, and conflict-resolution policies — over its
corpus. The Wikipedia KB derives intellectual-descent chains, family
progenitors, and historical contemporaries; resolves real conflicts
in the source data using a chain policy. The Moby-Dick corpus derives
theme co-occurrence networks with frequency-weighted confidence
attenuating through long transitive chains. The Git knowledge base
derives multi-hop topic navigation declaratively and classifies
operations by automation safety. The distillation pipeline
demonstrates the full purification sweep: noisy in, canonical out.

The point: structured reasoning is domain-agnostic. The same code
paths drive all seven; what differs is how each domain projects its
records into the standard triple form.

## How it works, in plain language

Three layers, built once and then reused at query time:

1. **Read your documents and extract structured knowledge.** This
   step uses AI (or, in this demo, hand-crafted patterns) to read
   text and pull out facts in a consistent format — *who did what,
   when, where, to whom*. This is the one place AI is used.

2. **Apply your business rules.** Combine extracted facts using
   logical rules of three kinds: simple chains (*"if A trained B and
   B trained C, then A is an intellectual ancestor of C"*), rules
   with alternative triggers (*"X influenced Y if X taught Y OR Y is
   X's intellectual descendant"*), and rules that fire on what's
   missing (*"flag any parent with no recorded parent of their own"*).
   The system applies these rules until no new facts can be derived,
   each derived fact tagged with the rule, inputs, and reasoning that
   produced it.

3. **Serve answers.** Queries run against the structured knowledge.
   No AI, no API calls. Every answer carries its source.

This split — **AI at construction time, no AI at query time** —
is what makes the system auditable, cheap, fast, and trustworthy.

## How SKEAR relates to Cyc

The closest architectural relative to SKEAR is **Cyc** — the long-
running symbolic-AI project built since the 1980s. Both reject
"LLM-as-database" in favour of an inspectable, hand-curatable,
formally-reasonable knowledge artifact. As SKEAR's inference
machinery has matured, the meaningful comparison has shifted from
"what can each do?" to "where do they sit relative to each other?"

**What's matched.** SKEAR now covers most of what Cyc covers on
inference plumbing: class hierarchies, property characteristics
(transitive / symmetric / inverse / functional / inverse-functional /
sub-property), domain/range typing, forward-chaining with fixpoint,
contradiction detection, conflict resolution, knowledge curation as
a programmable pipeline, and — via the shipped HermiT (OWL DL)
adapter — full description-logic reasoning including cardinality
restrictions, complex class expressions, and open-world inference.

**What Cyc still has that SKEAR doesn't.** Higher-order logic
(predicates as arguments), defeasible reasoning (defaults with
exceptions), modal operators beyond time (knows / believes /
desires), ~25M curated common-sense assertions, and decades of
production-grade theorem-prover hardening. Each is a deep
architectural feature in its own right. *(Microtheories — facts
holding in some contexts but not others — are now partly covered: a
`Triple` carries an optional `scope` tag and conflict detection is
scope-aware, so incompatible framings coexist without contradiction.
This is the lightweight per-fact form, not Cyc's full nested,
inheriting context lattice.)*

**What SKEAR has that Cyc doesn't.** Per-sentence textual
provenance (stronger than Cyc's microtheory-level), bidirectional
structure ↔ text via the cell-grammar layer, inspectable plain-text
JSON artifacts, sub-millisecond runtime serving with no AI or JVM
in the loop, edge deployability, seven cross-domain demonstrations
(Wikipedia / Moby-Dick / Git docs / astronomical distillation /
diachronic eras / multi-framing microtheories / import-consistency
auditing), a programmable distillation pipeline, the full Allen
interval algebra as a first-class primitive, flat microtheory scoping
on the Triple, and 60+ assertion-backed stress scenarios across eight
suites.

### Integration possibilities

The two systems compose cleanly without either having to change.
Two practical patterns:

- **Cyc as construction-time enricher.** Run SKEAR's extraction
  pipeline; for each entity, query Cyc for common-sense facts
  about it; adapt CYC's assertions into SKEAR's Triple shape;
  merge into the KB via the existing conflict module. Ship the
  enriched artifact — Cyc is gone after construction. Runtime
  serving is unchanged.

- **SKEAR's KB as ABox for a Cyc microtheory.** Treat Cyc as the
  TBox (schema + common-sense + microtheories), SKEAR's extracted
  KB as the ABox; run Cyc's inference engine over the union; pull
  derived facts back with microtheory-attributed provenance.
  Gains defeasibility, modal logic, and microtheory-scoped facts
  that SKEAR's engine doesn't natively express.

The OWL DL adapter (`src/kb/ontology_owl.py`) already demonstrates
the construction-time-enricher pattern against HermiT — same
architectural shape would work for Cyc, with the licensing and
translation costs noted in `docs/COMPARISONS.md`.

For the full structured comparison plus integration analysis, see
[docs/COMPARISONS.md](docs/COMPARISONS.md).

## Trying it out

If you have Python installed, every demo runs with a single command
(no setup, API keys, or external dependencies). The `kb/`, `ahab/`,
`git_rag/`, `distill/`, and `diachronic/` demos run as scripts
(`python src/kb/reason.py`, …); the `microtheory/` and `ingestion/`
suites run as modules from `src/` (`python -m microtheory.analyse`,
`python -m ingestion.analyse`). The technical reader will find the full
list in [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md).

## Where to go next

- **[docs/USE_CASES.md](docs/USE_CASES.md)** — concrete applications
  across regulated industries, customer support, internal knowledge,
  technical documentation, research, and conversational products.
  For each: where current approaches fall short, how this changes
  things, what's gained. Also: an honest section on where this does
  *not* replace LLMs.
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — the design,
  rationale, and full glossary of terms.
- **[docs/COMPARISONS.md](docs/COMPARISONS.md)** — how this compares
  to vector RAG, knowledge graphs, LLM-as-database, and other
  alternatives.
- **[docs/ORDERED_MICROTHEORIES.md](docs/ORDERED_MICROTHEORIES.md)** —
  the complete guide to *ordered microtheories*: representing
  procedures, programs, and code-as-data as scoped, ordered, cited
  triples, run by the executor (`kb.execute`) and compiled by the
  transpiler (`kb.transpile`). Full opcode reference and the eight
  worked examples (incl. end-to-end fraud detection).
- **[docs/NOVELTIES.md](docs/NOVELTIES.md)** — what this contributes
  that isn't standard in the field. Closes with a substantial
  "What SKEAR contributes to the field of knowledge representation"
  section positioning SKEAR against the 60-year history of KR
  (frame systems → Cyc → OWL → knowledge graphs → vector RAG →
  LLM-as-KB) and articulating the architectural bet for KR in the
  LLM era.
- **[docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)** — for
  engineers: code map, data model, API reference, recipes for
  extension.
- **[RELEASE_NOTES.md](RELEASE_NOTES.md)** — datetime-stamped record
  of what's been added and changed.
- **[LICENSE.md](LICENSE.md)** — MIT License.
