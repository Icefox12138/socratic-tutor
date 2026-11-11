"""Grep and lemma retrieval: the lexical supplement to FTS/BGE.

grep is an exact-substring channel (quotes, names, formulas, identifiers).
lemma folds inflected Greek/Latin forms so ``ira`` can find ``iram`` and
``μῆνις`` can find ``μῆνιν``. It is not a replacement for hybrid retrieval; it
is the precision channel the corpus needs for citation checks.

v1 (PDF pages) supports grep; lemma needs the v2 clean-text catalogue.
"""
import math
import os
import re
import sqlite3

from . import config
import threading
import time
from functools import lru_cache

from . import catalog, config, schema, textutil

try:                                    # optional: pip install simplemma
    import simplemma as _simplemma
except Exception:                       # pragma: no cover - depends on install
    _simplemma = None

MAX_SCAN = config.LEMMA_SCAN
WINDOW = 60

_GREEK = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
_GREEK_SUFFIXES = tuple(s.replace("\u03c2", "\u03c3") for s in (
    "οιο", "ους", "οις", "ων", "ην", "ης", "ας", "ες", "ον", "οι",
    "αι", "ει", "ου", "ιν", "ις", "ω", "α", "η", "ι", "ο", "υ", "ς",
))
_LATIN_SUFFIXES = (
    "onibus", "erunt", "orum", "arum", "erum", "onis", "onem", "ibus",
    "avit", "atus", "ata", "atum", "que", "ere", "ate", "ant", "ent",
    "am", "as", "em", "es", "is", "os", "us", "um", "ae", "an", "it",
    "i", "o", "a", "e",
)


def _connect():
    con = config.open_db(config.DB)
    con.row_factory = sqlite3.Row
    return con


def _filters(ver, view, source, lang, book, document_id, section, alias=""):
    sql, params = [], []
    pre = alias + "." if alias else ""
    if ver == "v2" and view == "student":
        streams = config.STUDENT_STREAMS or ("text",)
        sql.append("%sstream IN (%s)" % (pre, ",".join("?" * len(streams))))
        params.extend(streams)
    if source:
        if ver == "v2":
            sql.append("d.source_id = ?")
        else:
            sql.append("source = ?")
        params.append(source)
    if lang:
        sql.append("%slang = ?" % pre)
        params.append(lang)
    if document_id:
        if ver != "v2":
            raise ValueError("document_id needs a v2 catalogue")
        sql.append("%sdocument_id = ?" % pre)
        params.append(document_id)
    if book:
        if ver == "v2":
            sql.append("(%sdocument_id = ? OR d.title = ?)" % pre)
            params.extend([book, book])
        else:
            sql.append("book = ?")
            params.append(book)
    if section:
        if ver != "v2":
            raise ValueError("section needs a v2 catalogue")
        sql.append("%ssection = ?" % pre)
        params.append(section)
    return sql, params


def _rows(view="student", source=None, lang=None, book=None, document_id=None,
          section=None, contains=None):
    ver = config.schema_version()
    if ver not in ("v1", "v2"):
        raise RuntimeError("no_index")
    con = _connect()
    try:
        if ver == "v2":
            sql = ("SELECT c.id, c.document_id, c.ordinal, c.section, c.text,"
                   " c.lang, c.stream, c.locator_json, c.citation_label,"
                   " c.quality, c.char_start, c.char_end, d.title, d.author,"
                   " d.license, d.canonical_url, d.source_id FROM chunks c"
                   " JOIN documents d ON d.document_id = c.document_id"
                   " WHERE c.visibility = 'tutor'")
        else:
            sql = ("SELECT id, source, book, lang, page, text FROM chunks"
                   " WHERE visibility = 'tutor'")
        clauses, params = _filters(ver, view, source, lang, book, document_id,
                                   section, alias="c" if ver == "v2" else "")
        if clauses:
            sql += " AND " + " AND ".join(clauses)
        if contains:
            text = "c.text" if ver == "v2" else "text"
            sql += (" AND (instr(%s, ?) > 0 OR instr(lower(%s), lower(?)) > 0)"
                    % (text, text))
            params.extend([contains, contains])
        sql += " ORDER BY id"
        return con.execute(sql, params).fetchall(), ver
    finally:
        con.close()


