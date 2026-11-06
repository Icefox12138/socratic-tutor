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

from . import (catalog, citation_policy, citations, config, editions, lexical,
               locators, policy, schema, textutil, toc, translate)

CJK = re.compile(r"[\u3400-\u9fff]+")
WORD = re.compile(r"[a-z]{2,}")
_CLASSICAL = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]|[A-Za-z]{3,}")
_GREEK_SCRIPT = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")

_BGE = None
_BGE_ERR = None
_BGE_LOADING = False
_BGE_LOCK = threading.Lock()

# v2 has its own model instance and vector files: the two catalogues can point
# at different models, and a v2 deployment must not load v1 vectors by accident.
_V2_BGE = None
_V2_BGE_ERR = None
_V2_BGE_LOADING = False
_V2_BGE_LOCK = threading.Lock()

_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()
_CACHE_HITS = 0
_CACHE_MISSES = 0


def tokens(s: str):
    """v1 tokenisation, kept as a module-level alias for existing callers."""
    return textutil.tokens(s)


def tokens_v2(s: str):
    return textutil.tokens_v2(s)


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
    ver = config.schema_version()
    census = {"documents": 0, "sources": 0}
    if ver == "v2":
        try:
            census = schema.counts()
        except Exception:
            pass
    bge = bge_status()
    vectors, ids = config.BGE_VECTORS, config.BGE_IDS
    if ver == "v2":
        bge = v2_bge_status()
        vectors, ids = config.BGE_V2_VECTORS, config.BGE_V2_IDS
    return {"data": config.DATA, "db": config.DB,
            "vectors": vectors, "ids": ids,
            "toc": config.toc_db(), "schema": ver,
            "documents": census.get("documents", 0),
            "sources": census.get("sources", 0),
            "chunks": total, "tutor": tutor, "answer_key": secret,
            "render": config.render_status(),
            "bge": bge, **policy.health()}


_NORM = None


def _norm(text):
    """Strip everything that OCR or a human might render differently."""
    global _NORM
    if _NORM is None:
        import re as _re
        _NORM = _re.compile(r"[^\w\u4e00-\u9fff]+", _re.UNICODE)
    return _NORM.sub("", (text or "").lower())


def verify(book=None, page=None, quote="", source=None, document_id=None,
           section=None, revision=None):
    """Does `quote` appear in the stored text of that citation target?

    v1 targets a page (``book`` + ``page``); v2 targets a document, optionally
    narrowed to a section and pinned to a revision. A revision mismatch is a
    hard failure: the quotation was checked against a different text than the
    one the caller cites.
    """
    if document_id:
        return _verify_v2(document_id, quote, section=section, revision=revision)
    if page is None:
        raise ValueError("book+page or document_id is required")
    sql = ("SELECT text FROM chunks WHERE book = ? AND page = ? "
           "AND visibility = 'tutor'")
    params = [book, page]
    if source:
        sql += " AND source = ?"
        params.append(source)
    con = _connect()
    try:
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()
    page_text = _norm("".join(r["text"] for r in rows))
    needle = _norm(quote)
    if not page_text:
        return {"verified": False, "method": "text", "page": page,
                "reason": "no text indexed for that page", "chunks": 0}
    ok = needle in page_text if needle else False
    return {"verified": ok, "method": "text", "page": page,
            "chunks": len(rows),
            "reason": "" if ok else "quote not found on that page"}


def _verify_v2(document_id, quote, section=None, revision=None):
    sql = ("SELECT text, locator_json, citation_label FROM chunks "
           "WHERE document_id = ? AND visibility = 'tutor'")
    params = [document_id]
    if section:
        sql += " AND section = ?"
        params.append(section)
    con = _connect()
    try:
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()
    locs = [locators.loads(r["locator_json"]) for r in rows]
    scheme = locators.scheme(locs[0]) if locs else None
    out = {"verified": False, "method": "text", "document_id": document_id,
           "section": section, "scheme": scheme, "chunks": len(rows)}
    if not rows:
        out["reason"] = "no text indexed for that document/section"
        return out
    if revision:
        revisions = {str(l.get("revision")) for l in locs if l.get("revision")}
        if revisions and str(revision) not in revisions:
            out["reason"] = "revision mismatch: indexed %s, asked %s" % (
                ", ".join(sorted(revisions)), revision)
            out["revision"] = sorted(revisions)[0]
            return out
    stored = _norm("".join(r["text"] for r in rows))
    needle = _norm(quote)
    ok = bool(needle) and needle in stored
    out["verified"] = ok
    out["reason"] = "" if ok else "quote not found in that text"
    if locs:
        out["revision"] = locs[0].get("revision")
        out["locator"] = (rows[0]["citation_label"]
                          or locators.default_label(locs[0]))
    return out


