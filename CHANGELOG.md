# Changelog

Five independently versioned packages live in this repository (sidecar, classics-index,
socratic-mcp, dsh-socratic, dsh-socratic-persona, dsh-socratic-curriculum); calcbox and
ragpages live in their own repositories. Sections are per package; dates are release
dates, not commit dates.

## Repository

### 2026-11-11
- Compute moved to the standalone **calcbox** package (MIT). `sidecar/app/compute.py`
  is now a thin adapter; `compute_worker.py` and `sandbox_policy.py` are gone.
- `config.open_db()` opens an index that lives on read-only media: normal connection,
  then `?mode=ro`, then `?mode=ro&immutable=1`. Fixes /health, /v1/grep and search on
  a database the process cannot write to.
- /health no longer 500s when the schema probe cannot open the index.

### 2026-11-06 → 2026-11-17 (shipped; kept for history)
- `sidecar/` renders pages with **pypdfium2** instead of PyMuPDF. The whole
  repository is MIT again: no AGPL dependency remains. (Shipped in sidecar 0.3.0.)
- Release prep for 2026-11-06: sidecar 0.2.1, socratic-mcp 0.2.0,
  dsh-socratic 0.3.1; Dockerfile + compose for the sidecar.

## sidecar

### 0.3.2 — 2026-11-24
- **Lesson cards**: `/v1/state/init` with `lesson=...` imports the pack's
  `review_cards` into the FSRS queue (`learner.add_cards`, terms de-duplicated so a
  repeated init cannot flood the review queue). The response carries
  `lesson` and `cards: {added, skipped}`. The engine still invents no cards: the
  pack declares them (docs/CURRICULUM-SCHEMA.md) and the engine only imports.
- **`cards` extra**: `pip install "socratic-sidecar[cards]"` pulls FSRS. Without it
  card import degrades to `cards: {error: "fsrs not installed"}` and the /v1/cards
  endpoints keep their 503 behaviour; lesson binding itself still works.
- **Neutral lexicon sourcing**: `lexicon.py` no longer hardcodes `dict-lsj` /
  `grammar-smyth`. An edition name ("lsj") resolves its tier through the policy's
  `doc_kind → cite` rule, and the entry's `source` comes from
  `lexicon_headwords.source_id` → `documents.source_id`; a deployment with its own
  lexicon.db and policy needs no code change.
- 390 tests (new: lesson-card import/dedupe at learner and state-init level, and the
  policy fallback for lexicon tiers). CI installs `fsrs` so the card path is
  exercised instead of skipped.

### 0.3.1 — 2026-11-24
- **M2 — long entries page**: `/v1/lexicon` accepts `entry_offset` / `entry_limit`
  (characters) and returns `definition_offset`, `definition_total`,
  `definition_truncated` and `next_offset`. λόγος is 24 KB / 64 senses; a client no
  longer has to pull the whole entry into one result.
- **M2 — lookup latency**: one cached connection plus a cached schema snapshot per
  lexicon file, and per-column indexed equality lookups. The old
  `lower(headword) OR lower(lemma)` predicate scanned ~220k rows on every call.
  Real lexicon (219,738 entries): hit 56 ms → **0.3 ms**, miss 57 ms → **0.14 ms**;
  `schema.ensure_v2` now also creates `idx_lex_lower_head` / `idx_lex_lower_lemma`
  for the case-insensitive fallback.
- **M3 — grammar data**: A&G *New Latin Grammar* 640/642 sections ingested as
  grammar chunks (§1–§640; §641–§642 are the *Parallel Constructions* appendix
  tables), so `area=grammar&q=§419` answers with the section body and a citation.
  The Alpheios/DCC HTML edition lacks §607–629 and §639–642; those are filled
  section-by-section from the same 1903 text on Perseus. Ingestion lives in
  rag-build (`eval/ingest_ag.py`, `eval/lexicon_indexes.py`) and is idempotent.
- Grammar citation labels use the section title (`§419 ABLATIVE ABSOLUTE`) instead of
  the document title, and no longer double the `§`.

