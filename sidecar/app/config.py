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


# ROOT is the directory that *contains* this checkout (books and data sit beside
# the repo). Derive it so a clone on any machine works without configuration.
_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.environ.get("SOCRATIC_ROOT") or os.path.dirname(_HERE)
LIBRARY = os.environ.get("SOCRATIC_LIBRARY", _first_existing(
    os.path.join(ROOT, "library"),
    ROOT,
))
# Derived data must live where the process can write: SQLite creates journal and
# WAL files next to the database, so a read-only library directory cannot hold it.
# There is deliberately no fallback to eval/: that directory was the old ingestion
# pipeline and now belongs to a separate project.
DATA = os.environ.get("SOCRATIC_DATA", os.path.join(_HERE, "data"))

DB = os.environ.get("SOCRATIC_DB", os.path.join(DATA, "indexes", "search.db"))
CACHE = os.environ.get(
    "SOCRATIC_CACHE",
    os.path.join(ROOT, "socratic-tutor", "sidecar", "cache", "pages"),
)
TOKEN = os.environ.get("SOCRATIC_TOKEN", "")
LLM_KEY_FILE = os.environ.get(
    "SOCRATIC_LLM_KEY_FILE", os.path.join(ROOT, "deepseek API key.txt"))
REQUIRE_AUTH = os.environ.get("SOCRATIC_REQUIRE_AUTH", "0") == "1"
PRELOAD = os.environ.get("SOCRATIC_PRELOAD", "0") == "1"
# Browser origins allowed to call the sidecar. A plain browser reaches it from
# http://127.0.0.1|localhost; the DSH desktop app renders its UI over the custom
# `dsh-app://` scheme, so its embedded teaching panel is a cross-origin client
# too. Override the whole pattern to add or tighten origins.
CORS_ORIGIN_REGEX = os.environ.get(
    "SOCRATIC_CORS_ORIGIN_REGEX",
    r"(http://(127\.0\.0\.1|localhost)(:\d+)?|dsh-app://[^/]+)")
CACHE_TTL = float(os.environ.get("SOCRATIC_CACHE_TTL", "300"))
CACHE_SIZE = int(os.environ.get("SOCRATIC_CACHE_SIZE", "256"))
VERSION = "0.2.1"

BGE = os.environ.get("SOCRATIC_BGE", "1") == "1"
BGE_MODEL = os.environ.get("SOCRATIC_BGE_MODEL", os.path.join(ROOT, "models", "bge-m3"))
RERANK_MODEL = os.environ.get(
    "SOCRATIC_RERANK_MODEL", os.path.join(ROOT, "models", "bge-reranker-v2-m3")
)
BGE_VECTORS = os.environ.get("SOCRATIC_BGE_VECTORS",
                             os.path.join(DATA, "vectors", "bge-vectors.npy"))
BGE_IDS = os.environ.get("SOCRATIC_BGE_IDS",
                         os.path.join(DATA, "vectors", "bge-ids.npy"))
# v2 (public corpora) keeps its own vector files: v1 vectors are indexed by
# chunk id too, but the two catalogues are separate SQLite files.
BGE_V2_VECTORS = os.environ.get(
    "SOCRATIC_V2_VECTORS", os.path.join(DATA, "vectors", "public-vectors.npy"))
BGE_V2_IDS = os.environ.get(
    "SOCRATIC_V2_IDS", os.path.join(DATA, "vectors", "public-ids.npy"))
BGE_V2_MODEL = os.environ.get("SOCRATIC_V2_BGE_MODEL", BGE_MODEL)

# Federated v1+v2 search: explicit paths, because the two catalogues are
# separate SQLite files with different vector files.
V1_DB = os.environ.get("SOCRATIC_V1_DB", DB)
PUBLIC_DB = os.environ.get("SOCRATIC_PUBLIC_DB", os.path.join(DATA, "public.db"))
V1_BGE_VECTORS = os.environ.get("SOCRATIC_V1_BGE_VECTORS", BGE_VECTORS)
V1_BGE_IDS = os.environ.get("SOCRATIC_V1_BGE_IDS", BGE_IDS)
BGE_V2_MODEL_NAME = os.environ.get("SOCRATIC_V2_MODEL_NAME", "bge-m3")
BGE_V2_EMBED_VERSION = os.environ.get("SOCRATIC_V2_EMBED_VERSION", "fp16-normalized")

