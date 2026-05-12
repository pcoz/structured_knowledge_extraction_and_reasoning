# SKEAR — Use cases

What currently uses LLMs that SKEAR (Structured Knowledge Extraction
And Reasoning) can address.

> **See also**: [README](../README.md) ·
> [ARCHITECTURE](ARCHITECTURE.md) ·
> [DEVELOPER_GUIDE](DEVELOPER_GUIDE.md) ·
> [COMPARISONS](COMPARISONS.md) ·
> [NOVELTIES](NOVELTIES.md) ·
> [LICENSE](../LICENSE.md)

A practical inventory of LLM/RAG use cases that this architecture can
take over, in part or in whole. For each: what's currently used,
where it falls short, how this addresses it, what an implementation
looks like, and what's gained.

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