### 0.3.0 — 2026-11-17
- **Schema v2.1**: `documents.kind` (textbook/edition/dictionary/grammar…), the
  `chunks.stream` vocabulary grows to ten values, and a new `lexicon_headwords`
  table holds the exact-match index for dictionaries and grammars. All additive:
  `ensure_v2()` adds the column in place, and `migrate_v1_stream()` gives a v1
  database the inert `stream` column. `scripts/migrate_schema.py` wraps both with
  a timestamped backup and is idempotent.
- **Stream visibility is per document kind** (`citation_policy.streams_for`):
  a dictionary student sees `definition`/`example`, a textbook `formula`/`table`/
  `code`, an edition `commentary`/`apparatus`; `SOCRATIC_STUDENT_STREAMS` still
  overrides the whole table. `search`, `catalog` and the lexical channels all read
  through it, so no reader keeps its own list.
- **`/v1/lexicon`**: form → lemma → entry (dictionary) or `§N` (grammar), from
  `lexicon_headwords`; a missing database answers `no_lexicon` instead of failing.
- **Lexicon entries are read back whole**: v2.1 lexicon databases set
  `chunks.entry_id` on every sense chunk, so a multi-sense entry now returns all
  its senses joined (was: one chunk). Databases without the column keep the old
  single-chunk behaviour.
- **Curriculum framework (schema v1)**: `/v1/curriculum` serves lesson packs from
  `SOCRATIC_CURRICULUM` (a directory of JSON files), resolving vocab against
  `lexicon.db` when present; `scripts/curriculum_check.py` validates a pack
  directory. The engine ships the contract, not the courses (docs/CURRICULUM-SCHEMA.md).
- **LEARN / REVIEW phases** (opt-in on `/v1/state/init`): a preview pass (brief
  instruction + one worked example + self-explanation) between DIAGNOSE and PLAN,
  and a spaced-review opening. Both default off, so existing hosts see the old flow.
  The persona charter gains the two phase hints.
- The builtin policy gains `dict-lsj` / `grammar-smyth` / `grammar-ag`
  (tier A, `catalogue: lexicon`) and two `doc_kind` rules ahead of the catch-all;
  the default rule and `rrf` merge are unchanged.
- 383 tests (was 355).

### 0.2.1 — 2026-11-06
- Removed the Windows AppContainer path; compute worker now always uses the
  audit policy sandbox (network/subprocess denied, temp-only writes).
