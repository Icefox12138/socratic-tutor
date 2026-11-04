"""Chapter index storage for the sidecar.

The 卷/篇 logic itself lives in the published `classics-index` package so there
is exactly one implementation (packages/classics-index). This module only adds
the SQLite `toc` table on top of it; import paths are re-exported so callers
keep writing `toc.find` / `toc.merge_pian` exactly as before.
"""
import json
import os
import sqlite3
import sys

from . import config

try:
    from classics_index.core import (  # noqa: F401 - re-exported
        CN_DIGITS, CN_UNITS, PIAN, VOL, at, bind_to_volume, build,
        build_from_volumes, clean_volumes, cn2int, enrich, find, merge_pian,
        pian_sequence, volume_of)
except ImportError:  # running from a checkout without the package installed
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", "packages", "classics-index"))
    from classics_index.core import (  # noqa: F401 - re-exported
        CN_DIGITS, CN_UNITS, PIAN, VOL, at, bind_to_volume, build,
        build_from_volumes, clean_volumes, cn2int, enrich, find, merge_pian,
        pian_sequence, volume_of)


def _conn(path=None):
    # Chapter rows are data, so they may live in the RAG database (config.toc_db())
    con = sqlite3.connect(path or config.toc_db())
    con.execute(
        "CREATE TABLE IF NOT EXISTS toc ("
        "source TEXT, book TEXT, ord INTEGER, level INTEGER, title TEXT,"
        "page_start INTEGER, page_end INTEGER, volume INTEGER, pages INTEGER,"
        "meta TEXT, PRIMARY KEY(source, book, ord))")
    con.commit()
    return con


def save(source, book, chapters, meta=None, path=None):
    con = _conn(path)
    try:
        con.execute("DELETE FROM toc WHERE source=? AND book=?", (source, book))
        for ch in chapters:
            con.execute(
                "INSERT INTO toc(source,book,ord,level,title,page_start,page_end,volume,pages,meta)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (source, book, ch.get("ord", 0), ch.get("level", 1), ch["title"],
                 ch["page_start"], ch["page_end"], ch.get("volume"),
                 ch.get("pages", ch["page_end"] - ch["page_start"] + 1),
                 json.dumps(meta or {}, ensure_ascii=False)))
        con.commit()
    finally:
        con.close()
    return len(chapters)


def load(source, book, path=None):
    con = _conn(path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT * FROM toc WHERE source=? AND book=? ORDER BY ord", (source, book)).fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]



def books(path=None):
    con = _conn(path)
    try:
        rows = con.execute("SELECT source, book, count(*) n FROM toc GROUP BY source, book").fetchall()
    finally:
        con.close()
    return [{"source": r[0], "book": r[1], "chapters": r[2]} for r in rows]