def _v1_result(row, score):
    from . import search
    return search._row_result(row, score)


def _with_match(result, text, query, score):
    low = (text or "").casefold()
    needle = (query or "").casefold()
    idx = low.find(needle)
    if idx < 0:
        return None
    start = max(0, idx - WINDOW)
    end = min(len(text), idx + len(needle) + WINDOW)
    out = dict(result)
    out["score"] = round(float(score), 4)
    out["similarity"] = out["score"]
    out["match"] = {"start": idx, "end": idx + len(needle),
                    "snippet": text[start:end],
                    "count": low.count(needle)}
    return out


def grep(query, view="student", limit=20, source=None, lang=None, book=None,
         document_id=None, section=None):
    """Exact substring search, case-insensitive via Unicode casefold()."""
    if view not in ("student", "tutor"):
        raise ValueError("view must be student or tutor")
    query = (query or "").strip()
    if not query or len(query) > 300:
        raise ValueError("query must be 1..300 chars")
    limit = max(1, min(int(limit), 50))
    t0 = time.perf_counter()
    rows, ver = _rows(view=view, source=source, lang=lang, book=book,
                      document_id=document_id, section=section,
                      contains=query)
    # SQLite lower() is ASCII-only; for accented Greek/Latin uppercase queries
    # fall back to a small in-memory scan (v2 catalogues are small by design).
    if not rows and ver == "v2" and not query.isascii():
        rows, ver = _rows(view=view, source=source, lang=lang, book=book,
                          document_id=document_id, section=section)
    results = []
    for row in rows:
        text = row["text"] or ""
        res = (catalog.result_for_row(dict(row), 1.0) if ver == "v2"
               else _v1_result(row, 1.0))
        hit = _with_match(res, text, query, 1.0)
        if hit:
            results.append(hit)
    results.sort(key=lambda x: (-x["match"]["count"], x["chunk_id"]))
    return {"query": query, "view": view, "schema": ver, "mode": "grep",
            "results": results[:limit],
            "took_ms": round((time.perf_counter() - t0) * 1000, 2)}


def _stem(token, lang):
    """Small fallback stemmer when simplemma is not installed.

    Deliberately crude: Greek/Latin inflection stripping plus a 4-character
    prefix. Good enough for retrieval; simplemma is preferred when present.
    """
    word = textutil.fold_diacritics(token).lower()
    if lang == "greek":
        for suffix in sorted(_GREEK_SUFFIXES, key=len, reverse=True):
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                word = word[:-len(suffix)]
                break
        word = word.replace("\u03c2", "\u03c3")
        return word[:4] if len(word) > 4 else word
    if lang == "latin":
        for suffix in sorted(_LATIN_SUFFIXES, key=len, reverse=True):
            if word.endswith(suffix) and len(word) - len(suffix) >= 2:
                word = word[:-len(suffix)]
                break
        return word[:4] if len(word) > 4 else word
    return word


@lru_cache(maxsize=65536)
def _lemma_keys(token, lang):
    keys = {_stem(token, lang)}
    if _simplemma is not None and lang in ("greek", "latin"):
        code = "grc" if lang == "greek" else "la"
        try:
            lemma = _simplemma.lemmatize(token, lang=code)
            if lemma:
                keys.add(textutil.fold_diacritics(lemma).lower()
                         .replace("\u03c2", "\u03c3"))
        except Exception:
            pass
    return frozenset(k for k in keys if k)


