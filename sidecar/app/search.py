"""Chunk-level search with mandatory visibility filtering.

FTS5 bigram is always available. If BGE-M3 vectors and reranker are present,
search becomes: FTS top50 + BGE top50 -> cross-encoder rerank -> top N.
"""
import os
import re
import sqlite3
import threading
import time
from collections import OrderedDict
from urllib.parse import quote

from . import citations, config, policy, toc

CJK = re.compile(r"[\u3400-\u9fff]+")
WORD = re.compile(r"[a-z]{2,}")

_BGE = None
_BGE_ERR = None
_BGE_LOADING = False
_BGE_LOCK = threading.Lock()

_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()
_CACHE_HITS = 0
_CACHE_MISSES = 0


def tokens(s: str):
    out = []
    for run in CJK.findall(s or ""):
        if len(run) == 1:
            out.append(run)
        else:
            out.extend(run[i:i + 2] for i in range(len(run) - 1))
    out.extend(WORD.findall((s or "").lower()))
    return list(dict.fromkeys(out))


def _connect():
    con = sqlite3.connect(config.DB, timeout=5)
    con.row_factory = sqlite3.Row
    return con


def health():
    con = _connect()
    try:
        total = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
        tutor = con.execute("SELECT count(*) FROM chunks WHERE visibility='tutor'").fetchone()[0]
        secret = con.execute("SELECT count(*) FROM chunks WHERE visibility='answer_key'").fetchone()[0]
    finally:
        con.close()
    return {"db": config.DB, "chunks": total, "tutor": tutor,
            "answer_key": secret, "bge": bge_status(), **policy.health()}


def bge_status():
    if not config.BGE:
        return "disabled"
    if _BGE is not None:
        return "ready"
    if _BGE_ERR:
        return "error: " + _BGE_ERR
    if _BGE_LOADING:
        return "loading"
    return "lazy"


def _load_bge():
    global _BGE, _BGE_ERR, _BGE_LOADING
    with _BGE_LOCK:
        if _BGE is not None:
            return _BGE
        if _BGE_ERR:
            raise RuntimeError(_BGE_ERR)
        _BGE_LOADING = True
        try:
            import numpy as np
            import torch
            from sentence_transformers import SentenceTransformer
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            device = "cuda" if torch.cuda.is_available() else "cpu"
            st = SentenceTransformer(config.BGE_MODEL, device=device)
            st.max_seq_length = 256
            tok = AutoTokenizer.from_pretrained(config.RERANK_MODEL)
            rer = AutoModelForSequenceClassification.from_pretrained(config.RERANK_MODEL).to(device).eval()
            if device == "cuda":
                st.half()
                rer.half()

            vecs = np.load(config.BGE_VECTORS)
            ids = np.load(config.BGE_IDS)
            con = _connect()
            meta, texts = {}, {}
            for r in con.execute("SELECT id, source, book, lang, page, text FROM chunks WHERE visibility='tutor'"):
                meta[r["id"]] = (r["source"], r["book"], r["lang"], r["page"])
                texts[r["id"]] = r["text"]
            con.close()
            vmat = torch.from_numpy(vecs)
            if device == "cuda":
                vmat = vmat.cuda()
            _BGE = {"device": device, "st": st, "tok": tok, "rer": rer,
                    "ids": ids, "vecs": vmat, "meta": meta, "texts": texts}
            return _BGE
        except Exception as e:
            _BGE_ERR = str(e)[:300]
            raise
        finally:
            _BGE_LOADING = False


def _range(book, chapter, source="library"):
    """Page window for one chapter, or None when the book has no index."""
    if not book:
        return None
    rows = toc.load(source, book)
    if not rows:
        return None
    if chapter in (None, ""):
        return {"title": "全书", "page_start": rows[0]["page_start"],
                "page_end": rows[-1]["page_end"],
                "chapter": None, "pages": rows[-1]["page_end"] - rows[0]["page_start"] + 1}
    row = toc.find(rows, chapter)
    if not row:
        raise ValueError("chapter not found: %s" % chapter)
    return {"title": row["title"], "page_start": row["page_start"],
            "page_end": row["page_end"], "chapter": row,
            "pages": row["page_end"] - row["page_start"] + 1}


def _has_chunks(book):
    """Whether this book has text chunks. A missing catalog means "no": a fresh
    install has no index yet, and that should read as page-only, not a crash."""
    try:
        con = _connect()
        try:
            return con.execute("SELECT count(*) FROM chunks WHERE book = ?",
                               (book,)).fetchone()[0] > 0
        finally:
            con.close()
    except Exception:
        return False