def bge_status():
    """Why BGE is or is not serving. Missing files are named, not silently degraded."""
    if not config.BGE:
        return "disabled"
    if _BGE is not None:
        return "ready"
    if _BGE_ERR:
        return "error: " + _BGE_ERR
    if not os.path.exists(config.BGE_VECTORS):
        return "missing: " + config.BGE_VECTORS
    if not os.path.exists(config.BGE_IDS):
        return "missing: " + config.BGE_IDS
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


def v2_bge_status():
    """Why v2 hybrid retrieval is or is not serving."""
    if not config.BGE:
        return "disabled"
    if _V2_BGE is not None:
        return "ready"
    if _V2_BGE_ERR:
        return "error: " + _V2_BGE_ERR
    if not os.path.exists(config.BGE_V2_VECTORS):
        return "missing: " + config.BGE_V2_VECTORS
    if not os.path.exists(config.BGE_V2_IDS):
        return "missing: " + config.BGE_V2_IDS
    if _V2_BGE_LOADING:
        return "loading"
    return "lazy"


_V2_CHUNK_SQL = (
    "SELECT c.id, c.document_id, c.ordinal, c.section, c.text, c.lang,"
    " c.stream, c.locator_json, c.citation_label, c.quality,"
    " c.char_start, c.char_end, d.title, d.author, d.license,"
    " d.canonical_url, d.source_id FROM chunks c"
    " JOIN documents d ON d.document_id = c.document_id"
    " WHERE c.visibility = 'tutor'")


def _load_v2_bge():
    global _V2_BGE, _V2_BGE_ERR, _V2_BGE_LOADING
    with _V2_BGE_LOCK:
        if _V2_BGE is not None:
            return _V2_BGE
        if _V2_BGE_ERR:
            raise RuntimeError(_V2_BGE_ERR)
        _V2_BGE_LOADING = True
        try:
            import numpy as np
            import torch
            from sentence_transformers import SentenceTransformer
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            device = "cuda" if torch.cuda.is_available() else "cpu"
            st = SentenceTransformer(config.BGE_V2_MODEL, device=device)
            st.max_seq_length = 256
            tok = AutoTokenizer.from_pretrained(config.RERANK_MODEL)
            rer = AutoModelForSequenceClassification.from_pretrained(
                config.RERANK_MODEL).to(device).eval()
            if device == "cuda":
                st.half()
                rer.half()

            vecs = np.load(config.BGE_V2_VECTORS)
            ids = np.load(config.BGE_V2_IDS)
            if vecs.ndim != 2 or vecs.shape[1] != 1024:
                raise RuntimeError("v2 vectors must be (N, 1024), got %s"
                                   % (vecs.shape,))
            if ids.ndim != 1 or len(ids) != vecs.shape[0]:
                raise RuntimeError("v2 vector/ids mismatch: %s vs %s"
                                   % (vecs.shape, ids.shape))
            con = _connect()
            try:
                rows = con.execute(_V2_CHUNK_SQL).fetchall()
            finally:
                con.close()
            meta = {r["id"]: dict(r) for r in rows}
            texts = {cid: row["text"] for cid, row in meta.items()}
            keep = [k for k, cid in enumerate(ids) if int(cid) in meta]
            ids = ids[keep]
            vecs = vecs[keep]
            if len({int(x) for x in ids}) != len(ids):
                raise RuntimeError("duplicate chunk ids in v2 vectors")
            vmat = (torch.from_numpy(vecs).cuda() if device == "cuda"
                    else torch.from_numpy(vecs.astype(np.float32)))
            _V2_BGE = {"device": device, "st": st, "tok": tok, "rer": rer,
                       "ids": ids, "vecs": vmat, "meta": meta, "texts": texts}
            return _V2_BGE
        except Exception as e:
            _V2_BGE_ERR = str(e)[:300]
            raise
        finally:
            _V2_BGE_LOADING = False


