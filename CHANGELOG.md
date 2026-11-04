# Changelog

Three packages live in this repository and version independently. Sections are
per package; dates are release dates, not commit dates.

## Repository

### Unreleased
- `sidecar/` renders pages with **pypdfium2** instead of PyMuPDF. The whole
  repository is MIT again: no AGPL dependency remains.

## classics-index

### 0.1.3 — 2026-11-04
- README: states that this package is the build-time dependency of the separate
  private ingestion project, and that ingestion code does not live here.

### 0.1.2 — 2026-11-04
- The optional `ocr` extra no longer pulls PyMuPDF (AGPL); OCR helpers use
  `paddleocr` + `pillow` only. Keyword list follows.

### 0.1.2 — 2026-11-04
- README: the prerequisite is a database that satisfies `docs/RAG-DB-SCHEMA.md`;
  ingestion is not part of this repository.

### 0.1.1 — 2026-11-04
- Metadata only: `Homepage` / `Repository` / `Issues` now point at this repository
  (the package subdirectory), so the PyPI sidebar reaches the source.

### 0.1.0 — 2026-11-04
- First release. `volumes` / `pian` / `hui` / `find` / `at` subcommands.
- Pure standard library: no third-party runtime dependency.
- Bundled synthetic example book (`examples/`) used by the CLI tests.

## socratic-mcp

### 0.1.1 — 2026-11-04
- Metadata only: repository URLs added.

### 0.1.0 — 2026-11-04
- First release. MCP server over stdio exposing `kb_search`, `kb_read`,
  `chapter_lookup`, `review_session`, `socratic_state`, `socratic_health`.
- Speaks JSON-RPC 2.0 directly; no MCP SDK dependency.
- A missing sidecar yields `sidecar_unreachable` with `isError: true` instead of
  a dropped connection.

## dsh-socratic

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