@lru_cache(maxsize=16384)
def _chunk_keys(text, lang):
    keys = set()
    for run in textutil.CJK.findall(text or ""):
        if len(run) == 1:
            keys.add(run)
        else:
            keys.update(run[i:i + 2] for i in range(len(run) - 1))
    for word in textutil.WORD_V2.findall(text or ""):
        code = "greek" if _GREEK.search(word) else "latin"
        keys.update(_lemma_keys(word, code))
    return frozenset(keys)


def _query_groups(query, lang=None):
    groups = []
    seen = set()
    for run in textutil.CJK.findall(query or ""):
        parts = [run] if len(run) == 1 else [run[i:i + 2] for i in range(len(run) - 1)]
        for part in parts:
            token = ("zh", part)
            if token not in seen:
                seen.add(token)
                groups.append({"lang": "zh", "token": part,
                               "keys": frozenset([part])})
    for word in textutil.WORD_V2.findall(query or ""):
        code = lang if lang in ("greek", "latin") else (
            "greek" if _GREEK.search(word) else "latin")
        keys = _lemma_keys(word, code)
        token = (code, tuple(sorted(keys)))
        if token not in seen:
            seen.add(token)
            groups.append({"lang": code, "token": word.lower(),
                           "keys": keys})
    return groups


_COMMENTARY_INDEX = None
_COMMENTARY_LOCK = threading.Lock()
_ENGLISH_WORD = re.compile(r"[A-Za-z]{3,}")
_ENGLISH_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "what", "does",
    "did", "how", "why", "when", "where", "which", "who", "whom", "whose",
    "are", "was", "were", "been", "being", "have", "has", "had", "not",
    "but", "into", "about", "than", "then", "they", "their", "them", "its",
    "his", "her", "she", "him", "you", "your", "our", "can", "could",
    "would", "should", "may", "might", "must", "will", "shall", "there",
}


def _commentary_index():
    """English-dominant chunks inside Greek/Latin books (notes/vocab)."""
    global _COMMENTARY_INDEX
    if config.schema_version() != "v1":
        return None
    try:
        mtime = os.path.getmtime(config.DB)
    except OSError:
        return None
    key = (os.path.abspath(config.DB), mtime)
    with _COMMENTARY_LOCK:
        if _COMMENTARY_INDEX and _COMMENTARY_INDEX[0] == key:
            return _COMMENTARY_INDEX[1]
        con = _connect()
        try:
            rows = con.execute(
                "SELECT id, text FROM chunks WHERE visibility='tutor'"
                " AND lang IN ('greek','latin')").fetchall()
        finally:
            con.close()
        postings = {}
        for row in rows:
            text = row["text"] or ""
            words = [w.lower() for w in _ENGLISH_WORD.findall(text)]
            if len(words) < 8:
                continue
            greek = len(_GREEK.findall(text))
            if greek / max(1, len(text)) > 0.35:
                continue
            for word in set(words):
                if word not in _ENGLISH_STOP:
                    postings.setdefault(word, []).append(row["id"])
        index = {"postings": postings, "n": len(rows)}
        _COMMENTARY_INDEX = (key, index)
        return index