def _v2_rerank(b, query, pairs, bs=16):
    import torch
    order = []
    for k in range(0, len(pairs), bs):
        batch = pairs[k:k + bs]
        enc = b["tok"]([query] * len(batch), [p[1][:1200] for p in batch],
                       padding=True, truncation=True, max_length=512,
                       return_tensors="pt").to(b["device"])
        with torch.no_grad():
            scores = b["rer"](**enc).logits.view(-1).float().cpu().numpy()
        order.extend((cid, float(score)) for (cid, _text), score
                     in zip(batch, scores.tolist()))
    order.sort(key=lambda x: -x[1])
    return order


def _v2_meta_ok(row, view, source=None, lang=None, book=None,
                document_id=None, section=None):
    if view == "student":
        streams = config.STUDENT_STREAMS or ("text",)
        if row["stream"] not in streams:
            return False
    if source and row["source_id"] != source:
        return False
    if lang and row["lang"] != lang:
        return False
    if document_id and row["document_id"] != document_id:
        return False
    if book and row["document_id"] != book and row["title"] != book:
        return False
    if section and row["section"] != section:
        return False
    return True


def _v2_bge_search(query, view, limit, source=None, lang=None, book=None,
                   document_id=None, section=None, b=None):
    import numpy as np
    import torch

    b = b or _load_v2_bge()
    fts = _v2_rows(query, view, 50, source=source, lang=lang, book=book,
                   document_id=document_id, section=section)
    fts_ids = [r["id"] for r in fts]

    with torch.no_grad():
        qv = b["st"].encode([query], normalize_embeddings=True,
                            convert_to_numpy=True,
                            show_progress_bar=False).astype(np.float32)
        q = torch.from_numpy(qv)
        if b["device"] == "cuda":
            q = q.half().cuda()
        scores = torch.matmul(b["vecs"], q.T).view(-1)
        k = min(50, scores.numel())
        top = (torch.topk(scores, k=k).indices.cpu().numpy() if k
               else np.array([], dtype=np.int64))
    bge_ids = [int(b["ids"][i]) for i in top]

    fused = {}
    for rank, cid in enumerate(fts_ids):
        fused[cid] = fused.get(cid, 0.0) + 1 / (60 + rank + 1)
    for rank, cid in enumerate(bge_ids):
        fused[cid] = fused.get(cid, 0.0) + 1 / (60 + rank + 1)
    cand = [cid for cid, _score in sorted(fused.items(), key=lambda kv: -kv[1])]
    cand = [cid for cid in cand
            if cid in b["meta"] and _v2_meta_ok(
                b["meta"][cid], view, source=source, lang=lang, book=book,
                document_id=document_id, section=section)]
    cand = cand[: config.RERANK_TOPK]
    if not cand:
        return []
    pairs = [(cid, b["texts"][cid]) for cid in cand]
    order = _v2_rerank(b, query, pairs)
    return [catalog.result_for_row(b["meta"][cid], score)
            for cid, score in order[:limit]]


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
    image = None
    if config.render_enabled():
        image = (f"/v1/pages?source={quote(row['source'])}"
                 f"&book={quote(row['book'])}&page={row['page']}")
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
            "role": "cite",
            "policy_version": citation_policy.version(),
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
        top = torch.topk(scores, k=min(config.BGE_TOPK, scores.numel())).indices.cpu().numpy()

    bge_ids = [int(b["ids"][i]) for i in top]
    # RRF fuse FTS rank + BGE rank, then rerank only the top candidates.
    fused = {}
    for rank, cid in enumerate(fts_ids):
        fused[cid] = fused.get(cid, 0) + 1 / (60 + rank + 1)
    for rank, cid in enumerate(bge_ids):
        fused[cid] = fused.get(cid, 0) + config.BGE_RRF_WEIGHT / (60 + rank + 1)
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


