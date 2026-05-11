# Release Notes

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
