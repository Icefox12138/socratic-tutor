"""Minimal sidecar configuration."""
import os

ROOT = os.environ.get("SOCRATIC_ROOT", r"D:\Guo-Code")
DB = os.environ.get(
    "SOCRATIC_DB",
    os.path.join(ROOT, "socratic-tutor", "eval", "p1", "ingest", "search.db"),
)
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
BGE_VECTORS = os.environ.get(
    "SOCRATIC_BGE_VECTORS",
    os.path.join(ROOT, "socratic-tutor", "eval", "p1", "bge", "bge-vectors.npy"),
)
BGE_IDS = os.environ.get(
    "SOCRATIC_BGE_IDS",
    os.path.join(ROOT, "socratic-tutor", "eval", "p1", "bge", "bge-ids.npy"),
)
RERANK_TOPK = int(os.environ.get("SOCRATIC_RERANK_TOPK", "50"))
STATE_DB = os.environ.get(
    "SOCRATIC_STATE_DB",
    os.path.join(ROOT, "socratic-tutor", "sidecar", "state.db"),
)