def _v2_rows(query, view, limit, source=None, lang=None, book=None,
             document_id=None, section=None):
    toks = textutil.tokens_v2(query)
    if not toks:
        return []
    sql = (
        "SELECT c.id, c.document_id, c.ordinal, c.section, c.text, c.lang,"
        " c.stream, c.locator_json, c.citation_label, c.quality,"
        " c.char_start, c.char_end, d.title, d.author, d.license,"
        " d.canonical_url, d.source_id, bm25(chunks_fts) AS rank "
        "FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid "
        "JOIN documents d ON d.document_id = c.document_id "
        "WHERE chunks_fts MATCH ? AND c.visibility = 'tutor'"
    )
    params = [" OR ".join(toks)]
    if view == "student":
        streams = config.STUDENT_STREAMS or ("text",)
        sql += " AND c.stream IN (%s)" % ",".join("?" * len(streams))
        params.extend(streams)
    if source:
        sql += " AND d.source_id = ?"
        params.append(source)
    if lang:
        sql += " AND c.lang = ?"
        params.append(lang)
    if document_id:
        sql += " AND c.document_id = ?"
        params.append(document_id)
    if book:
        sql += " AND (c.document_id = ? OR d.title = ?)"
        params.extend([book, book])
    if section:
        sql += " AND c.section = ?"
        params.append(section)
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)
    con = _connect()
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def _v2_result(row, score):
    return catalog.result_for_row(row, score)


def _v2_note_error(exc):
    global _V2_BGE_ERR
    if _V2_BGE is None:
        _V2_BGE_ERR = str(exc)[:300]


def _v2_hit_list(query, view, limit, source=None, lang=None, book=None,
                 document_id=None, section=None, use_bge=False):
    if use_bge:
        return _v2_bge_search(query, view, limit, source=source, lang=lang,
                              book=book, document_id=document_id,
                              section=section)
    rows = _v2_rows(query, view, limit, source=source, lang=lang, book=book,
                    document_id=document_id, section=section)
    return [_v2_result(r, -float(r["rank"])) for r in rows]