def commentary_search(query, view="student", limit=20, source=None, lang=None,
                      book=None):
    """English-commentary retrieval over Greek/Latin books (v1)."""
    if config.schema_version() != "v1":
        return {"query": query, "mode": "commentary", "schema": "v1",
                "results": [], "took_ms": 0.0}
    terms = [w.lower() for w in _ENGLISH_WORD.findall(query or "")]
    terms = list(dict.fromkeys(w for w in terms if w not in _ENGLISH_STOP))
    if not terms:
        return {"query": query, "mode": "commentary", "schema": "v1",
                "results": [], "took_ms": 0.0}
    t0 = time.perf_counter()
    index = _commentary_index()
    postings, n = index["postings"], max(1, index["n"])
    scores, matched = {}, {}
    for term in terms:
        ids = postings.get(term)
        if not ids:
            continue
        weight = math.log(1.0 + n / (1.0 + len(ids)))
        for cid in ids:
            scores[cid] = scores.get(cid, 0.0) + weight
            matched[cid] = matched.get(cid, 0) + 1
    if not scores:
        return {"query": query, "mode": "commentary", "schema": "v1",
                "results": [], "took_ms": round((time.perf_counter() - t0) * 1000, 2)}
    ranked = sorted(scores, key=lambda cid: (-scores[cid], -matched[cid]))
    con = _connect()
    try:
        found = {}
        for start in range(0, len(ranked), 400):
            part = ranked[start:start + 400]
            marks = ",".join("?" * len(part))
            rows = con.execute(
                "SELECT id, source, book, lang, page, text FROM chunks"
                " WHERE id IN (%s) AND visibility='tutor'" % marks, part)
            for row in rows:
                found[row["id"]] = row
    finally:
        con.close()
    results = []
    for cid in ranked:
        row = found.get(cid)
        if row is None:
            continue
        if source and row["source"] != source:
            continue
        if book and row["book"] != book:
            continue
        from . import search
        item = search._row_result(row, scores[cid])
        item["match"] = {"coverage": round(matched[cid] / len(terms), 3)}
        results.append(item)
    results.sort(key=lambda x: (-x["score"], -x["match"]["coverage"]))
    return {"query": query, "mode": "commentary", "schema": "v1",
            "results": results[:limit],
            "took_ms": round((time.perf_counter() - t0) * 1000, 2)}



_GREEK_INDEX = None
_GREEK_LOCK = threading.Lock()


def _greek_index():
    """Inverted lemma/stem index over v1 Greek chunks, built once per DB."""
    global _GREEK_INDEX
    if config.schema_version() != "v1":
        return None
    try:
        mtime = os.path.getmtime(config.DB)
    except OSError:
        return None
    key = (os.path.abspath(config.DB), mtime)
    with _GREEK_LOCK:
        if _GREEK_INDEX and _GREEK_INDEX[0] == key:
            return _GREEK_INDEX[1]
        con = _connect()
        try:
            rows = con.execute(
                "SELECT id, text FROM chunks WHERE visibility='tutor'"
                " AND lang='greek'").fetchall()
        finally:
            con.close()
        postings = {}
        for row in rows:
            for lemma in _chunk_keys(row["text"] or "", "greek"):
                postings.setdefault(lemma, []).append(row["id"])
        index = {"postings": postings, "n": len(rows)}
        _GREEK_INDEX = (key, index)
        return index


def greek_lemma_search(query, view="student", limit=20, source=None,
                       lang=None, book=None):
    """v1 Greek-only lemma retrieval; returns page citations.

    This is the v1 counterpart of the v2 lemma channel: 33k Greek chunks are
    indexed once, so an English question translated to a Greek nominative can
    still find the inflected form on the page (φάσκε, Ἠελίοιο, ...).
    """
    if config.schema_version() != "v1":
        return {"query": query, "mode": "greek-lemma", "schema": "v1",
                "results": [], "took_ms": 0.0}
    groups = [g for g in _query_groups(query, "greek") if g["lang"] == "greek"]
    if not groups:
        return {"query": query, "mode": "greek-lemma", "schema": "v1",
                "results": [], "took_ms": 0.0}
    t0 = time.perf_counter()
    index = _greek_index()
    postings, n = index["postings"], max(1, index["n"])
    scores, matched = {}, {}
    for group in groups:
        best = None
        for lemma in group["keys"]:
            ids = postings.get(lemma)
            if ids and (best is None or len(ids) < len(best[1])):
                best = (lemma, ids)
        if not best:
            continue
        df = len(best[1])
        weight = math.log(1.0 + n / (1.0 + df))
        for cid in best[1]:
            scores[cid] = scores.get(cid, 0.0) + weight
            matched[cid] = matched.get(cid, 0) + 1
    if not scores:
        return {"query": query, "mode": "greek-lemma", "schema": "v1",
                "results": [], "took_ms": round((time.perf_counter() - t0) * 1000, 2)}
    ranked = sorted(scores, key=lambda cid: (-scores[cid], -matched[cid]))
    con = _connect()
    try:
        found = {}
        for start in range(0, len(ranked), 400):
            part = ranked[start:start + 400]
            marks = ",".join("?" * len(part))
            rows = con.execute(
                "SELECT id, source, book, lang, page, text FROM chunks"
                " WHERE id IN (%s) AND visibility='tutor'" % marks, part)
            for row in rows:
                found[row["id"]] = row
    finally:
        con.close()
    results = []
    for cid in ranked:
        row = found.get(cid)
        if row is None:
            continue
        if source and row["source"] != source:
            continue
        if book and row["book"] != book:
            continue
        coverage = matched[cid] / len(groups)
        score = scores[cid]
        from . import search
        item = search._row_result(row, score)
        item["match"] = {"coverage": round(coverage, 3),
                         "lemmas": [g["token"] for g in groups
                                    if any(k in postings for k in g["keys"])]}
        results.append(item)
    results.sort(key=lambda x: (-x["score"], -x["match"]["coverage"]))
    return {"query": query, "mode": "greek-lemma", "schema": "v1",
            "results": results[:limit],
            "took_ms": round((time.perf_counter() - t0) * 1000, 2)}

