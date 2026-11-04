"""Minimal sidecar configuration.

Two roots:
  LIBRARY  the books (PDF, PDF-new, loeb, teubner) — never generated content
  DATA     everything derived from them (indexes, vectors, experiments)

Both fall back to the pre-2026-11 layout so an existing install keeps working.
"""
import os


def _first_existing(*candidates):
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[-1]


ROOT = os.environ.get("SOCRATIC_ROOT", r"D:\Guo-Code")
LIBRARY = os.environ.get("SOCRATIC_LIBRARY", _first_existing(
    os.path.join(ROOT, "library"),
    ROOT,
))
# Derived data must live where the process can write: SQLite creates journal and
# WAL files next to the database, so a read-only library directory cannot hold it.
# There is deliberately no fallback to eval/: that directory was the old ingestion
# pipeline and now belongs to a separate project.
DATA = os.environ.get("SOCRATIC_DATA", os.path.join(ROOT, "socratic-tutor", "data"))

DB = os.environ.get("SOCRATIC_DB", os.path.join(DATA, "indexes", "search.db"))
CACHE = os.environ.get(
    "SOCRATIC_CACHE",
    os.path.join(ROOT, "socratic-tutor", "sidecar", "cache", "pages"),
)
TOKEN = os.environ.get("SOCRATIC_TOKEN", "")
REQUIRE_AUTH = os.environ.get("SOCRATIC_REQUIRE_AUTH", "0") == "1"
PRELOAD = os.environ.get("SOCRATIC_PRELOAD", "0") == "1"
CACHE_TTL = float(os.environ.get("SOCRATIC_CACHE_TTL", "300"))
CACHE_SIZE = int(os.environ.get("SOCRATIC_CACHE_SIZE", "256"))
VERSION = "0.1.0"

BGE = os.environ.get("SOCRATIC_BGE", "1") == "1"
BGE_MODEL = os.environ.get("SOCRATIC_BGE_MODEL", os.path.join(ROOT, "models", "bge-m3"))
RERANK_MODEL = os.environ.get(
    "SOCRATIC_RERANK_MODEL", os.path.join(ROOT, "models", "bge-reranker-v2-m3")
)
BGE_VECTORS = os.environ.get("SOCRATIC_BGE_VECTORS",
                             os.path.join(DATA, "vectors", "bge-vectors.npy"))
BGE_IDS = os.environ.get("SOCRATIC_BGE_IDS",
                         os.path.join(DATA, "vectors", "bge-ids.npy"))
RERANK_TOPK = int(os.environ.get("SOCRATIC_RERANK_TOPK", "50"))
STATE_DB = os.environ.get(
    "SOCRATIC_STATE_DB",
    os.path.join(ROOT, "socratic-tutor", "sidecar", "state.db"),
)

# The chapter index is data, not runtime state. SOCRATIC_TOC_IN=search reads it
# from the RAG database; the default keeps it in state.db for compatibility.
# Resolution stays dynamic so tests (and callers) can repoint STATE_DB at runtime.
TOC_IN = os.environ.get("SOCRATIC_TOC_IN", "state").lower()
TOC_DB_OVERRIDE = os.environ.get("SOCRATIC_TOC_DB") or None


def toc_db():
    """Which SQLite file holds the chapter index."""
    if TOC_DB_OVERRIDE:
        return TOC_DB_OVERRIDE
    return DB if TOC_IN == "search" else STATE_DB
