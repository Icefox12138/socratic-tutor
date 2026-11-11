"""RAG database schema v2: a stable core plus per-source adapters.

v1 (:mod:`docs.RAG-DB-SCHEMA`) describes a scanned-PDF library: every chunk has
an integer page and a page image. Public corpora break that assumption — a
Wikisource citation is a revision, a CTS citation is a URN line, a dataset
citation is a row id — so v2 replaces ``page`` with a typed locator.

The two schemas live in separate SQLite files. ``SOCRATIC_SCHEMA`` selects:
``auto`` (default) detects the file, ``v1``/``v2`` force a contract. The v1
code path is untouched, so an existing installation keeps working.
"""
import os
import sqlite3

SCHEMA_META = "schema_meta"

# Every statement is idempotent: ensure_v2() may run on an existing database.
DDL = [
    "CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT)",

    """CREATE TABLE IF NOT EXISTS sources (
        source_id      TEXT PRIMARY KEY,
        adapter        TEXT NOT NULL,
        base_url       TEXT,
        auth_env       TEXT,
        rate_limit     REAL,
        license        TEXT,
        redistribution TEXT,           -- allowed | share-alike | forbidden | unknown
        enabled        INTEGER NOT NULL DEFAULT 1,
        config_json    TEXT
    )""",

    """CREATE TABLE IF NOT EXISTS documents (
        document_id   TEXT PRIMARY KEY,
        source_id     TEXT NOT NULL REFERENCES sources(source_id),
        title         TEXT NOT NULL,
        author        TEXT,
        edition       TEXT,
        lang          TEXT,
        script        TEXT,
        license       TEXT,
        provenance    TEXT,
        canonical_url TEXT,
        metadata_json TEXT
    )""",

    """CREATE TABLE IF NOT EXISTS chunks (
        id             INTEGER PRIMARY KEY,
        document_id    TEXT NOT NULL REFERENCES documents(document_id),
        ordinal        INTEGER NOT NULL,
        section        TEXT,
        text           TEXT NOT NULL,
        lang           TEXT,
        stream         TEXT NOT NULL DEFAULT 'text',   -- text|translation|commentary|apparatus
        visibility     TEXT NOT NULL DEFAULT 'tutor',  -- tutor|answer_key
        locator_json   TEXT NOT NULL,
        citation_label TEXT,
        quality        TEXT,
        char_start     INTEGER,
        char_end       INTEGER,
        source_version TEXT
    )""",

    "CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id, ordinal)",
    "CREATE INDEX IF NOT EXISTS idx_chunks_stream ON chunks(stream, visibility)",

    "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, tokenize='unicode61')",

    """CREATE TABLE IF NOT EXISTS assets (
        asset_id      TEXT PRIMARY KEY,
        document_id   TEXT REFERENCES documents(document_id),
        chunk_id      INTEGER REFERENCES chunks(id),
        type          TEXT,            -- page_image | scan | audio | mapping
        uri           TEXT,
        rights        TEXT,
        metadata_json TEXT
    )""",

    """CREATE TABLE IF NOT EXISTS embeddings (
        chunk_id INTEGER NOT NULL REFERENCES chunks(id),
        model    TEXT NOT NULL,
        dim      INTEGER NOT NULL,
        version  TEXT,
        PRIMARY KEY (chunk_id, model)
    )""",
]


def connect(path=None):
    from . import config
    con = config.open_db(path or config.DB)
    con.row_factory = sqlite3.Row
    return con


def ensure_v2(path=None):
    """Create the v2 tables and stamp the version. Safe to call repeatedly."""
    from . import config
    path = path or config.DB
    con = sqlite3.connect(path)
    try:
        for stmt in DDL:
            con.execute(stmt)
        con.execute("INSERT OR REPLACE INTO schema_meta(key, value) VALUES('rag_schema','v2')")
        con.execute("PRAGMA user_version = 2")
        con.commit()
    finally:
        con.close()
    return path


def _tables(con):
    return {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")}


def _columns(con, table):
    return {r[1] for r in con.execute("PRAGMA table_info(%s)" % table)}


def version(path=None):
    """Return ``v2``, ``v1``, ``none`` (no file) or ``unknown``."""
    from . import config
    path = path or config.DB
    if not os.path.exists(path):
        return "none"
    try:
        con = config.open_db(path)
    except (sqlite3.Error, OSError):
        return "unknown"
    try:
        tables = _tables(con)
        if SCHEMA_META in tables:
            row = con.execute("SELECT value FROM schema_meta WHERE key='rag_schema'").fetchone()
            if row and row[0] == "v2":
                return "v2"
        if "chunks" in tables:
            cols = _columns(con, "chunks")
            if "document_id" in cols and "locator_json" in cols:
                return "v2"
            return "v1"
        return "unknown"
    finally:
        con.close()


def counts(path=None):
    """Cheap catalog census used by /health."""
    con = connect(path)
    try:
        out = {"chunks": con.execute("SELECT count(*) FROM chunks").fetchone()[0],
               "documents": 0, "sources": 0}
        tables = _tables(con)
        if "documents" in tables:
            out["documents"] = con.execute("SELECT count(*) FROM documents").fetchone()[0]
        if "sources" in tables:
            out["sources"] = con.execute("SELECT count(*) FROM sources").fetchone()[0]
        return out
    finally:
        con.close()
