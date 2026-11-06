"""Recent citations per DSH session/turn for the embedded UI."""
import os
import sqlite3
import time

from . import config


def _conn(path=None):
    p = path or config.STATE_DB
    os.makedirs(os.path.dirname(p), exist_ok=True)
    con = sqlite3.connect(p)
    con.execute(
        "CREATE TABLE IF NOT EXISTS citations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,"
        "turn INTEGER, step INTEGER, call_id TEXT,"
        "chunk_id INTEGER, source TEXT, book TEXT, page INTEGER, lang TEXT,"
        "document_id TEXT, scheme TEXT, url TEXT,"
        "locator TEXT, page_image TEXT, snippet TEXT, created_at REAL NOT NULL)"
    )
    cols = {r[1] for r in con.execute("PRAGMA table_info(citations)").fetchall()}
    for name, typ in (("turn", "INTEGER"), ("step", "INTEGER"), ("call_id", "TEXT"),
                      ("document_id", "TEXT"), ("scheme", "TEXT"), ("url", "TEXT")):
        if name not in cols:
            con.execute(f"ALTER TABLE citations ADD COLUMN {name} {typ}")
    con.execute("CREATE INDEX IF NOT EXISTS idx_cit_session ON citations(session_id, id)")
    con.commit()
    return con


def add_many(session_id, results, turn=None, step=None, call_id=None, path=None):
    if not session_id or not results:
        return 0
    con = _conn(path)
    try:
        now = time.time()
        for r in results:
            c = r.get("citation") or {}
            snippet = "" if r.get("image_only") else (r.get("text") or "")[:400]
            con.execute(
                "INSERT INTO citations(session_id,turn,step,call_id,chunk_id,source,book,page,"
                "lang,document_id,scheme,url,locator,page_image,snippet,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (session_id, turn, step, call_id, r.get("chunk_id"), r.get("source"),
                 r.get("book"), r.get("page"), r.get("lang"),
                 c.get("document_id") or r.get("document_id"), c.get("scheme"),
                 c.get("url"), c.get("locator"), c.get("page_image"), snippet, now))
        con.commit()
        return len(results)
    finally:
        con.close()


def list_for(session_id, limit=20, turn=None, path=None):
    con = _conn(path)
    con.row_factory = sqlite3.Row
    sql = "SELECT * FROM citations WHERE session_id=?"
    args = [session_id]
    if turn is not None:
        sql += " AND turn=?"
        args.append(int(turn))
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(max(1, min(int(limit), 100)))
    try:
        rows = con.execute(sql, args).fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]
