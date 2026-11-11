# Changelog

Three packages live in this repository and version independently. Sections are
per package; dates are release dates, not commit dates.

## Repository

### 2026-11-11
- Compute moved to the standalone **calcbox** package (MIT). `sidecar/app/compute.py`
  is now a thin adapter; `compute_worker.py` and `sandbox_policy.py` are gone.
- `config.open_db()` opens an index that lives on read-only media: normal connection,
  then `?mode=ro`, then `?mode=ro&immutable=1`. Fixes /health, /v1/grep and search on
  a database the process cannot write to.
- /health no longer 500s when the schema probe cannot open the index.

### Unreleased
- `sidecar/` renders pages with **pypdfium2** instead of PyMuPDF. The whole
  repository is MIT again: no AGPL dependency remains.
- Release prep for 2026-11-06: sidecar 0.2.1, socratic-mcp 0.2.0,
  dsh-socratic 0.3.1; Dockerfile + compose for the sidecar.

## sidecar

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

### 0.5.0 — 2026-11-06
- **Breaking:** the teaching layer moved to the new `dsh-socratic-persona`
  bundle. This package now ships the 13 tools and the console cards only — no
  charter, no per-step state summary, no stream rewriting.
- The `persona` config option is gone: installing (or not installing) the
  persona bundle is the switch. Presence is clearer than a flag, and it works
  per profile instead of forcing a development session to sit inside a teaching
  charter.
- `lib/stream-mode.js` moved with it; `lib/transport.js` stays here.

## dsh-socratic-persona

### 0.1.0 — 2026-11-06
- First release: the charter (`systemPrompt` section `socratic:charter`), the
  `agent/pre-step` state summary, and the `llm/stream` rewrite that enforces
  citations, withholds answer leaks and keeps one question per turn.
- Standalone: one `GET /v1/state/<session>` is the only sidecar call, so this
  package does not depend on the tools bundle.
- 12 contract tests.
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