def _search_v2(query, view, limit, source=None, lang=None, book=None,
               document_id=None, section=None, session_id=None, turn=None,
               step=None, call_id=None):
    """Public-corpora search: FTS/BGE, plus translated query variants."""
    t0 = time.perf_counter()
    use_bge = (config.BGE and
               not v2_bge_status().startswith(("disabled", "missing", "error")))

    variants = []
    if str(config.TRANSLATE).lower() != "off":
        try:
            langs = translate.corpus_languages()
            variants = translate.expand(query, targets=langs) if langs else []
        except Exception:
            variants = []

    items = [{"lang": None, "text": query, "source": "query"}] + variants
    runs = []                      # (text, hits, rrf weight)
    bge_used = False
    for index, item in enumerate(items):
        item_bge = use_bge and (index == 0 or config.TRANSLATE_BGE)
        try:
            hits = _v2_hit_list(item["text"], view, limit, source=source,
                                lang=lang, book=book, document_id=document_id,
                                section=section, use_bge=item_bge)
            bge_used = bge_used or item_bge
        except Exception as e:
            if use_bge:
                _v2_note_error(e)
                use_bge = False
            hits = _v2_hit_list(item["text"], view, limit, source=source,
                                lang=lang, book=book, document_id=document_id,
                                section=section, use_bge=False)
        if index == 0:
            weight = 1.0
        elif item.get("source") == "llm":
            weight = config.TRANSLATE_LLM_WEIGHT
        elif str(item.get("lang") or "").startswith("zh"):
            weight = 0.8
        else:
            weight = config.TRANSLATE_WEIGHT
        runs.append((item["text"], hits, weight))

    lexical_counts = {"grep": 0, "lemma": 0}
    if str(config.LEXICAL).lower() != "off":
        for index, item in enumerate(items):
            text = item["text"]
            # Exact grep: always for the original query; for a translated
            # variant only when it is a single term (a keyword string is not a
            # quotation and would never match as a whole).
            if (len((text or "").strip()) >= 2 and
                    (index == 0 or not any(ch.isspace() for ch in text.strip()))):
                try:
                    got = lexical.grep(
                        text, view=view, limit=max(limit, 20), source=source,
                        lang=lang, book=book, document_id=document_id,
                        section=section)["results"]
                except Exception:
                    got = []
                if got:
                    runs.append((text, got, config.LEXICAL_GREP_WEIGHT))
                    lexical_counts["grep"] += len(got)
            if _CLASSICAL.search(text or ""):
                try:
                    got = lexical.lemma_search(
                        text, view=view, limit=max(limit, 20), source=source,
                        lang=lang, book=book, document_id=document_id,
                        section=section, min_coverage=0.6)["results"]
                except Exception:
                    got = []
                if got:
                    runs.append((text, got, config.LEXICAL_LEMMA_WEIGHT))
                    lexical_counts["lemma"] += len(got)

    if len(runs) == 1:
        results = runs[0][1][:limit]
    else:
        fused, best, coverage = {}, {}, {}
        for text, hits, weight in runs:
            terms = set(textutil.tokens_v2(text))
            for rank, hit in enumerate(hits):
                cid = hit["chunk_id"]
                fused[cid] = fused.get(cid, 0.0) + weight / (60 + rank + 1)
                # RRF ties are common across language variants; prefer the
                # candidate that actually contains more of that variant's terms.
                hits_terms = len(terms & set(textutil.tokens_v2(hit.get("text") or "")))
                coverage[cid] = max(coverage.get(cid, 0), hits_terms)
                if cid not in best or hit["score"] > best[cid]["score"]:
                    best[cid] = hit
        ordered = sorted(fused, key=lambda cid: (-fused[cid],
                                                 -coverage.get(cid, 0),
                                                 -best[cid]["score"]))[:limit]
        results = [best[cid] for cid in ordered]

    payload = {"query": query, "view": view, "schema": "v2",
               "mode": "bge+rerank-public" if bge_used else "fts-public",
               "results": results, "chapter": None,
               "translated": bool(variants), "translations": variants,
               "lexical": lexical_counts,
               "took_ms": round((time.perf_counter() - t0) * 1000, 2),
               "cached": False}
    _cite(payload, session_id, turn, step, call_id)
    return payload


def _v1_hit_list(query, vis, limit, source, lang, book, pages, use_bge):
    if use_bge:
        return _bge_search(query, vis, limit, source, lang, book, pages)
    rows = _fts_rows(query, vis, limit, source, lang, book, pages)
    return [_row_result(r, -float(r["rank"])) for r in rows]


def _v1_rerank(query, results, limit):
    """Rerank fused v1 candidates against the original query.

    Translated variants retrieve candidates with their own query; scoring all
    candidates against the original question keeps the cross-lingual recall
    without letting a variant's phrasing own the top-1.
    """
    if not results:
        return []
    import torch
    b = _load_bge()
    pairs = [(query, (r.get("text") or "")[:1200]) for r in results]
    scored, bs = [], 16
    for k in range(0, len(pairs), bs):
        batch = pairs[k:k + bs]
        enc = b["tok"]([p[0] for p in batch], [p[1] for p in batch],
                       padding=True, truncation=True, max_length=512,
                       return_tensors="pt").to(b["device"])
        with torch.no_grad():
            s = b["rer"](**enc).logits.view(-1).float().cpu().numpy()
        scored.extend(zip(results[k:k + bs], s.tolist()))
    scored.sort(key=lambda x: -x[1])
    out = []
    for hit, score in scored[:limit]:
        item = dict(hit)
        item["score"] = round(float(score), 4)
        item["similarity"] = item["score"]
        out.append(item)
    return out


