"""Append-only evaluation log (P2-2)."""
import json
import os
import sqlite3
import time

from . import config


def _path(path=None):
    return path or config.STATE_DB


def init(path=None):
    p = _path(path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    con = sqlite3.connect(p)
    con.execute(
        "CREATE TABLE IF NOT EXISTS evaluations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "session_id TEXT NOT NULL,"
        "question TEXT, answer TEXT,"
        "result TEXT NOT NULL, confidence REAL,"
        "misconceptions TEXT, reason TEXT, source TEXT,"
        "created_at REAL NOT NULL)"
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_eval_session ON evaluations(session_id, id)")
    con.commit()
    con.close()
    return p


def save(session_id, question, answer, ev, path=None):
    p = init(path)
    con = sqlite3.connect(p)
    try:
        cur = con.execute(
            "INSERT INTO evaluations(session_id, question, answer, result, confidence,"
            " misconceptions, reason, source, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (session_id, question, answer, ev["result"], ev["confidence"],
             json.dumps(ev.get("misconceptions", []), ensure_ascii=False),
             ev.get("reason", ""), ev.get("source", ""), time.time()))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def list_for(session_id, limit=50, path=None):
    p = init(path)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            "SELECT * FROM evaluations WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, max(1, min(int(limit), 200)))).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["misconceptions"] = json.loads(d.get("misconceptions") or "[]")
        except Exception:
            d["misconceptions"] = []
        out.append(d)
    return out