def lemma_search(query, view="student", limit=20, source=None, lang=None,
                 book=None, document_id=None, section=None, min_coverage=0.5):
    """Lemma/inflection-tolerant search over a v2 catalogue."""
    if view not in ("student", "tutor"):
        raise ValueError("view must be student or tutor")
    query = (query or "").strip()
    if not query:
        raise ValueError("query must not be empty")
    if config.schema_version() != "v2":
        raise ValueError("lemma search needs a v2 catalogue (clean text)")
    limit = max(1, min(int(limit), 50))
    groups = _query_groups(query, lang)
    if not groups:
        return {"query": query, "view": view, "schema": "v2", "mode": "lemma",
                "results": [], "took_ms": 0.0}
    t0 = time.perf_counter()
    rows, _ver = _rows(view=view, source=source, lang=lang, book=book,
                       document_id=document_id, section=section)
    truncated = len(rows) > MAX_SCAN
    rows = rows[:MAX_SCAN]
    cached = [(row, _chunk_keys(row["text"] or "", row["lang"] or ""))
              for row in rows]

    df = [0] * len(groups)
    for _row, keys in cached:
        for i, group in enumerate(groups):
            if group["keys"] & keys:
                df[i] += 1
    total = max(1, len(cached))
    weights = [math.log(1.0 + total / (1.0 + n)) for n in df]
    weight_sum = sum(weights) or 1.0

    exact_needle = textutil.fold_diacritics(query).lower()
    results = []
    for row, keys in cached:
        matched = [i for i, group in enumerate(groups)
                   if group["keys"] & keys]
        if not matched:
            continue
        coverage = len(matched) / len(groups)
        if coverage < min_coverage:
            continue
        score = sum(weights[i] for i in matched) / weight_sum
        if exact_needle and exact_needle in textutil.fold_diacritics(
                row["text"] or "").lower():
            score += 0.1
        res = catalog.result_for_row(dict(row), score)
        res["match"] = {
            "coverage": round(coverage, 3),
            "lemmas": [groups[i]["token"] for i in matched],
            "exact": exact_needle in textutil.fold_diacritics(
                row["text"] or "").lower(),
        }
        results.append(res)
    results.sort(key=lambda x: (-x["score"], -x["match"]["coverage"],
                                x["chunk_id"]))
    return {"query": query, "view": view, "schema": "v2", "mode": "lemma",
            "results": results[:limit], "truncated": truncated,
            "took_ms": round((time.perf_counter() - t0) * 1000, 2)}