def _search_v1_enhanced(query, view, limit, source=None, lang=None, book=None,
                        toc_source="library", session_id=None, turn=None,
                        step=None, call_id=None):
    """Opt-in v1 retrieval: translated variants + exact grep RRF."""
    t0 = time.perf_counter()
    vis = "tutor"
    rng = _range(book, None, toc_source)
    pages = None
    if rng:
        pages = (rng["page_start"], rng["page_end"])
    variants = []
    if str(config.TRANSLATE).lower() != "off":
        try:
            if not (config.V1_TRANSLATE_NONCJK_ONLY and textutil.CJK.search(query)):
                langs = translate.corpus_languages()
                variants = translate.expand(query, targets=langs) if langs else []
        except Exception:
            variants = []
    items = [{"lang": None, "text": query, "source": "query"}] + variants
    runs = []
    bge_used = False
    use_bge = bool(config.BGE)
    for index, item in enumerate(items):
        try:
            hits = _v1_hit_list(item["text"], vis, limit, source, lang, book,
                                pages, use_bge)
            bge_used = bge_used or use_bge
        except Exception as e:
            global _BGE_ERR
            _BGE_ERR = str(e)[:300]
            use_bge = False
            hits = _v1_hit_list(item["text"], vis, limit, source, lang, book,
                                pages, False)
        if index == 0:
            weight = 1.0
        elif item.get("source") == "llm":
            weight = config.TRANSLATE_LLM_WEIGHT
        elif str(item.get("lang") or "").startswith("zh"):
            weight = 0.8
        else:
            weight = config.TRANSLATE_WEIGHT
        runs.append((item["text"], hits, weight))

    lexical_counts = {"grep": 0, "lemma": 0, "greek_lemma": 0,
                      "commentary": 0, "edition_align": 0}
    if str(config.LEXICAL).lower() != "off":
        for index, item in enumerate(items):
            text = item["text"]
            if (len((text or "").strip()) >= 2 and
                    (index == 0 or not any(ch.isspace() for ch in text.strip()))):
                try:
                    got = lexical.grep(
                        text, view=view, limit=max(limit, 20), source=source,
                        lang=lang, book=book)["results"]
                except Exception:
                    got = []
                if got:
                    runs.append((text, got, config.LEXICAL_GREP_WEIGHT))
                    lexical_counts["grep"] += len(got)

    if config.V1_GREEK_LEMMA and _GREEK_SCRIPT.search(query or ""):
        for item in items:
            text = item["text"]
            if not _GREEK_SCRIPT.search(text or ""):
                continue
            try:
                got = lexical.greek_lemma_search(
                    text, view=view, limit=max(limit, 20), source=source,
                    lang=lang, book=book)["results"]
            except Exception:
                got = []
            if got:
                runs.append((text, got, config.V1_GREEK_LEMMA_WEIGHT))
                lexical_counts["greek_lemma"] += len(got)

    if config.V1_COMMENTARY and not textutil.CJK.search(query or ""):
        for item in items:
            text = item["text"]
            if not re.search(r"[A-Za-z]{3,}", text or ""):
                continue
            try:
                got = lexical.commentary_search(
                    text, view=view, limit=max(limit, 20), source=source,
                    lang=lang, book=book)["results"]
            except Exception:
                got = []
            if got:
                runs.append((text, got, config.V1_COMMENTARY_WEIGHT))
                lexical_counts["commentary"] += len(got)

    if config.V1_EDITION_ALIGN and not book and runs:
        aligned, seen = [], set()
        for hit in runs[0][1][:5]:
            for ob, op, score in editions.align_pages(
                    hit.get("book"), hit.get("page"))[:config.V1_EDITION_ALIGN_TOPK]:
                if (ob, op) in seen or (ob, op) == (hit.get("book"), hit.get("page")):
                    continue
                seen.add((ob, op))
                con = _connect()
                try:
                    sql = ("SELECT id, source, book, lang, page, text FROM chunks"
                           " WHERE book=? AND page=? AND visibility='tutor'")
                    params = [ob, op]
                    if source:
                        sql += " AND source=?"
                        params.append(source)
                    row = con.execute(sql + " ORDER BY id LIMIT 1",
                                      params).fetchone()
                finally:
                    con.close()
                if row is not None:
                    item = _row_result(row, max(0.5, float(score)))
                    aligned.append(item)
                if len(aligned) >= 20:
                    break
            if len(aligned) >= 20:
                break
        if aligned:
            runs.append((query, aligned, config.V1_EDITION_ALIGN_WEIGHT))
            lexical_counts["edition_align"] = len(aligned)

    fused, best, coverage = {}, {}, {}
    for text, hits, weight in runs:
        terms = set(textutil.tokens(text))
        for rank, hit in enumerate(hits):
            cid = hit["chunk_id"]
            fused[cid] = fused.get(cid, 0.0) + weight / (60 + rank + 1)
            hits_terms = len(terms & set(textutil.tokens(hit.get("text") or "")))
            coverage[cid] = max(coverage.get(cid, 0), hits_terms)
            if cid not in best or hit["score"] > best[cid]["score"]:
                best[cid] = hit
    ordered = sorted(fused, key=lambda cid: (-fused[cid],
                                             -coverage.get(cid, 0),
                                             -best[cid]["score"]))[:limit]
    if config.V1_PAGE_DEDUPE:
        seen, unique = set(), []
        for cid in ordered:
            hit = best[cid]
            key = (hit.get("source"), hit.get("book"), hit.get("page"))
            if key in seen:
                continue
            seen.add(key)
            unique.append(cid)
        ordered = unique
    if config.V1_ANCHOR_BASE and runs and runs[0][1]:
        base = [hit["chunk_id"] for hit in runs[0][1][:max(1, config.V1_ANCHOR_TOPK)]]
        ordered = base + [c for c in ordered if c not in base]
    payload = {"query": query, "view": view, "results": [best[c] for c in ordered][:limit],
               "chapter": rng,
               "mode": "bge+rerank" if bge_used else "fts",
               "translated": bool(variants), "translations": variants,
               "lexical": lexical_counts,
               "took_ms": round((time.perf_counter() - t0) * 1000, 2),
               "cached": False}
    if config.V1_FINAL_RERANK and len(runs) > 1 and payload["results"]:
        try:
            payload["results"] = _v1_rerank(query, payload["results"], limit)
        except Exception:
            pass
    _cite(payload, session_id, turn, step, call_id)
    return payload