# Query translation for v2 (Chinese question -> Greek/Latin/English keywords).
# auto = offline glossary + LLM only for OOV terms (domain-gated); glossary =
# offline only; llm = always LLM; off = never.
TRANSLATE = os.environ.get("SOCRATIC_TRANSLATE", "auto").lower()
LLM_BASE = os.environ.get("SOCRATIC_LLM_BASE", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("SOCRATIC_LLM_MODEL", "deepseek-chat")
LLM_KEY = os.environ.get("SOCRATIC_LLM_KEY", "")
TRANSLATE_TIMEOUT = float(os.environ.get("SOCRATIC_TRANSLATE_TIMEOUT", "6"))
# RRF weight of a translated variant relative to the original query.
TRANSLATE_WEIGHT = float(os.environ.get("SOCRATIC_TRANSLATE_WEIGHT", "1.5"))
# LLM variants are noisier than the curated glossary; keep them as recall
# support rather than letting them displace a strong monolingual hit.
TRANSLATE_LLM_WEIGHT = float(
    os.environ.get("SOCRATIC_TRANSLATE_LLM_WEIGHT", "1.0"))
# Translated variants are keyword-like; by default they use FTS while the
# original query keeps BGE+rerank. Set to 1 to run BGE on variants too.
TRANSLATE_BGE = os.environ.get("SOCRATIC_TRANSLATE_BGE", "0") == "1"

# Upper bound for a lemma scan (v2 catalogues are small; guard accidental full scans).
LEMMA_SCAN = int(os.environ.get("SOCRATIC_LEMMA_SCAN", "50000"))

# Lexical supplement in v2 search: grep exact strings and lemma forms as extra
# RRF lists. off disables; auto runs both where useful.
LEXICAL = os.environ.get("SOCRATIC_LEXICAL", "auto").lower()
LEXICAL_GREP_WEIGHT = float(os.environ.get("SOCRATIC_LEXICAL_GREP_WEIGHT", "2.0"))
LEXICAL_LEMMA_WEIGHT = float(os.environ.get("SOCRATIC_LEXICAL_LEMMA_WEIGHT", "1.3"))

# v1 (private PDF) opt-in improvements: translation variants + grep fusion.
# Off by default so the existing v1 path and its cache stay bit-compatible.
V1_RETRIEVAL = os.environ.get("SOCRATIC_V1_RETRIEVAL", "0") == "1"
# v1 citations are page-level and the P1 metric is page recall@10; one chunk
# per page keeps ten pages in the top-10 instead of ten chunks of one page.
V1_PAGE_DEDUPE = os.environ.get("SOCRATIC_V1_PAGE_DEDUPE", "1") == "1"
# Keep the base query's best hit at rank 1; translated variants only add
# recall below it. This avoids the v1 top-1 drop seen with LLM variants.
V1_ANCHOR_BASE = os.environ.get("SOCRATIC_V1_ANCHOR_BASE", "1") == "1"
# How many base-query hits keep their slots; translated/Greek lists fill the rest.
V1_ANCHOR_TOPK = int(os.environ.get("SOCRATIC_V1_ANCHOR_TOPK", "1"))
# Optional second rerank of the fused list against the original query.
V1_FINAL_RERANK = os.environ.get("SOCRATIC_V1_FINAL_RERANK", "0") == "1"
# P1's 0.82 came from translating only the Greek/Latin (English) questions.
# Chinese questions target Chinese books; translating them adds noise.
V1_TRANSLATE_NONCJK_ONLY = os.environ.get(
    "SOCRATIC_V1_TRANSLATE_NONCJK_ONLY", "1") == "1"
# v1 Greek lemma channel: an in-memory inverted index over Greek chunks.
V1_GREEK_LEMMA = os.environ.get("SOCRATIC_V1_GREEK_LEMMA", "0") == "1"
V1_GREEK_LEMMA_WEIGHT = float(
    os.environ.get("SOCRATIC_V1_GREEK_LEMMA_WEIGHT", "2.0"))
# English commentary pages inside Greek/Latin books (vocab/notes) are a
# separate lexical channel; the questions are often English.
V1_COMMENTARY = os.environ.get("SOCRATIC_V1_COMMENTARY", "0") == "1"
V1_COMMENTARY_WEIGHT = float(
    os.environ.get("SOCRATIC_V1_COMMENTARY_WEIGHT", "1.3"))

# Edition alignment: add the corresponding page from other editions of the
# same work (same Greek/Latin passage, different page numbering).
V1_EDITION_ALIGN = os.environ.get("SOCRATIC_V1_EDITION_ALIGN", "0") == "1"
V1_EDITION_ALIGN_WEIGHT = float(
    os.environ.get("SOCRATIC_V1_EDITION_ALIGN_WEIGHT", "2.0"))
V1_EDITION_ALIGN_TOPK = int(
    os.environ.get("SOCRATIC_V1_EDITION_ALIGN_TOPK", "2"))

# Candidate width for v1 hybrid. Wider reranking costs latency but can recover
# pages that rank 51-100 before rerank.
BGE_TOPK = int(os.environ.get("SOCRATIC_BGE_TOPK", "50"))
# v1 RRF: BGE is stronger than bigram FTS on natural-language questions.
BGE_RRF_WEIGHT = float(os.environ.get("SOCRATIC_BGE_RRF_WEIGHT", "1.0"))
RERANK_TOPK = int(os.environ.get("SOCRATIC_RERANK_TOPK", "50"))
STATE_DB = os.environ.get(
    "SOCRATIC_STATE_DB",
    os.path.join(_HERE, "sidecar", "state.db"),
)

# The chapter index is data, not runtime state. SOCRATIC_TOC_IN=search reads it
# from the RAG database; the default keeps it in state.db for compatibility.
# Resolution stays dynamic so tests (and callers) can repoint STATE_DB at runtime.
# Page rendering is optional: a deployment that keeps only text + vectors does
# not need PDFium or the PDFs themselves.
RENDER = os.environ.get("SOCRATIC_RENDER", "auto").lower()   # auto | on | off


def _pdfium_available():
    import importlib.util
    return importlib.util.find_spec("pypdfium2") is not None


def render_enabled():
    """Whether /v1/pages can actually render.

    auto: on when the library directory exists and PDFium imports.
    on:   required — a missing dependency is the operator's problem, surfaced early.
    off:  text-only deployment; page images are simply absent.
    """
    if RENDER == "on":
        return True
    if RENDER == "off":
        return False
    return os.path.isdir(os.path.join(LIBRARY, "PDF")) and _pdfium_available()


def render_status():
    if RENDER == "off":
        return "off"
    if not _pdfium_available():
        return "missing: pypdfium2 not installed"
    if RENDER == "auto" and not os.path.isdir(os.path.join(LIBRARY, "PDF")):
        return "off: no library directory at " + os.path.join(LIBRARY, "PDF")
    return "on"


# RAG contract: v1 (scanned PDF pages) or v2 (documents + typed locators).
# auto detects the file, so one binary serves both kinds of catalogue.
SCHEMA = os.environ.get("SOCRATIC_SCHEMA", "auto").lower()

# Streams a student may see. v2 stores translation/commentary/apparatus rows
# next to the text so a tutor can reveal them; the default withholds them.
STUDENT_STREAMS = tuple(
    s.strip() for s in os.environ.get("SOCRATIC_STUDENT_STREAMS", "text").split(",")
    if s.strip()
)


def schema_version(path=None):
    """Which contract the configured database follows."""
    from . import schema as _schema
    if SCHEMA in ("v1", "v2"):
        return SCHEMA
    return _schema.version(path or DB)


TOC_IN = os.environ.get("SOCRATIC_TOC_IN", "state").lower()
TOC_DB_OVERRIDE = os.environ.get("SOCRATIC_TOC_DB") or None


def toc_db():
    """Which SQLite file holds the chapter index."""
    if TOC_DB_OVERRIDE:
        return TOC_DB_OVERRIDE
    return DB if TOC_IN == "search" else STATE_DB