def _page_results(source, book, chapter, dpi=150):
    """Page-image hits for a chapter of a book that has no text chunks."""
    out = []
    for p in range(chapter["page_start"], chapter["page_end"] + 1):
        out.append({"page": p,
                    "page_image": "/v1/pages?source=%s&book=%s&page=%d&dpi=%d"
                                  % (quote(source), quote(book), p, dpi)})
    return out


def _fts_rows(query, view, limit, source, lang, book=None, pages=None):
    toks = tokens(query)
    if not toks:
        return []
    sql = (
        "SELECT c.id, c.source, c.book, c.lang, c.page, c.text, bm25(chunks_fts) AS rank "
        "FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid "
        "WHERE chunks_fts MATCH ? AND c.visibility = ?"
    )
    params = [" OR ".join(toks), view]
    if source:
        sql += " AND c.source = ?"
        params.append(source)
    if lang:
        sql += " AND c.lang = ?"
        params.append(lang)
    if book:
        sql += " AND c.book = ?"
        params.append(book)
    if pages:
        sql += " AND c.page BETWEEN ? AND ?"
        params.extend(pages)
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)
    con = _connect()
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def _row_result(row, score):
    image = f"/v1/pages?source={quote(row['source'])}&book={quote(row['book'])}&page={row['page']}"
    score = round(float(score), 4)
    # Community-compatible aliases (RAGFlow/Onyx style) next to the native
    # fields: document_id / similarity / positions. bbox is null because chunks
    # are page-level here, not block-level.
    doc_id = "%s:%s" % (row["source"], row["book"])
    return policy.redact({
        "chunk_id": row["id"],
        "document_id": doc_id,
        "source": row["source"],
        "book": row["book"],
        "lang": row["lang"],
        "page": row["page"],
        "positions": None,
        "bbox": None,
        "similarity": score,
        "text": row["text"],
        "score": score,
        "citation": {
            "locator": f"{row['book']} p.{row['page']}",
            "tier": "unknown",
            "page_image": image,
            "document_id": doc_id,
        },
    })


def _bge_search(query, view, limit, source, lang, book=None, pages=None):
    import numpy as np
    import torch

    b = _load_bge()
    fts = _fts_rows(query, view, 50, source, lang, book, pages)
    fts_ids = [r["id"] for r in fts]

    with torch.no_grad():
        qv = b["st"].encode([query], normalize_embeddings=True,
                            convert_to_numpy=True, show_progress_bar=False).astype(np.float16)
        q = torch.from_numpy(qv)
        if b["device"] == "cuda":
            q = q.cuda()
        scores = torch.matmul(b["vecs"], q.T).view(-1)
        top = torch.topk(scores, k=min(50, scores.numel())).indices.cpu().numpy()

    bge_ids = [int(b["ids"][i]) for i in top]
    # RRF fuse FTS rank + BGE rank, then rerank only the top candidates.
    fused = {}
    for rank, cid in enumerate(fts_ids):
        fused[cid] = fused.get(cid, 0) + 1 / (60 + rank + 1)
    for rank, cid in enumerate(bge_ids):
        fused[cid] = fused.get(cid, 0) + 1 / (60 + rank + 1)
    cand = [c for c, _ in sorted(fused.items(), key=lambda kv: -kv[1])]
    cand = [c for c in cand if c in b["meta"]]
    if source:
        cand = [c for c in cand if b["meta"][c][0] == source]
    if lang:
        cand = [c for c in cand if b["meta"][c][2] == lang]
    if book:
        cand = [c for c in cand if b["meta"][c][1] == book]
    if pages:
        cand = [c for c in cand if pages[0] <= b["meta"][c][3] <= pages[1]]
    cand = cand[: config.RERANK_TOPK]
    if not cand:
        return []
    pairs = [(query, b["texts"][c][:1200]) for c in cand]
    order = []
    bs = 16
    for k in range(0, len(pairs), bs):
        batch = pairs[k:k + bs]
        enc = b["tok"]([p[0] for p in batch], [p[1] for p in batch], padding=True,
                       truncation=True, max_length=512, return_tensors="pt").to(b["device"])
        with torch.no_grad():
            s = b["rer"](**enc).logits.view(-1).float().cpu().numpy()
        order.extend(zip(cand[k:k + bs], s.tolist()))
    order.sort(key=lambda x: -x[1])
    return [_row_result({
        "id": cid, "source": b["meta"][cid][0], "book": b["meta"][cid][1],
        "lang": b["meta"][cid][2], "page": b["meta"][cid][3],
        "text": b["texts"][cid],
    }, score) for cid, score in order[:limit]]


