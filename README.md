# Structured Knowledge Extraction and Reasoning

**Answers your customers, regulators, and staff can trust — sourced
from your own documents, with every claim traceable to the sentence
it came from.**

> **Copyright © Edward Chalk.** The architecture and source code are
> the original work of Edward Chalk; copyright protection is asserted
> to the extent permitted by law. Free for non-commercial use; for
> commercial licensing see [LICENSE.md](LICENSE.md).

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
- **Can reason, not just retrieve.** It can connect facts across
  documents to answer questions whose answers no single document
  contains.

## Who this is for

| If you... | This helps because... |
|---|---|
| Run a regulated business (finance, legal, medical, pharma) | Every answer is sourced and reproducible — audit-ready by construction |
| Have a deep technical product or manual | Customers and staff get instant, accurate answers from your own documentation |
| Field the same questions over and over in support | Answers come from your knowledge base, not a model's training data |
| Want a brand-safe conversational assistant | The assistant can only say things that exist in the corpus you curated |
| Worry about hallucination, data leakage, or AI cost at scale | None of those apply at query time, because there is no AI at query time |

## What's in the repository

Three working demonstrations, each runnable in a few seconds without
any setup, API keys, or external dependencies:

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
though no single article says so directly.

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

## How it works, in plain language

Three layers, built once and then reused at query time:

1. **Read your documents and extract structured knowledge.** This
   step uses AI (or, in this demo, hand-crafted patterns) to read
   text and pull out facts in a consistent format — *who did what,
   when, where, to whom*. This is the one place AI is used.

2. **Apply your business rules.** Combine extracted facts using
   logical rules — for example, *"if A trained B and B trained C,
   then A is an intellectual ancestor of C"*. The system derives new
   facts automatically, each tagged with the rule and inputs that
   produced it.

3. **Serve answers.** Queries run against the structured knowledge.
   No AI, no API calls. Every answer carries its source.

This split — **AI at construction time, no AI at query time** —
is what makes the system auditable, cheap, fast, and trustworthy.

## Trying it out

If you have Python installed, all three demos run with a single
command each. The technical reader will find the details in
[docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md).

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
- **[docs/NOVELTIES.md](docs/NOVELTIES.md)** — what this contributes
  that isn't standard in the field.
- **[docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)** — for
  engineers: code map, data model, API reference, recipes for
  extension.
- **[LICENSE.md](LICENSE.md)** — free for non-commercial use; for
  commercial licensing contact `licensing [at] sapientronic [dot] ai`.
