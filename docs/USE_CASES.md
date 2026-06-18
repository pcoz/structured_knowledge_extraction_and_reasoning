# SKEAR — Use cases

What currently uses LLMs that SKEAR (Structured Knowledge Extraction
And Reasoning) can address.

> **See also**: [README](../README.md) ·
> [ARCHITECTURE](ARCHITECTURE.md) ·
> [DEVELOPER_GUIDE](DEVELOPER_GUIDE.md) ·
> [COMPARISONS](COMPARISONS.md) ·
> [NOVELTIES](NOVELTIES.md) ·
> [ORDERED_MICROTHEORIES](ORDERED_MICROTHEORIES.md) ·
> [LICENSE](../LICENSE.md)

A practical inventory of LLM/RAG use cases that this architecture can
take over, in part or in whole. For each: what's currently used,
where it falls short, how this addresses it, what an implementation
looks like, and what's gained.

## Quick navigation

47 use cases, organised into eleven clusters. Jump to the one
closest to yours:

| Cluster | Use cases | Anchor in the project |
|---|---|---|
| [Regulated industries](#regulated-industries--hallucination-is-unacceptable) | 1-5 (legal, medical, financial compliance, pharma, tax) | strong hallucination-resistance |
| [Technical / developer documentation](#technical--developer-documentation) | 6-9 (product docs, API docs, code understanding, runbooks) | the `src/git_rag/` pattern |
| [Customer-facing knowledge](#customer-facing-knowledge) | 10-12 (support chatbots, HR, onboarding) | bounded curated answer space |
| [Internal knowledge management](#internal-knowledge-management) | 13-15 (corporate KGs, meetings, R&D) | relationship-aware retrieval |
| [Research and exploration](#research-and-exploration) | 16-18 (scientific literature, patents, news timelines) | multi-document reasoning |
| [Brand / character / conversational](#brand-character-and-conversational) | 19-21 (branded agents, character agents, brand-voice content) | the `src/ahab/` pattern |
| [Multi-source reconciliation / distillation](#multi-source-reconciliation--distillation) | 22-26 (MDM, sci-data integration, genealogy, reference data, news reconciliation) | the `src/distill/` pipeline |
| [Time-aware knowledge](#time-aware-knowledge) | 27-31 (regulatory over time, sanctions, drug labeling, land registry, contract obligations) | Allen interval algebra |
| [Audit-trail reconstruction](#audit-trail-reconstruction) | 32-35 (insider trading, patent priority, sci-misconduct, e-discovery) | per-sentence provenance |
| [Domain structural constraints](#domain-specific-structural-constraints) | 36-39 (BOMs, pharma formulation, hardware design, curriculum) | HermiT OWL DL adapter |
| [Multi-framing / preserving incompatible views of the same subject](#multi-framing--preserving-incompatible-views-of-the-same-subject) | 40-47 (history of science, evolving legal interpretation, evolving medical understanding, contested terminology, competing schools of thought, ideologically-divided analysis, legal-perspective framings, cross-cultural framings) | the `src/diachronic/` machinery generalised |

Use cases group by how much hallucination matters:

- **Regulated** — hallucination is a deal-breaker. Strongest fit.
- **Technical / documentation** — hallucination wastes time but is
  recoverable. Strong fit; mostly an efficiency / quality win.
- **Customer-facing knowledge** — hallucination damages trust.
  Strong fit if the answer space is curatable.
- **Internal knowledge management** — hallucination annoys staff.
  Strong fit.
- **Research / exploration** — hallucination corrupts the search
  process. Strong fit for structured exploration; less of a fit for
  open-ended discovery.
- **Brand / character / conversational** — hallucination off-brand
  is a reputation risk. Strong fit if the corpus is bounded.

Plus four additional clusters unlocked by the temporal, confidence,
conflict-resolution, distillation, and OWL DL capabilities:

- **Multi-source reconciliation / distillation** — multiple sources
  for the same set of facts; produce one canonical artifact.
- **Time-aware knowledge** — facts that hold in some periods but not
  others; "what was true on date X?" queries.
- **Audit-trail reconstruction** — who knew what when; legal,
  scientific, and compliance investigations.
- **Domain-specific structural constraints** — cardinality + complex
  class expressions, where the schema is itself part of the answer.

---

## Regulated industries — hallucination is unacceptable

### 1. Legal research / case law Q&A

**Currently uses**: LLM + retrieval over case law databases
(Harvey, CoCounsel, Westlaw AI). Lawyer asks "which cases cited X?"
or "what does precedent say on Y?"; the system retrieves and
summarises.

**Where it falls short**: synthesised citations are sometimes
fabricated; bar associations have sanctioned attorneys for filings
with hallucinated cases. Provenance is post-hoc.

**How this addresses it**: extract (case, cites, case) triples plus
(case, holding, statement) records during indexing. Every claim
served carries the originating case + paragraph. Multi-hop queries
(which Supreme Court cases cited cases that cited X?) are graph
traversals.

**Implementation**: cell-grammar tailored to legal prose (holding,
ratio, obiter); curated extractor per jurisdiction; standard
relation set (CITED_BY, OVERTURNED, AFFIRMED, DISTINGUISHED).

**Win**: lawyer-defensible answers. Bar-compliance assurance.

---

### 2. Medical clinical decision support

**Currently uses**: LLM-backed assistants (UpToDate AI, BMJ Best
Practice digital). Clinician asks "drug interactions with X for
patient with Y condition" or "guideline-recommended treatment for Z".

**Where it falls short**: LLM may state a contraindication that
isn't actually in current guidelines; clinician must verify every
claim; medico-legal risk of relying on hallucinations.

**How this addresses it**: structured corpus over current guidelines
(NICE, USPSTF, professional society publications). Every served
answer carries the guideline document + section. Reasoning rules
encode contraindication logic (drug X + condition Y → flag).

**Implementation**: per-guideline KB items with topic, indication,
dose, contraindication, evidence-grade, source-pubmed-id. Inference
rules handle interactions (drug-drug, drug-condition).

**Win**: medico-legal defensibility; no guideline citation can be
fabricated; reasoning is auditable.

---

### 3. Financial compliance / regulatory Q&A

**Currently uses**: LLM over regulator documentation (MiFID, SEC
rules, AML regulations). Compliance officer asks "do we need to file
X under Y regulation?"

**Where it falls short**: regulatory text is high-stakes; an
incorrect answer can mean a fine or jail. Citations need to be
exact, including subclauses.

**How this addresses it**: regulation extracted as (rule, condition,
obligation) triples with exact section/subsection provenance.
Multi-hop reasoning across cross-referenced regulations becomes
graph traversal.

**Implementation**: extractor per regulatory body; relation set
covers OBLIGATES, EXEMPTS, AMENDS, CROSS_REFERENCES. Per-fact
provenance includes the regulation, article number, sub-paragraph,
and version date.

**Win**: audit-trail compliance; deterministic regulatory
interpretation; version-controlled updates.

---

### 4. Pharmaceutical drug-information systems

**Currently uses**: LLM over drug monographs. Pharmacist or patient
asks about interactions, dosing, side effects.

**Where it falls short**: drug information must be exact. An LLM
that misstates a maximum dose is a clinical safety risk.

**How this addresses it**: structured monograph corpus per drug
with (drug, attribute, value) triples (max_dose, contraindication,
interaction_with, side_effect). Per-fact provenance to the FDA label
section.

**Implementation**: per-drug KB items keyed by INN/brand; relation
set INTERACTS_WITH, CONTRAINDICATED_IN, REQUIRES_MONITORING.

**Win**: clinical safety; deterministic drug-information lookup;
straightforward FDA-label audit.

---

### 5. Tax advice / corporate tax Q&A

**Currently uses**: LLM over tax codes and HMRC/IRS guidance. CFO or
accountant asks "is this expense deductible?"

**Where it falls short**: tax positions need to be defensible
under audit. Hallucinated rules cost real money.

**How this addresses it**: tax code extracted as (rule, applies_to,
treatment) triples. Inference rules handle conditional treatment
(if X applies, then Y rule overrides).

**Implementation**: per-jurisdiction KB; relation set DEDUCTIBLE_IF,
SUBJECT_TO_RATE, EXEMPT_UNDER. Provenance to specific tax code
section.

**Win**: audit-defensible advice; deterministic treatment of edge
cases.

---

## Technical / developer documentation

### 6. Software product documentation Q&A

**Currently uses**: LLM + vector RAG over manuals (the
`src/git_rag/` demo case generalised). Developer asks "how do I X?"

**Where it falls short**: synthesised commands are sometimes
syntactically wrong or invent flags that don't exist. Stack
Overflow's main complaint about LLM answers.

**How this addresses it**: this is exactly the `src/git_rag/` pattern
from this repo. Per-command KB items with (command, options,
examples, source-manual-section). Copy-pasteable, verified, sourced.

**Implementation**: see `src/git_rag/` for a working template.
Customise per product (Kubernetes, AWS CLI, PostgreSQL, etc.).

**Win**: developer trust; no hallucinated flags; instant updates as
docs change.

---

### 7. SDK / API documentation Q&A

**Currently uses**: LLM + retrieval over API docs. Developer asks
"how do I call X with Y parameter?"

**Where it falls short**: LLMs often confuse APIs across versions or
similar libraries (numpy/scipy, react/vue), suggest deprecated
methods, or hallucinate parameter names.

**How this addresses it**: per-method KB items with signature,
parameters, return values, deprecations, example, source-API-version.
Queries route to the right version automatically.

**Implementation**: extract from OpenAPI specs or doc-comment
sources directly (no NL extraction needed for structured API docs).
Version is a first-class slot.

**Win**: no API-version confusion; no deprecated-method suggestions;
no hallucinated parameters.

---

### 8. Code understanding / "how does this codebase work?"

**Currently uses**: GitHub Copilot Chat, Cursor, Sourcegraph Cody.
Engineer asks "where is this function called?" or "how is this class
used?"

**Where it falls short**: LLMs often invent call paths or misidentify
which code branch handles a case. Staticly answerable questions get
probabilistic answers.

**How this addresses it**: call-graph and definition-graph extracted
deterministically (by an AST walker, not an LLM). Graph queries
return exact answers.

**Implementation**: language-specific AST extractor builds the KB;
relations include CALLS, IMPORTS, DEFINES, OVERRIDES, INHERITS_FROM.
Standard for any compiled or AST-parseable language.

**Win**: exact answers; no hallucinated call paths; works on private
code without uploading to a cloud LLM.

---

### 9. Internal engineering wiki / runbook Q&A

**Currently uses**: LLM + vector RAG over Confluence / Notion. SRE
asks "how do we handle X incident?" or "where is the runbook for Y?"

**Where it falls short**: runbooks change frequently; vector RAG's
re-embedding cycle lags. Synthesis mixes outdated and current
guidance.

**How this addresses it**: structured runbook KB with (incident-type,
symptom, diagnostic-step, mitigation, escalation, source-runbook,
last-updated). Always-current, traceable answers.

**Implementation**: small curated KB per service; updates are
record-level edits, not re-embedding passes.

**Win**: SRE confidence in on-call answers; deterministic runbook
lookup; instant updates.

---

## Customer-facing knowledge

### 10. Customer support chatbots

**Currently uses**: Zendesk AI, Intercom Fin, in-house LLM chatbots.
Customer asks about product features, policies, troubleshooting.

**Where it falls short**: hallucinated policy answers ("yes, you can
return it after 90 days" when the actual policy is 30) cost real
money in honoured refunds and customer trust.

**How this addresses it**: structured FAQ / policy KB with (topic,
question-patterns, answer, source-document, applicability-conditions).
Every served answer cites the policy doc.

**Implementation**: curated KB per product line; topic/intent
matching identical to the `src/git_rag/` pattern. Optional: LLM
paraphrase pass on the deterministic output for tone (no facts added).

**Win**: policy-compliant answers; reduced honoured-hallucination
liability; audit trail for every interaction.

---

### 11. HR / employee handbook chatbots

**Currently uses**: in-house LLM over employee handbooks. Employee
asks about leave, benefits, expense policy.

**Where it falls short**: handbook policies vary by jurisdiction;
LLMs mix policies across regions. HR fielding tickets to correct
misinformation negates the cost saving.

**How this addresses it**: per-region structured HR KB with
(policy-type, eligibility, entitlement, process, source-handbook,
jurisdiction). Jurisdiction is a first-class slot.

**Implementation**: per-jurisdiction KB; matching routes to the
right jurisdiction based on employee profile.

**Win**: jurisdiction-correct answers; reduced HR escalation;
auditable.

---

### 12. Onboarding assistants

**Currently uses**: LLM that "knows" the company. New employee asks
"who does what?", "what tools do we use?", "how do I get access to
X?"

**Where it falls short**: LLM either has training cutoff lag or
needs continuous fine-tuning. Either way, it hallucinates current
team structures and tools.

**How this addresses it**: org-chart + tool-inventory + process KB
extracted from the company's actual systems. Always current.

**Implementation**: nightly extraction from HR system / SSO catalog /
service registry. Standard relations: REPORTS_TO, OWNS, ON_TEAM,
USES_TOOL.

**Win**: factually-current onboarding; no stale "your manager is
Alice" when Alice left two months ago.

---

## Internal knowledge management

### 13. Corporate knowledge graphs

**Currently uses**: Pinecone/Weaviate + LLM over internal documents.
Knowledge worker searches for "who's working on X?", "what's the
history of project Y?"

**Where it falls short**: corporate documents are heavy on
relationships (people, projects, products). Vector RAG flattens
this into chunks and loses the graph structure.

**How this addresses it**: extract the graph during indexing. The
KG IS the search interface, not a side artifact. Multi-hop queries
(people who worked on project Y under manager Z) become native.

**Implementation**: extractor over document corpus; alias-map links
entities across documents; standard org/project relations.

**Win**: relationship queries that vector RAG can't answer;
provenance built-in; faster onboarding for new hires.

---

### 14. Meeting / call-transcript analysis

**Currently uses**: LLM summarisation. "What did we decide?" "Who
took action item X?"

**Where it falls short**: summaries are sometimes wrong; action
items get reattributed; key decisions get paraphrased into something
softer.

**How this addresses it**: extract structured (speaker, statement,
type) triples where type ∈ {decision, action-item, question,
disagreement}. Every claim links to a transcript timestamp.

**Implementation**: per-meeting KB items; speaker-diarised
transcripts; structured action-item slots (owner, due-date,
follow-up).

**Win**: verifiable meeting outputs; action items traceable to who
actually said what; reduced post-meeting follow-up disputes.

---

### 15. Research / R&D internal documentation

**Currently uses**: LLM over lab notebooks, internal papers, prior
projects. Researcher asks "has anyone tried X?" or "what did we
learn about Y?"

**Where it falls short**: research conclusions are nuanced; LLM
summaries lose qualifications ("worked in conditions A, failed in
conditions B" becomes "worked").

**How this addresses it**: extract (experiment, condition, result,
confidence, source-document). Conditions are first-class slots;
qualifications preserved.

**Implementation**: per-experiment KB items; relation set INFORMS,
DISCONFIRMS, EXTENDS. Confidence and condition-context preserved.

**Win**: avoid re-running experiments because the prior result was
forgotten or mischaracterised; faithful capture of nuance.

---

## Research and exploration

### 16. Scientific literature exploration

**Currently uses**: Semantic Scholar / Elicit + LLM. Researcher asks
"what papers found result X?" or "what's the consensus on Y?"

**Where it falls short**: LLM-generated literature summaries
sometimes fabricate consensus where there is none; citations to
non-existent papers (Galactica-style) remain a documented failure.

**How this addresses it**: extract (paper, finding, methodology,
sample-size, confidence, source-doi) triples. Reasoning rules
identify supporting / contradicting findings.

**Implementation**: per-paper structured record (title, authors,
year, doi, abstract, key-findings, methodology, sample-size). Relation
set CITES, SUPPORTS, CONTRADICTS, EXTENDS.

**Win**: real citations only; structured-finding queries beyond
keyword search.

---

### 17. Patent search / prior art research

**Currently uses**: LLM-assisted patent search. Inventor or counsel
asks "what's the prior art for X?"

**Where it falls short**: hallucinated patent claims; misattributed
inventions; missed art due to terminology variation.

**How this addresses it**: structured patent KB with (patent, claim,
priority-date, inventor, assignee, cites, cited-by). Inference rules
identify chain-of-precedence and design-arounds.

**Implementation**: per-patent KB items; structured claim
decomposition; relation set CITES_BACK_TO, NARROWED_BY, EXPIRED_ON.

**Win**: cite-verifiable prior-art searches; no fabricated patent
numbers; design-around analysis becomes a graph query.

---

### 18. News / event timeline reconstruction

**Currently uses**: LLM over news articles. Journalist asks "what
happened with X?" or "construct timeline of Y".

**Where it falls short**: LLM-constructed timelines mix dates,
attribute events to wrong actors, conflate similar events.

**How this addresses it**: extract (event, date, location, actors,
outcome, source-article) records. Timeline construction is a
chronological query.

**Implementation**: per-article event extraction; date slots are
typed and arithmetic-friendly; multi-source consensus via voting
across articles.

**Win**: dates and actors correct; timeline traceable to specific
news sources; cross-source disagreement explicit (not silently
synthesised away).

---

## Brand, character, and conversational

### 19. Branded conversational agents

**Currently uses**: LLM fine-tuned on company tone-of-voice. The
chatbot "speaks like the brand" while answering customer queries.

**Where it falls short**: tone-of-voice and factual content are
intertwined in the weights. Updating one without affecting the other
is hard. Drift over time.

**How this addresses it**: structured corpus of approved brand
messaging; query matches retrieve approved content + chapter-style
provenance. Tone-of-voice is a property of the corpus (which is
human-approved), not of a model that can drift.

**Implementation**: see `src/ahab/` for the pattern — bounded
utterance corpus + theme matching + verbatim rendering. Replace
Ahab's quotes with approved brand messaging.

**Win**: no off-brand outputs; legal-approved content only;
auditable to which approved message went out.

---

### 20. Character agents for entertainment / education

**Currently uses**: LLM "play X" prompts (talk to historical
figures, fictional characters, etc.). Used in education, museum
installations, games.

**Where it falls short**: LLM-played characters say things the
character never said; in education this misinforms; in
entertainment it breaks immersion.

**How this addresses it**: this is exactly the `src/ahab/` demo.
Curated utterance corpus from the source material; theme-matched
retrieval; verbatim quotes only.

**Implementation**: see `src/ahab/` for the working template.
Generalises to any character with a sizable corpus of authentic
quotes.

**Win**: educationally faithful; entertaining; no
"Lincoln-on-Twitter" hallucinations.

---

### 21. Brand voice content generation

**Currently uses**: LLM with brand-voice prompts. Marketing team
generates social posts, email copy, ad text.

**Where it falls short**: the LLM drifts off-brand, requires manual
editing every time; iterating brand voice means re-prompting.

**How this addresses it**: template library + slot-filling
(approved verbs, approved sentiments, approved CTAs). Brand voice
is the template library; specific content fills the slots.

**Implementation**: cell-grammar applied to marketing: shape =
post-type, context = product-line, flavour = brand-voice variant
(formal / casual / premium). Slot fillings parameterise the
specifics.

**Win**: brand consistency by construction; no manual editing; A/B
test by varying slot fillings.

---

## Multi-source reconciliation / distillation

Use cases where the central problem is "I have N sources for the
same set of facts; produce one canonical, defensible artifact." The
distillation pipeline (`src/distill/purify.py`) is built precisely
for this shape: detect functional-property violations, resolve via
authority/recency/confidence chains, boost confidence on multi-
source agreement, prune low-authority noise.

### 22. Master Data Management (MDM)

**Currently uses**: hand-rolled rules, vendor MDM stacks (Informatica,
Reltio, Tamr) with hierarchical "golden record" survivorship rules,
optional LLM augmentation. Customer, product, supplier, employee
record deduplication and consolidation across CRM / ERP / billing /
support systems.

**Where it falls short**: survivorship rules are buried in vendor
config; provenance of "which source contributed which field" is
weak; LLM augmentation hallucinates merges that don't have source
evidence. Rule maintenance is its own headache.

**How this addresses it**: each source's records become Triples
tagged with source + valid_from/valid_to + confidence.
`apply_with_conflict_resolution` runs a chain policy (authority
wins → latest wins → highest confidence → surface for review),
emits a canonical KB plus a diagnostic record of every choice.
The corroboration boost (`noisy_or`) strengthens fields where
multiple sources agree.

**Implementation**: per-source extractor producing Triples,
`KB.source_authority` ranking, OWL functional axioms for fields
that should be unique per entity (email, SSN, tax ID),
inverse-functional axioms for unique identifiers, `ChainPolicy`
matched to the customer's existing survivorship preferences.

**Win**: every survivorship decision auditable to the policy +
inputs; no opaque vendor logic; the conflict-detection axioms ARE
the data-quality contract.

---

### 23. Scientific data integration across labs

**Currently uses**: ad-hoc Python notebooks, increasingly an LLM
asked to "reconcile these CSVs". Genomics, materials science,
clinical-trial multi-site studies, environmental monitoring, particle
physics — anywhere multiple labs measure the same phenomenon and
results must be combined.

**Where it falls short**: measurement units and conventions differ
between labs; outliers from instrument calibration drift get
silently included; the LLM glosses over discrepancies in synthesis;
no audit trail back to which lab said what.

**How this addresses it**: each measurement is a Triple with
`source_article` = the originating lab + protocol version,
`confidence` reflecting instrument precision, `valid_from`/`valid_to`
for measurement campaign dates. Functional-property axioms detect
measurements that differ beyond the within-experiment tolerance.
HighestConfidence / Authority chain policy picks the canonical
value; SurfaceForReview keeps disputed measurements for explicit
review.

**Implementation**: per-lab data adapter producing Triples,
per-measurement-type confidence policy, optional OWL cardinality
constraints (each sample has exactly one mass spectrum), distillation
pipeline producing the consensus KB.

**Win**: replication crisis exposure becomes a query; the canonical
artifact has every contributing lab in its provenance; outlier
measurements aren't quietly discarded — they're explicitly flagged.

---

### 24. Genealogy / family history reconciliation

**Currently uses**: spreadsheet-based hand reconciliation, vendor
trees (Ancestry, FamilySearch), occasional LLM "explain this branch
of my tree". Records from censuses, vital records, immigration logs,
DNA matches, church registers, family memorabilia.

**Where it falls short**: multiple sources give different birth/
marriage/death dates and places for the same person — sometimes a
real discrepancy, sometimes the same record transliterated differently
in different archives. LLM summaries pick one without justifying it.

**How this addresses it**: each record contributes Triples tagged
with archive name + record-set authority. Functional axioms on
BIRTH_DATE / DEATH_DATE / BIRTH_PLACE. Temporal scoping handles
the same person appearing in multiple records over their life.
Confidence reflects record reliability (church register = high,
oral tradition = lower). Distillation produces the consensus
family tree.

**Implementation**: per-archive Triple extractor, alias_map for
spelling variants (Smyth / Smith / Smithe), inverse-functional
axiom on government IDs where present, OWL DL for "every person
has exactly one biological mother and father" cardinality, chain
policy preferring primary documents over derivative ones.

**Win**: every fact in the tree has a citation; conflicts between
sources are surfaced not silently flattened; the consolidated tree
is reproducible from the inputs.

---

### 25. Reference data and standards versioning

**Currently uses**: vendor reference-data feeds (Bloomberg, Reuters,
LSEG), in-house standards repositories, hand-maintained mapping
tables. Currency codes, country codes, language codes, industry
taxonomies, regulatory identifiers — anywhere a controlled
vocabulary needs to be reconciled across multiple authoritative
sources.

**Where it falls short**: ISO updates, country renames (Burma →
Myanmar, Czechia formal name), currency redenominations, ticker
symbol changes — when these happen, downstream consumers see
silent inconsistency.

**How this addresses it**: each reference item is a Triple with
the issuing body as `source_article`, the publication date as
`valid_from`, the supersession date as `valid_to`. Authority-
ranked policy prefers official sources. Temporal queries return
the correct vocabulary for any given date.

**Implementation**: per-authority adapter, OWL functional axioms
on canonical-name / ISO-code mappings, temporal slots on every
mapping, AuthorityWinsPolicy preferring ISO / IETF / official
issuer over derivative sources.

**Win**: "what was the ISO 3166 code for Czechia on 2016-04-15?"
is a deterministic query; downstream systems get the right answer
for the right period; deprecated codes don't get silently used.

---

### 26. News-event reconciliation across outlets

**Currently uses**: aggregator feeds (Google News, GDELT), LLM
summarisation across articles. Reports of the same event from
multiple outlets with conflicting details (casualty counts, named
suspects, sequence of events).

**Where it falls short**: LLM summaries collapse the disagreement;
high-confidence reporting from one outlet is averaged with low-
confidence early speculation from another; corrections published
days later aren't reconciled with original reports.

**How this addresses it**: per-outlet extractor with reliability-
ranked authority; temporal slots reflecting when each claim was
made (so corrections come with their own publication date and
supersede earlier ones); functional axioms on event-specific
quantities (death toll, perpetrator name); chain policy preferring
later + higher-authority + multi-source-corroborated.

**Implementation**: outlet-keyed authority dict, event-anchored
extraction (each event becomes a subject), distillation pipeline
producing the consolidated event record.

**Win**: the artifact shows every outlet's claim with full
provenance; corrections supersede their predecessors temporally;
disputed claims surface for review rather than being averaged away.

---

## Time-aware knowledge

Use cases where the central question isn't "what's true?" but "what
was true on date X?" — historical compliance, regulatory
reconstruction, contract-state tracking. The temporal slots on
Triple (`valid_from`, `valid_to`) plus the Allen interval algebra
in `src/kb/temporal.py` make these queryable as first-class.

### 27. Regulatory compliance over time

**Currently uses**: legal-research databases (Westlaw, LexisNexis)
+ LLM Q&A over them. "Was this transaction compliant with the
regulation in force on its execution date?"

**Where it falls short**: LLMs often answer with the current rule
rather than the rule in force on the relevant date. Regulations
revise frequently (KYC thresholds, sanctions lists, capital
requirements). Date-specific compliance is exactly where
hallucination causes the most damage.

**How this addresses it**: each regulatory provision is a Triple
with `valid_from` = entry-into-force date, `valid_to` = repeal /
supersession date. `valid_at(triple, "2019-07-14")` returns the
rule that applied on that date. Multi-hop queries respect the
temporal validity at each hop — answers are reconstructed from
the regulatory body that was actually in force.

**Implementation**: per-regulator extractor with strict temporal
slots, OWL functional axiom on (rule, applicable-on-date) so two
versions don't apply simultaneously, point-in-time query
interface.

**Win**: defensible historical compliance answers; correct rules
for the right date; supersessions handled cleanly rather than
silently overwriting.

---

### 28. Sanctions / embargoes tracking

**Currently uses**: vendor sanctions screening (Refinitiv, Dow
Jones, OFAC files directly), increasingly LLM-augmented. Banks,
exporters, shipping companies must check transactions against
sanctions lists that change weekly.

**Where it falls short**: a transaction in 2018 against a then-
sanctioned entity must be evaluated against the 2018 list, not
today's. Vendor systems often only expose the current list.

**How this addresses it**: each sanction is a Triple with the
designating authority as source + `valid_from` (designation date)
and `valid_to` (delisting date, if delisted). Historical screening
queries the KB at the transaction date.

**Implementation**: OFAC / EU / UK extractor producing dated
Triples, temporal-aware screening function, complete history
preserved so a delisting doesn't erase the period of designation.

**Win**: regulatory investigations get historically-correct
answers; transactional reviews defensibly cite the rule in force.

---

### 29. Drug labeling and indication change tracking

**Currently uses**: FDA Orange Book + manual cross-referencing,
LLM-Q&A over current drug monographs. Approved indications,
contraindications, dosing ranges, black-box warnings — these
change over a drug's lifecycle.

**Where it falls short**: a clinical decision in 2015 should be
evaluated against the 2015 label, not the 2024 label that may
include warnings added post-market. Current-state lookups give
the wrong answer for any historical case.

**How this addresses it**: label revisions are temporal facts.
`(drug X, BLACK_BOX_WARNING, "Y")` is valid from one date to
another. Medico-legal review at a past date asks the KB to
reconstruct the label as it stood.

**Implementation**: FDA-label-revision-history adapter, temporal
slots on every label claim, point-in-time query API for med-mal
review.

**Win**: defensible "what was known on the prescribing date?"
answers; transparent label-evolution tracking; post-market safety
signals are temporally located.

---

### 30. Property / land registry over time

**Currently uses**: title insurance companies, public-records
search firms, county recorder offices. Ownership chain, easement
history, encumbrance history — all temporal.

**Where it falls short**: title abstractors do this work manually;
LLMs hallucinate ownership transitions; "did this easement exist
at the time of the disputed encroachment?" is a standard real-
estate-litigation question that current tooling answers poorly.

**How this addresses it**: ownership / lien / easement Triples
with `valid_from` = recording date, `valid_to` = release /
release-of-lien date. The Allen interval algebra answers complex
questions about overlapping interests.

**Implementation**: per-county recorder adapter, OWL functional
axiom on (parcel, OWNED_BY, owner) at a given time, the full
13-relation Allen algebra for "did easement A overlap with
encumbrance B?" questions.

**Win**: title research becomes a query; historical land-use
disputes get defensible point-in-time answers.

---

### 31. Contract-state and obligation tracking

**Currently uses**: contract-lifecycle-management tools (Icertis,
Ironclad), LLM-extraction over uploaded PDFs. Tracking which
obligations are active right now, which expired, which are about
to trigger.

**Where it falls short**: contracts have many overlapping clauses
with different effective windows; renewal options, payment
schedules, exclusivity periods, MFN clauses — each has its own
temporal extent. Current tooling treats the contract as one big
document, not as a set of temporally-scoped obligations.

**How this addresses it**: each clause becomes a Triple with
`valid_from`/`valid_to` derived from the clause's text. The KB
answers "what obligations are in force on date X?" as a temporal
query.

**Implementation**: per-clause Triple extraction, temporal
slot extraction from clause text, OWL functional axioms on
non-overlapping clause categories (exclusivity windows), Allen
algebra for "did this obligation overlap with that one?"

**Win**: obligation management at the clause level, not the
contract level; auto-detection of conflicting clauses; renewal-
trigger alerts as a scheduled query.

---

## Audit-trail reconstruction

Use cases where the question is "who knew what when, and how do we
prove it?" Per-sentence textual provenance + temporal slots + the
chain-of-derivation `Derivation` records make this a structural
property of every fact in the artifact.

### 32. Insider-trading investigations

**Currently uses**: e-discovery vendors (Relativity, Reveal),
manual review supplemented by LLM email classification. The
question is structural: did individual X have access to material
non-public information before transaction Y?

**Where it falls short**: LLM classification is fast but not
defensible in court; manual review is slow and expensive;
both struggle with the "what was the state of knowledge on date
X?" reconstruction.

**How this addresses it**: each piece of evidence (email,
meeting record, document access log) is a Triple with the actor
as subject, the information as object, the timestamp as
`valid_from`. The temporal layer + provenance answers "did
person X have access to information Y before timestamp Z?"
deterministically with full source-document traceability.

**Implementation**: corpus ingestion from e-discovery system,
actor / information / timestamp extraction, per-document
provenance, temporal query interface.

**Win**: every claim in an investigative finding traces to its
source document; the temporal reconstruction is defensible
without manual re-review; opposing counsel can re-run the same
query.

---

### 33. Patent priority disputes

**Currently uses**: patent attorneys with expensive manual
review of lab notebooks, prior-art searches, invention disclosure
forms. The question: who conceived of and reduced-to-practice a
specific invention first?

**Where it falls short**: priority disputes hinge on dates and
the specific content of each piece of evidence. LLMs introduce
unreliability into a process where unreliability ends careers.

**How this addresses it**: each piece of evidence is a Triple
(inventor, conceived-of / reduced-to-practice, invention-element)
with `valid_from` = the documented date and `source_article` =
the originating lab notebook page or memo. The full chain
becomes queryable.

**Implementation**: per-document evidence extractor, per-claim
inventor identification, temporal validity on every conception
/ reduction event, point-in-time query interface for "who got
to element X first?"

**Win**: a defensible audit-trail-of-evidence for litigation;
opposing counsel sees the exact provenance of each claim;
fabricated or backdated evidence can be cross-checked against
the documentary record.

---

### 34. Scientific misconduct investigations

**Currently uses**: journal editorial offices, university
research-integrity offices, ad-hoc panels. Manual review of
notebooks, raw data, drafts, correspondence.

**Where it falls short**: investigators piece together a
narrative from heterogeneous evidence; the timeline of who
knew what is critical and easy to get wrong; current tools
don't reconstruct it systematically.

**How this addresses it**: every piece of evidence (raw data
file, draft, email, meeting note) becomes a Triple with full
provenance + temporal slot. The KB answers questions like
"when did the authors know the result couldn't be replicated?"
or "who saw which version of figure 3 before publication?"

**Implementation**: ingestion of investigation evidence,
actor / content / timestamp triples, full provenance to source
files, chain-of-knowledge query interface.

**Win**: misconduct findings rest on a defensible reconstruction;
the institutional response is auditable; future similar cases
can re-run the same query pattern.

---

### 35. Discovery during litigation

**Currently uses**: e-discovery vendors with LLM-assisted
review. Massive document sets, often millions of items, where
the question is "produce every responsive item about topic X
from before date Y by custodian Z."

**Where it falls short**: LLM-assisted review produces responsive
sets with unclear provenance; opposing counsel challenges the
selection methodology; review costs scale with document count.

**How this addresses it**: each document becomes a set of
Triples; the responsiveness criteria become a structured query
over those Triples; the resulting set has full document-level
provenance + the exact query that produced it.

**Implementation**: per-custodian Triple extractor, topic
classifier producing structured tags, temporal slot derived
from document metadata, query-driven review API.

**Win**: discovery productions defensible to opposing counsel;
the exact criteria and selection methodology are part of the
artifact; review costs decouple from document count.

---

## Domain-specific structural constraints

Use cases where the schema itself is part of the answer:
cardinality, type relationships, complex class memberships. The
OWL DL adapter (HermiT via `src/kb/ontology_owl.py`) brings full
description-logic reasoning to the engine at construction time.

### 36. Manufacturing bills-of-materials (BOMs) and parts catalogs

**Currently uses**: PLM / ERP systems (Siemens Teamcenter, SAP,
Oracle Agile), CAD tooling. The question: does this product
specification self-consistently respect part counts, sub-assembly
constraints, material requirements?

**Where it falls short**: cardinality errors (a car spec with
3 wheels, a circuit with 2 ground pins instead of 1) get caught
only at integration time. LLM-assisted spec generation makes
this worse, not better.

**How this addresses it**: BOMs are knowledge graphs. Cardinality
axioms (`car has exactly 4 wheels`, `engine has at least 1
crankshaft`) become OWL declarations; HermiT verifies every
proposed configuration. Inconsistent specs surface at validation
time with named contradicting axioms.

**Implementation**: per-product OWL ontology with cardinality
axioms, BOM Triples for each specific product instance,
`hermit_enrich` for structural validation.

**Win**: structural errors caught at spec time, not assembly
time; the constraints are versioned alongside the product spec;
LLM-generated specs can be validated before manufacturing.

---

### 37. Pharmaceutical formulation validation

**Currently uses**: in-house chemoinformatics + manual review.
Each formulation has constraints: active-ingredient quantity
limits, excipient compatibility rules, dosage-form requirements.

**Where it falls short**: violations get caught in production;
late-stage validation expensive; rule maintenance scattered
across systems.

**How this addresses it**: formulation rules become OWL DL
axioms — cardinality on active ingredients, disjointness between
incompatible excipient classes, complex class definitions
(`InjectableFormulation ⊑ (Solution ⊔ Suspension) ⊓ ∃HAS_PRESERVATIVE.Approved`).
HermiT validates proposed formulations against the full rule set.

**Implementation**: pharma-grade OWL ontology, per-product
formulation Triples, HermiT validation in the design workflow.

**Win**: structural and regulatory compliance verified at
design time; the rule set is auditable to regulatory inspectors;
new formulations validated against the same rules as past
approvals.

---

### 38. Hardware design verification

**Currently uses**: EDA tooling (Synopsys, Cadence), in-house
rule checkers. Pin counts, signal integrity, fan-out limits,
clock-domain crossings.

**Where it falls short**: many constraints are encoded in vendor-
specific tool flows; cross-vendor portability is poor; LLM-
assisted design generation makes verification harder.

**How this addresses it**: structural design rules become OWL
axioms — cardinality on connection points, complex class
expressions for valid module compositions, disjointness for
incompatible signal types. HermiT verifies design integrity at
construction time.

**Implementation**: per-process-node OWL ontology, design
Triples extracted from netlists, HermiT verification as a
pre-fabrication gate.

**Win**: vendor-agnostic structural verification; design rules
explicit and auditable; LLM-generated designs validated before
fabrication commitment.

---

### 39. Educational curriculum modeling

**Currently uses**: LMS systems (Canvas, Blackboard), accreditation
spreadsheets. Course-prerequisite relationships, programme-of-study
constraints, accreditation-body requirements.

**Where it falls short**: prerequisite chains get broken silently
when courses are renumbered; accreditation requirements drift
out of sync with offerings; LLM-generated curricula don't
respect structural constraints.

**How this addresses it**: courses, prerequisites, learning
outcomes become Triples; programme constraints become OWL DL
axioms (`every BS degree requires ≥ 30 credits AT_LEVEL_300`).
HermiT verifies that a proposed programme satisfies all
constraints.

**Implementation**: per-institution OWL ontology, course-catalogue
Triples, HermiT validation of proposed programmes.

**Win**: accreditation compliance becomes a deterministic check;
prerequisite chains validated by construction; degree-programme
changes auditable to accreditors.

---

## Multi-framing / preserving incompatible views of the same subject

This is the **killer-application category** for SKEAR's
architecture. Use cases where the question isn't "what's the
answer?" but "how has the subject been understood — across eras,
schools of thought, ideologies, methodologies, cultures, or
practitioner communities — and how are those framings
structurally different?"

This is exactly the failure mode of LLMs. They train on the union
of all framings and produce a single smoothed answer. There's no
internal switch for "restrict to framing X"; the structure of
disagreement is averaged away in the weights.

SKEAR represents each framing as scoped data: the same subject can
carry incompatible IS_A classifications, properties, and organising
relations under different framings, with each framing's scope and
source explicit. Queries like "what did framing X hold about
subject Y?" return the framing-specific answer, sourced. The
`src/diachronic/` suite demonstrates this with historical eras as
the scope axis; the same machinery applies to any scope axis —
legal / jurisprudential perspective (common law vs civil law,
plaintiff vs defendant framing, originalist vs purposive
interpretation), ideological position, methodological tradition,
school of thought, cultural community, practitioner discipline.

### 40. History of science / paradigm-shift tracking

**Currently uses**: hand-written historiography, with LLM summary
assistance. "How has our understanding of [concept] evolved?"

**Where it falls short**: LLMs blend every era into one trained
distribution and produce a smooth synthesised answer. Era-specific
detail is lost; reversals (where a property held for centuries was
later rejected) get glossed over; the answer is not traceable to
period-specific sources.

**How this addresses it**: each historical claim is a Triple with
temporal validity and period-authoritative source. The schema
itself (the IS_A class, the organising relations) is data that
changes across eras. Queries like "what did Newton-era physics
classify atoms as?" return the period-correct answer, sourced.

**Implementation**: per-era extraction from primary sources,
temporal slots on every claim, IS_A relations as first-class
schema-as-data, conflict-detection rules that respect temporal
scoping.

**Win**: defensible historical accuracy; the textbook-physics smooth
answer is no longer the only available answer; paradigm shifts
become queryable events rather than narrative summaries.

---

### 41. Evolving legal / regulatory interpretation

**Currently uses**: legal databases + LLM summarisation. "How has
the court interpreted statute X over time?"

**Where it falls short**: the interpretation isn't just a fact that
changes — the framework (which constitutional doctrine applies,
which precedents control, which canons of construction) shifts
across eras. LLMs collapse all of this into one synthesised reading.

**How this addresses it**: each interpretive claim is a Triple
attributable to its court + opinion + date; the doctrinal
framework (which classifications hold, which precedents are
controlling) is itself data with temporal validity. The same
statute carries different IS_A classifications across doctrinal
eras (e.g., commerce-clause expansion / contraction).

**Implementation**: per-opinion extraction, temporal validity from
opinion date to overruling date, doctrine-as-data on every claim,
DL constraints for what counts as a controlling precedent in
which era.

**Win**: legal-history research becomes a query; doctrinal shifts
become traceable events; the interpretive lineage of any statute
is reconstructible from the structured record.

---

### 42. Evolving medical understanding / shifting diagnostic categories

**Currently uses**: medical literature search, history-of-medicine
scholarship. "What did clinicians believe about [condition] in
[year]?"

**Where it falls short**: diagnostic categories themselves change
(hysteria → various modern diagnoses; homosexuality removed from
DSM; Asperger's merged with ASD). Etiological theories shift
(humoral → germ theory → genetic). LLMs answer with current
classification regardless of the asked-about era.

**How this addresses it**: diagnostic categories are temporally-
scoped IS_A relations; etiological explanations are
period-authoritative Triples. The DSM-IV view of a condition is
different data from the DSM-5 view — temporally distinct, both
preserved.

**Implementation**: per-edition DSM extraction, per-period medical-
literature extraction, temporal slots reflecting when each
classification was active, AuthorityWinsPolicy by clinical
guideline authority for the period.

**Win**: medico-legal review of historical care decisions gets the
classification in force at the time; the history of psychiatry,
endocrinology, oncology becomes a queryable record rather than a
narrative summary.

---

### 43. Contested terminology / concept tracking across communities

**Currently uses**: corpus-linguistics tooling (Sketch Engine,
COCA) + LLM-assisted summary. "How has the meaning of [term]
shifted?"

**Where it falls short**: meaning shift isn't only lexical — it's
ontological. "Liberal" in 1850 indexes different commitments than
"liberal" in 2020. Different IS_A class, different co-occurring
concepts, different rhetorical opponents. LLMs flatten this into
a tidy etymology that misses the structural reorganisation.

**How this addresses it**: each period's usage produces Triples
with the period's IS_A, properties, and co-occurring concepts.
Vocabulary-drift analysis (the same machinery as
`src/diachronic/analyse.py`) surfaces the structural difference
in how the term was assembled.

**Implementation**: per-period corpus extraction, temporal
validity per usage, schema-as-data so IS_A is a first-class
historical record, drift-detection report comparing eras.

**Win**: scholarly research on conceptual history becomes
defensible and reproducible; the way a term was used in 1850 is
structurally distinguishable from its use in 2020, not just
described as "different."

---

### 44. Competing schools of thought within a discipline

**Currently uses**: review papers, LLM-assisted comparison.
"What does cognitive science / economics / psychology say about
[phenomenon]?" Each discipline has multiple internally-coherent
schools — behaviorist vs cognitivist vs psychoanalytic in
psychology; Keynesian vs Austrian vs MMT in economics; cognitive
vs phenomenological vs enactivist in cognitive science.

**Where it falls short**: LLMs collapse the schools into a
synthesised "discipline says" answer that no school would
actually endorse. Each school's distinctive framing — what counts
as evidence, which causal mechanism dominates, what the basic
unit of analysis is — gets smoothed.

**How this addresses it**: each school's view is its own scope.
Same phenomenon, different IS_A classifications (a depression is
a chemical imbalance in one framing, a maladaptive cognitive
schema in another, an unresolved transference in a third), each
with the school's methodology and source corpus attributed.
Queries can ask "what does school X hold?" without contaminating
the answer with school Y's framing.

**Implementation**: per-school corpus extraction, scope axis =
school identifier, IS_A and HAS_EXPLANATION relations per school,
methodology attributed as source-authority, schools as named
contexts.

**Win**: scholarly literature reviews become reproducible queries
rather than narrative summaries; comparative work across schools
can rest on structural data; no school's framing gets averaged
into the dominant one.

---

### 45. Ideologically-divided analysis of contested events

**Currently uses**: think-tank reports, journalism, LLM-assisted
summarisation. "What happened during the [contested event]?"
Politically-charged subjects — wars, regime changes, economic
crises, social movements — get framed differently by different
ideological communities.

**Where it falls short**: LLMs converge on a centrist synthesis
that satisfies no one and obscures the structural disagreement.
Or worse, they adopt one framing wholesale (whichever dominated
their training corpus) and present it as neutral.

**How this addresses it**: each ideological framing is its own
scope. Same event, different causal attributions, different
moral classifications, different relevant antecedents. Queries
return the framing-specific account with full source provenance;
side-by-side comparison surfaces the actual disagreement rather
than smoothing it.

**Implementation**: per-framing source extraction (each ideological
community has its canonical sources), framing axis as the scope,
disjointness axioms between competing causal-attribution classes
(when they're genuinely incompatible), conflict-detection without
forced resolution (SurfaceForReviewPolicy preserves both).

**Win**: comparative analysis defensible to all sides; the
structural disagreement is data, not a synthesis casualty;
researchers can audit which sources contributed to which framing.

---

### 46. Legal / jurisprudential perspective — same case, different framings

**Currently uses**: litigation databases, brief-drafting tools,
LLM-assisted "what does the case say?" Q&A. The same set of facts
gets framed differently by plaintiff vs defendant, by originalist
vs purposive interpretation, by common-law vs civil-law tradition,
by liability theory (negligence vs strict liability vs intentional
tort).

**Where it falls short**: LLMs synthesise a single "the law says"
answer that obscures the framings each side argues from. A
defendant-side perspective and a plaintiff-side perspective on
the same fact pattern are STRUCTURALLY different ways of carving
the facts — what counts as a duty, what counts as causation, what
counts as damages. LLMs flatten this into one neutral-sounding
account that's useless for arguing either side.

**How this addresses it**: each legal framing is its own scope.
Same fact pattern, different IS_A classifications (the same
conduct is "reasonable care" under one theory, "negligent" under
another, "intentional" under a third), different applicable
precedents per framing, different elements that count as
satisfied. Queries can ask "from the plaintiff's framing, what
controlling precedents apply?" or "from an originalist framing,
how does this statute read?" — each answer scoped to its framing
with full source citation.

**Implementation**: per-framing extraction (each brief's framing
becomes a scope), framing axis on the schema, precedent-applicable
relations scoped per framing, statute-interpretation as scoped
data (originalist text vs purposive text vs textualist text are
different IS_A classifications of the same statute).

**Win**: litigation research becomes structurally honest about
the framing being used; opposing-counsel arguments can be
reconstructed defensibly; the SAME fact pattern legitimately
supports multiple framings, and the KB preserves that without
forcing convergence on a "neutral" account.

---

### 47. Cross-cultural framings of the same phenomenon

**Currently uses**: anthropology, comparative-religion scholarship,
medical-pluralism literature. Same phenomenon — illness, death,
kinship, justice, time — gets organised differently in different
cultural traditions. Western biomedicine vs traditional Chinese
medicine vs Ayurveda on the body. Common-law vs civil-law on legal
reasoning. Different theological traditions on the same text.

**Where it falls short**: LLMs default to whichever tradition
dominated their training data and treat alternatives as deviations
to be "explained." The structural fact that each tradition has its
own internally-coherent way of carving up the phenomenon gets lost.

**How this addresses it**: each tradition is its own scope on the
schema. Same phenomenon, different IS_A classifications, different
organising relations, different things counting as evidence. The
KB doesn't pick one as canonical — it preserves each framing
with its own community-internal coherence and authoritative
sources.

**Implementation**: per-tradition corpus extraction with
tradition-specific source-authority, tradition as a scope axis on
the schema, the same disjointness handling as ideological framings
(when traditions genuinely classify things into incompatible
categories), no forced canonicalisation across traditions.

**Win**: comparative scholarship defensible by construction; no
tradition gets implicitly demoted to "alternative"; clinical /
legal / theological systems get structurally-faithful representation
in cross-tradition work.

---

## Where this does NOT replace LLMs

Several use cases stay LLM territory. The architecture is wrong for
them:

- **Open-ended creative writing** — fiction, poetry, brainstorming.
  No bounded corpus to extract from.
- **Code generation from natural-language specs** — the LLM is doing
  generative pattern composition, not retrieval.
- **Translation** — surface-form transformation across languages;
  hard to factor into discrete facts.
- **Conversational small-talk** — no underlying knowledge to ground
  on.
- **Multi-turn agentic planning** — long-horizon planning over
  open-ended goals.
- **Image / audio understanding** — the input modality is wrong for
  text-extraction pipelines (though an analogous cell-grammar over
  images is the natural extension).

For these, LLMs are the right tool. This architecture is for
**fact-grounded knowledge serving and retrieval**, not creative
generation.

---

## Choosing between this and LLM + RAG

| if your use case has... | choose this | choose LLM+RAG |
|---|---|---|
| Hallucination is unacceptable | ✓ | ✗ |
| Per-fact provenance required | ✓ | ✗ |
| Audit trail required | ✓ | ✗ |
| Bounded, curatable corpus | ✓ | either |
| Open-ended natural-language synthesis | ✗ | ✓ |
| Need creative or generative output | ✗ | ✓ |
| Multi-hop reasoning core to queries | ✓ | weak fit |
| Sub-second latency required | ✓ | possible (cost) |
| Edge / on-prem only deployment | ✓ | hard |
| <$1K-$10K construction budget | ✓ | depends |
| Want vendor-independence | ✓ | depends |
| Don't have engineering capacity to curate | ✗ | ✓ |
| Tone-of-voice is the main product feature | possible | ✓ |
| Multi-language with surface-form needs | weak fit | ✓ |
| Need point-in-time queries ("what was true on date X?") | ✓ | ✗ |
| Multi-source contradictions need reconcilable answers | ✓ | ✗ |
| Confidence / uncertainty must propagate through reasoning | ✓ | ✗ |
| Structural constraints (cardinality, complex class expressions) | ✓ (via HermiT) | ✗ |
| Need a defensible canonical artifact from noisy inputs | ✓ (distillation) | ✗ |
| Existing investment in Cyc / OWL / SHACL ontologies | ✓ (DSL maps cleanly) | weak fit |

For most use cases above the answer is **a combination**: this
architecture handles the factual layer; an LLM handles surface
fluency or open-ended portions. The LLM consumes the structured
output (no synthesis hallucination); the structured layer constrains
what the LLM can say.

---

## The conservative deployment pattern

Start with a clear narrow domain. Build the KB. Deploy with the LLM
disabled (deterministic answers only). Add LLM paraphrase / tone
post-processing once the underlying answers are right. Resist
mixing the layers — the LLM-synthesis hallucination is what this
architecture exists to avoid; reintroducing it negates the value.
