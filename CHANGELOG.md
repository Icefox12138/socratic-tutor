# Changelog

Three packages live in this repository and version independently. Sections are
per package; dates are release dates, not commit dates.

## Repository

### Unreleased
- `sidecar/` renders pages with **pypdfium2** instead of PyMuPDF. The whole
  repository is MIT again: no AGPL dependency remains.
- Release prep for 2026-11-06: sidecar 0.2.0, socratic-mcp 0.2.0,
  dsh-socratic 0.3.0; Dockerfile + compose for the sidecar.

## sidecar

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
  subprocess worker; audit sandbox fallback; credentials + disputed marker.
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
