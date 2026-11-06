"""Cross-edition page alignment for v1 classical texts.

The same work often has several PDFs with different page numbers. A retrieval
hit in one edition can be mapped to the corresponding page in the others by
comparing the Greek/Latin token set of each page. The alignment is lazy (per
work) and cached for the configured database.
"""
import os
import re
import sqlite3
import threading

from . import config, textutil

_CACHE = {}
_LOCK = threading.Lock()
_GREEK = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]{3,}")
_LATIN = re.compile(r"[A-Za-z]{4,}")
_STOP = {"the", "and", "with", "from", "that", "this", "which", "what",
         "when", "where", "they", "their", "have", "been", "were", "will",
         "would", "could", "should", "there", "about", "into", "than"}


def _connect():
    con = sqlite3.connect(config.DB, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def _tokens(text, lang):
    if lang == "greek":
        return {textutil.fold_diacritics(w).lower()
                for w in _GREEK.findall(text or "")}
    return {w.lower() for w in _LATIN.findall(text or "")
            if w.lower() not in _STOP}


def _build(work):
    con = _connect()
    try:
        books = con.execute(
            "SELECT DISTINCT book, lang FROM chunks WHERE visibility='tutor'"
            " AND lang IN ('greek','latin') AND book LIKE ?",
            (work + "__%",)).fetchall()
        if len(books) < 2:
            return {}
        pages = {}
        for book_row in books:
            book, lang = book_row["book"], book_row["lang"]
            rows = con.execute(
                "SELECT DISTINCT page FROM chunks WHERE book=?"
                " AND visibility='tutor'", (book,)).fetchall()
            pages[book] = {}
            for row in rows:
                page = row["page"]
                texts = con.execute(
                    "SELECT text FROM chunks WHERE book=? AND page=?"
                    " AND visibility='tutor'", (book, page)).fetchall()
                pages[book][page] = _tokens(
                    " ".join(t[0] or "" for t in texts), lang)
    finally:
        con.close()

    maps = {book: {} for book in pages}
    books = list(pages)
    for a in books:
        for b in books:
            if a == b:
                continue
            index = {}
            for page, toks in pages[b].items():
                for tok in toks:
                    index.setdefault(tok, []).append(page)
            for page, toks in pages[a].items():
                if len(toks) < 4:
                    continue
                cand = {}
                for tok in toks:
                    for other in index.get(tok, ()):
                        cand[other] = cand.get(other, 0) + 1
                scored = []
                for other, overlap in cand.items():
                    union = len(toks) + len(pages[b][other]) - overlap
                    score = overlap / max(1, union)
                    if score >= 0.10:
                        scored.append((score, other))
                scored.sort(reverse=True)
                maps[a][page] = [(b, other, round(score, 3))
                                 for score, other in scored[:2]]
    return maps


def align_pages(book, page):
    """Return [(other_book, other_page, score)] for the same passage."""
    if not book or page is None or "__" not in book:
        return []
    work = book.split("__")[0]
    try:
        mtime = os.path.getmtime(config.DB)
    except OSError:
        return []
    key = (os.path.abspath(config.DB), mtime, work)
    with _LOCK:
        if key not in _CACHE:
            _CACHE[key] = _build(work)
        maps = _CACHE[key]
    return maps.get(book, {}).get(page, [])