def search(query: str, view: str = "student", limit: int = 8,
           source: str | None = None, lang: str | None = None,
           book: str | None = None, chapter=None, toc_source: str = "library",
           session_id: str | None = None, turn: int | None = None,
           step: int | None = None, call_id: str | None = None,
           document_id: str | None = None, section: str | None = None,
           scope: str | None = None):
    if view not in ("student", "tutor"):
        raise ValueError("view must be student or tutor")
    if scope not in (None, "", "auto", "all", "routed"):
        raise ValueError("scope must be auto, all or routed")
    if scope == "all":
        from . import federated
        return federated.search_all(
            query, view=view, limit=limit, source=source, lang=lang, book=book,
            document_id=document_id, section=section, session_id=session_id,
            turn=turn, step=step, call_id=call_id)
    if scope == "routed":
        from . import federated
        return federated.search_routed(
            query, view=view, limit=limit, source=source, lang=lang, book=book,
            document_id=document_id, section=section, session_id=session_id,
            turn=turn, step=step, call_id=call_id)
    vis = "tutor"  # current corpus: student == tutor minus answer_key
    limit = max(1, min(int(limit), 20))

    if config.schema_version() == "v2":
        return _search_v2(query, view=view, limit=limit, source=source,
                          lang=lang, book=book, document_id=document_id,
                          section=section or chapter, session_id=session_id,
                          turn=turn, step=step, call_id=call_id)

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
                    "role": "cite",
                    "policy_version": citation_policy.version(),
                    "page_image": pages_out[0]["page_image"],
                },
            }], turn=turn, step=step, call_id=call_id)
        return payload

    if config.V1_RETRIEVAL:
        return _search_v1_enhanced(query, view=view, limit=limit, source=source,
                                   lang=lang, book=book,
                                   toc_source=toc_source, session_id=session_id,
                                   turn=turn, step=step, call_id=call_id)

    # render mode belongs in the key: the same query returns citations with or
    # without a page image depending on it, and the cache must not leak one mode
    # into the other.
    key = (query, vis, limit, source, lang, book, pages, config.BGE,
           config.render_enabled())
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