- Cross-platform: removed hard-coded `D:\` API-key path; portable font fallback;
  SQLite read-only URI via `pathlib`.
- Sidecar Dockerfile/compose kept for Linux.

### 0.2.0 — 2026-11-06
- Public corpora v2: Wikisource / Perseus CTS adapters, locator/stream/license,
  revision/URN citations, BGE-M3 vectors, FTS + BGE + rerank.
- Query translation: offline glossary + optional LLM only for OOV terms;
  Chinese-history domain gate.
- Lexical channels: `/v1/grep`, `/v1/lemma`; grep/lemma fused into v2 RRF.
- v1 retrieval: selective non-Chinese translation and base top-1 anchoring;
  opt-in Greek lemma / commentary / edition alignment experiments.
- Federated search: `scope=all` and `scope=routed` (`v1+v2`).
- Compute backends: SymPy/SciPy/pint/control; optional Wolfram/Lean; killed
  subprocess worker; audit sandbox; credentials + disputed marker.
- 263 sidecar tests.

## classics-index

### 0.1.4 — 2026-11-20
- `__version__` synced with `pyproject.toml` (was 0.1.0 while the manifest said
  0.1.3) and a test now enforces the two agree.
- Removed the duplicated `enrich()` in `core.py`: the first copy shadowed the
  second, and only one of them was reachable.
- README: license is MIT and the package is on PyPI (the old text said the
  license was undecided and "do not publish"); the OCR scripts are in the
  private rag-build project, not in this repo; added a boundary table (pure
  logic in the package, OCR/storage/paths outside it).
- No API change.

### 0.1.3 — 2026-11-04
- README: states that this package is the build-time dependency of the separate
  private ingestion project, and that ingestion code does not live here.

### 0.1.2 — 2026-11-04
- README: the prerequisite is a database that satisfies `docs/RAG-DB-SCHEMA.md`;
  ingestion is not part of this repository.
- The optional `ocr` extra no longer pulls PyMuPDF (AGPL); OCR helpers use
  `paddleocr` + `pillow` only. Keyword list follows.

### 0.1.1 — 2026-11-04
- Metadata only: `Homepage` / `Repository` / `Issues` now point at this repository
  (the package subdirectory), so the PyPI sidebar reaches the source.

### 0.1.0 — 2026-11-04
- First release. `volumes` / `pian` / `hui` / `find` / `at` subcommands.
- Pure standard library: no third-party runtime dependency.
- Bundled synthetic example book (`examples/`) used by the CLI tests.

## socratic-mcp

### 0.2.1 — 2026-11-23
- `__init__.__version__` and `tools.VERSION` now agree with the package version;
  the 0.2.0 wheel on PyPI still answered `initialize` with
  `serverInfo.version = "0.1.0"`.
- No API change.

### 0.2.0 — 2026-11-06
- New `kb_lexical` tool (grep / lemma) for exact quotations and inflected forms.
- `kb_search` accepts `scope=all|routed` for federated v1+v2 routing.
- `kb_search` / `kb_lexical` pass `source/lang/book/document_id/section`.
- 6 tests.

### 0.1.1 — 2026-11-04
- Metadata only: repository URLs added.

### 0.1.0 — 2026-11-04
- First release. MCP server over stdio exposing `kb_search`, `kb_read`,
  `chapter_lookup`, `review_session`, `socratic_state`, `socratic_health`.
- Speaks JSON-RPC 2.0 directly; no MCP SDK dependency.
- A missing sidecar yields `sidecar_unreachable` with `isError: true` instead of
  a dropped connection.

## dsh-socratic

### 0.5.2 — 2026-11-24
- **Word-card UI** in the embedded console (`conversation.composer.dock`, order
  220): search a headword or a grammar section (`§419`) against `/v1/lexicon`,
  render headword/POS/lemma/definition with the citation tier badge, page long
  entries by character window (`更多 1200/24481`), and jump from any citation
  row's 「词条 ↗」 straight to the matching entry (the locator decides dict vs
  `§N`). Degrades honestly: `no_lexicon` and `not_found` are shown as such.
- `client.js` gains a contract test (stub loader + stub React) covering slot
  registration and the closed-state chips; CI runs it next to the tools tests.

### 0.5.1 — 2026-11-12
- `engines.dsh` widened to `>=0.2.1-rc.2 <0.3.0-0 || >=0.2.2-rc.2 <0.3.0-0`.
  Strict semver excludes a prerelease unless a comparator carries the same
  `major.minor.patch`, so the old single range did **not** strictly match
  `0.2.2-rc.2` even though DSH (which evaluates with `includePrerelease`) accepted
  it. The union matches `0.2.2-rc.2` strictly, keeps the 0.2.1 releases, and still
  refuses every 0.3.x. Verified against DSH 0.2.2-rc.2's own semver.

### 0.5.0 — 2026-11-06
- **Breaking:** the teaching layer moved to the new `dsh-socratic-persona`
  bundle. This package now ships the 13 tools and the console cards only — no
  charter, no per-step state summary, no stream rewriting.
- The `persona` config option is gone: installing (or not installing) the
  persona bundle is the switch. Presence is clearer than a flag, and it works
  per profile instead of forcing a development session to sit inside a teaching
  charter.
- `lib/stream-mode.js` moved with it; `lib/transport.js` stays here.

### 0.4.2 — 2026-11-06
- Refactor only: `charterText()`, `makeStreamHandler()` and `makePreStepHandler()`
  are exported, so the charter wording and both Host hooks can be asserted in
  unit tests instead of by reading a live session. 8 new tests (20 total); no
  behaviour change.

### 0.4.1 — 2026-11-06
- New `persona` config option (**default on**). With `persona: false` the plugin
  registers its 13 tools and nothing else: no teaching charter in the system
  prompt, no per-step state summary, no `llm/stream` rewriting. Those three all
  apply to every session in the profile, which is wrong for a development
  session that only wants the tools.
- 4 new contract tests (12 total).

### 0.4.0 — 2026-11-06
- Embedded console gained a read-only **policy card**: policy version, what is
  enforced, the source table (tier / role) and every channel with its
  availability and whether the serving path is using it.
- Turn citations now show the **trust tier** (`A`–`D`, `*` when estimated) and
  the **role in the answer** (`anchor` / `corroborating`), read from the
  citation row the sidecar persists. Rows written before those columns existed
  stay blank rather than being labelled `unknown`.
- Both cards keep the panel's resilience rules: per-endpoint `allSettled`, no
  polling on the policy card, and a visible `last_reload_error`.
- Requires sidecar ≥ 0.2.1; against an older sidecar the new fields are simply
  absent and the badges do not render.

### 0.3.1 — 2026-11-06
- Documentation only: README/SMOKE use portable `/path/to/...` placeholders
  instead of a machine-specific `D:\...` path.

### 0.3.0 — 2026-11-06
- New `lexical_search` tool: grep exact strings / lemma inflected forms.
- `kb_search` accepts `scope=all` (merge v1+v2) and `scope=routed`.
- `compute_math` supports backend/target/data: SymPy, SciPy, pint, control,
  optional Wolfram/Lean; unavailable backends return 503.
- `compute_math` renders credentials/disputed metadata.
- `files` whitelist keeps logs/screenshots out of the tarball.

### 0.2.4 — 2026-11-04
- `cite_verify` accepts an optional `quote`: with it the check runs against the
  indexed text of that page (`/v1/verify`), so citations stay verifiable in a
  text-only deployment where page rendering is switched off.

### 0.2.3 — 2026-11-04
- README: prerequisite is a RAG database built elsewhere; a missing index yields
  `no_index` tool results instead of a crash.

### 0.2.2 — 2026-11-04
- Metadata: `author` added.

### 0.2.1 — 2026-11-04
- Metadata only: `repository.directory`, `homepage`, `bugs`.

### 0.2.0 — 2026-11-04
- First npm release. Twelve tools registered.
- Transport extracted into `lib/transport.js`; every tool answers with a
  structured `sidecar_unreachable` error when the service is down (`socratic_health`
  excepted, so the failure is diagnosable).
- `SOCRATIC_STREAM=stream` opt-in passthrough for token-by-token output; buffered
  rewriting remains the default so interception still sees the whole reply.
- `files` whitelist so screenshots, logs and tests never enter the tarball.

## dsh-socratic-persona

### 0.1.1 — 2026-11-12
- The `agent/pre-step` handler no longer mutates the decision returned by
  `next()`; it returns `{ ...decision, messages: [injected, ...messages] }`.
  DSH 0.2.2 deep-freezes `llm/stream` options, so mutating a returned object is a
  hazard worth avoiding before it bites.
- Same `engines.dsh` widening as the tools bundle.
- 13 contract tests (one new: a frozen decision is returned intact, and the
  identity fallback `agent.id` is covered).

### 0.1.0 — 2026-11-06
- First release: the charter (`systemPrompt` section `socratic:charter`), the
  `agent/pre-step` state summary, and the `llm/stream` rewrite that enforces
  citations, withholds answer leaks and keeps one question per turn.
- Standalone: one `GET /v1/state/<session>` is the only sidecar call, so this
  package does not depend on the tools bundle.
- 12 contract tests.

## dsh-socratic-curriculum

### 0.1.0 — 2026-11-24
- First release: the course layer. Three tools (`curriculum_list`,
  `curriculum_lesson`, `curriculum_start`) over the sidecar's `/v1/curriculum`
  endpoints, and one `agent/pre-step` hook that injects the active lesson block
  at the first step of each turn (never mutating the decision returned by
  `next()`).
- `curriculum_start` binds a lesson to the session state machine:
  `/v1/state/init` with `lesson=<id>, learn=true`, or `review=true` for a
  review-first opening.
- The engine ships the contract, not the courses: lesson packs live in
  `SOCRATIC_CURRICULUM` and are validated with `scripts/curriculum_check.py`.
  Without packs the tools answer `lessons: []` and the hook is inert.
- 10 contract tests.
- npm: https://www.npmjs.com/package/dsh-socratic-curriculum (0.1.0, OIDC + provenance).
