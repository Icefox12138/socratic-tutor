"""Federated v1 (private PDF) + v2 (public corpora) search.

The two catalogues are separate SQLite files with separate vector files. This
module serialises config switching, runs each catalogue, then merges by RRF.
Only `scope=all` uses it; normal searches are unchanged.
"""
import os
import re
import threading
import time

from . import config, search, translate

_LOCK = threading.Lock()
_GREEK = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
_V2_WORK = ("iliad", "aeneid", "史記", "史记", "homer", "virgil", "vergil")


def _probe(db, is_v1, query):
    config.DB = db
    config.SCHEMA = "auto"
    if is_v1:
        config.BGE_VECTORS = config.V1_BGE_VECTORS
        config.BGE_IDS = config.V1_BGE_IDS
    try:
        if is_v1:
            return len(search._fts_rows(query, "tutor", 3, None, None, None, None))
        return len(search._v2_rows(query, "tutor", 3, None, None, None, None, None))
    except Exception:
        return 0


def _route(query):
    q = (query or "").casefold()
    classical_zh = any(m.lower() in q for m in translate.ZH_HISTORY_MARKERS)
    greek = bool(_GREEK.search(query or ""))
    work = any(w in q for w in _V2_WORK)
    reason = "v1-default"
    if classical_zh:
        reason = "classical-zh"
    elif work:
        reason = "v2-work"
    elif greek and len(q) <= 80:
        reason = "greek-quote"
    return reason, classical_zh or work or (greek and len(q) <= 80)


def search_routed(query, view="student", limit=8, source=None, lang=None,
                  book=None, document_id=None, section=None, session_id=None,
                  turn=None, step=None, call_id=None):
    """Route to one catalogue using cheap FTS probes, then search only it."""
    t0 = time.perf_counter()
    v1 = config.V1_DB if os.path.exists(config.V1_DB) else None
    v2 = config.PUBLIC_DB if os.path.exists(config.PUBLIC_DB) else None
    if not v1 and not v2:
        raise RuntimeError("no catalogue configured")
    reason, prefer_v2 = _route(query)
    probe = {}
    with _LOCK:
        snap = _snapshot()
        try:
            if v1:
                probe["v1"] = _probe(v1, True, query)
            if v2:
                probe["v2"] = _probe(v2, False, query)
        finally:
            _restore(snap)
    if prefer_v2 and v2 and probe.get("v2", 0) > 0:
        chosen, other = "v2", "v1"
    elif v1 and probe.get("v1", 0) > 0:
        chosen, other = "v1", "v2"
    elif v2 and probe.get("v2", 0) > 0:
        chosen, other = "v2", "v1"
    else:
        chosen, other = ("v1", "v2") if v1 else ("v2", "v1")
    paths = {"v1": v1, "v2": v2}
    payload, errors = None, []
    with _LOCK:
        snap = _snapshot()
        try:
            payload = _run_one(paths[chosen], chosen == "v1", query, view, limit,
                               source, lang, book, document_id, section)
        except Exception as e:
            errors.append({"schema": chosen, "error": str(e)[:200]})
        finally:
            _restore(snap)
    if payload is None or not payload.get("results"):
        if paths.get(other):
            with _LOCK:
                snap = _snapshot()
                try:
                    payload = _run_one(paths[other], other == "v1", query, view,
                                       limit, source, lang, book, document_id,
                                       section)
                    reason += "+fallback"
                    chosen = other
                except Exception as e:
                    errors.append({"schema": other, "error": str(e)[:200]})
                finally:
                    _restore(snap)
    if payload is None:
        raise RuntimeError("both catalogues failed: %s" % errors)
    if chosen == "v2" and reason == "v1-default":
        reason = "v2-coverage"
    payload["mode"] = "routed"
    payload["schema"] = "federated"
    for hit in payload.get("results") or []:
        hit["schema"] = chosen
    payload["routed_to"] = chosen
    payload["route_reason"] = reason
    payload["route_probe"] = probe
    payload["errors"] = errors
    payload["took_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    search._cite(payload, session_id, turn, step, call_id)
    return payload



def _snapshot():
    return (config.DB, config.SCHEMA, config.BGE_VECTORS, config.BGE_IDS)


def _restore(snap):
    config.DB, config.SCHEMA, config.BGE_VECTORS, config.BGE_IDS = snap


def _run_one(db, is_v1, query, view, limit, source, lang, book, document_id,
             section):
    config.DB = db
    config.SCHEMA = "auto"
    if is_v1:
        config.BGE_VECTORS = config.V1_BGE_VECTORS
        config.BGE_IDS = config.V1_BGE_IDS
    payload = search.search(query, view=view, limit=limit, source=source,
                            lang=lang, book=book, document_id=document_id,
                            section=section)
    payload["schema"] = "v1" if is_v1 else "v2"
    return payload


def search_all(query, view="student", limit=8, source=None, lang=None,
               book=None, document_id=None, section=None, session_id=None,
               turn=None, step=None, call_id=None):
    t0 = time.perf_counter()
    dbs = []
    for db, is_v1 in ((config.V1_DB, True), (config.PUBLIC_DB, False)):
        if db and os.path.exists(db) and all(db != seen for seen, _ in dbs):
            dbs.append((db, is_v1))
    if not dbs:
        raise RuntimeError("no catalogue configured")
    payloads, errors = [], []
    with _LOCK:
        snap = _snapshot()
        try:
            for db, is_v1 in dbs:
                try:
                    payloads.append(_run_one(
                        db, is_v1, query, view, limit, source, lang, book,
                        document_id, section))
                except Exception as e:
                    errors.append({"schema": "v1" if is_v1 else "v2",
                                   "error": str(e)[:200]})
        finally:
            _restore(snap)

    fused, best = {}, {}
    lexical = {"grep": 0, "lemma": 0}
    translated = False
    for payload in payloads:
        schema = payload.get("schema")
        translated = translated or bool(payload.get("translated"))
        for key in lexical:
            lexical[key] += int((payload.get("lexical") or {}).get(key, 0))
        for rank, hit in enumerate(payload.get("results") or []):
            item = dict(hit)
            item["schema"] = schema
            key = (schema, item.get("chunk_id"))
            fused[key] = fused.get(key, 0.0) + 1.0 / (60 + rank + 1)
            if key not in best or item.get("score", 0) > best[key].get("score", 0):
                best[key] = item
    ordered = sorted(fused, key=lambda k: (-fused[k], -best[k].get("score", 0)))
    results = [best[k] for k in ordered[:limit]]
    out = {"query": query, "view": view, "schema": "federated",
           "mode": "federated", "results": results,
           "schemas": [p.get("schema") for p in payloads],
           "translated": translated, "lexical": lexical,
           "errors": errors,
           "took_ms": round((time.perf_counter() - t0) * 1000, 2),
           "cached": False}
    for key in ("translations", "chapter"):
        if any(key in p for p in payloads):
            out[key] = next((p[key] for p in payloads if key in p), None)
    search._cite(out, session_id, turn, step, call_id)
    return out