def cache_stats():
    with _CACHE_LOCK:
        return {"size": len(_CACHE), "hits": _CACHE_HITS, "misses": _CACHE_MISSES,
                "ttl": config.CACHE_TTL, "capacity": config.CACHE_SIZE}


def clear_cache():
    global _CACHE_HITS, _CACHE_MISSES
    with _CACHE_LOCK:
        _CACHE.clear()
        _CACHE_HITS = 0
        _CACHE_MISSES = 0


def _cache_get(key):
    global _CACHE_HITS, _CACHE_MISSES
    now = time.monotonic()
    with _CACHE_LOCK:
        row = _CACHE.get(key)
        if row is None:
            _CACHE_MISSES += 1
            return None
        ts, payload = row
        if now - ts > config.CACHE_TTL:
            _CACHE.pop(key, None)
            _CACHE_MISSES += 1
            return None
        _CACHE.move_to_end(key)
        _CACHE_HITS += 1
        return payload


def _cache_put(key, payload):
    with _CACHE_LOCK:
        _CACHE[key] = (time.monotonic(), payload)
        _CACHE.move_to_end(key)
        while len(_CACHE) > config.CACHE_SIZE:
            _CACHE.popitem(last=False)


def _cite(payload, session_id, turn, step, call_id):
    if session_id:
        citations.add_many(session_id, payload.get("results", []),
                            turn=turn, step=step, call_id=call_id)


def search(query: str, view: str = "student", limit: int = 8,
           source: str | None = None, lang: str | None = None,
           book: str | None = None, chapter=None, toc_source: str = "library",
           session_id: str | None = None, turn: int | None = None,
           step: int | None = None, call_id: str | None = None):
    if view not in ("student", "tutor"):
        raise ValueError("view must be student or tutor")
    vis = "tutor"  # current corpus: student == tutor minus answer_key
    limit = max(1, min(int(limit), 20))
    t0 = time.perf_counter()

    rng = _range(book, chapter, toc_source)
    pages = (rng["page_start"], rng["page_end"]) if rng else None
    if rng and not _has_chunks(book):
        # No text layer for this book (scans): the chapter is served as pages.
        pages_out = _page_results(toc_source, book, rng, dpi=150)
        payload = {"query": query, "view": view, "results": [],
                   "mode": "page_only", "chapter": rng, "pages": pages_out,
                   "took_ms": round((time.perf_counter() - t0) * 1000, 2),
                   "cached": False}
        # One citation row per chapter: the turn card shows the chapter's page
        # image and a deep link into the page browser.
        if session_id and pages_out:
            short = os.path.splitext(os.path.basename(book))[0][:24]
            citations.add_many(session_id, [{
                "chunk_id": None, "source": toc_source, "book": book,
                "page": rng["page_start"], "lang": "page", "text": "",
                "citation": {
                    "locator": "%s %s p.%d–%d" % (short, rng["title"],
                                                  rng["page_start"], rng["page_end"]),
                    "tier": "page",
                    "page_image": pages_out[0]["page_image"],
                },
            }], turn=turn, step=step, call_id=call_id)
        return payload

    key = (query, vis, limit, source, lang, book, pages, config.BGE)
    hit = _cache_get(key)
    if hit is not None:
        _cite(hit, session_id, turn, step, call_id)
        return {**hit, "took_ms": round((time.perf_counter() - t0) * 1000, 2),
                "cached": True}

    cacheable = not config.BGE
    if config.BGE:
        try:
            results = _bge_search(query, vis, limit, source, lang, book, pages)
            payload = {"query": query, "view": view, "results": results,
                       "chapter": rng,
                       "took_ms": round((time.perf_counter() - t0) * 1000, 2),
                       "mode": "bge+rerank", "cached": False}
            _cite(payload, session_id, turn, step, call_id)
            _cache_put(key, {k: v for k, v in payload.items() if k != "took_ms"})
            return payload
        except Exception as e:
            global _BGE_ERR
            _BGE_ERR = str(e)[:300]
            cacheable = False
    rows = _fts_rows(query, vis, limit, source, lang, book, pages)
    results = [_row_result(r, -float(r["rank"])) for r in rows]
    payload = {"query": query, "view": view, "results": results,
               "chapter": rng,
               "took_ms": round((time.perf_counter() - t0) * 1000, 2),
               "mode": "fts", "cached": False}
    _cite(payload, session_id, turn, step, call_id)
    if cacheable:
        _cache_put(key, {k: v for k, v in payload.items() if k != "took_ms"})
    return payload
