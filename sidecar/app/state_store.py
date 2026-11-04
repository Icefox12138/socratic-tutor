"""Event-sourced teaching sessions (P2-7)."""
import json
import os
import sqlite3
import time

from . import config, state_machine


def _conn(path=None):
    p = path or config.STATE_DB
    os.makedirs(os.path.dirname(p), exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.execute(
        "CREATE TABLE IF NOT EXISTS sessions ("
        "session_id TEXT PRIMARY KEY, goal TEXT, concept TEXT, lang TEXT,"
        "created_at REAL, updated_at REAL)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS state_events ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,"
        "seq INTEGER NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL,"
        "state_after TEXT, created_at REAL NOT NULL,"
        "UNIQUE(session_id, seq))"
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON state_events(session_id, seq)")
    con.commit()
    return con


def create_session(session_id, goal="", concept="", lang="zh", state=None, path=None):
    con = _conn(path)
    try:
        con.execute("DELETE FROM state_events WHERE session_id=?", (session_id,))
        now = time.time()
        con.execute(
            "INSERT OR REPLACE INTO sessions(session_id,goal,concept,lang,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?)", (session_id, goal, concept, lang, now, now))
        con.execute(
            "INSERT INTO state_events(session_id,seq,kind,payload,state_after,created_at)"
            " VALUES(?,?,?,?,?,?)",
            (session_id, 1, "init", json.dumps({"goal": goal, "concept": concept, "lang": lang},
                                               ensure_ascii=False),
             json.dumps(state.to_dict() if state else {}, ensure_ascii=False), now))
        con.commit()
    finally:
        con.close()


def append_event(session_id, event, payload, state, path=None):
    con = _conn(path)
    try:
        row = con.execute("SELECT COALESCE(MAX(seq),0) FROM state_events WHERE session_id=?",
                          (session_id,)).fetchone()
        seq = int(row[0]) + 1
        now = time.time()
        con.execute(
            "INSERT INTO state_events(session_id,seq,kind,payload,state_after,created_at)"
            " VALUES(?,?,?,?,?,?)",
            (session_id, seq, "step", json.dumps(payload, ensure_ascii=False),
             json.dumps(state.to_dict(), ensure_ascii=False), now))
        con.execute("UPDATE sessions SET updated_at=? WHERE session_id=?", (now, session_id))
        con.commit()
        return seq
    finally:
        con.close()


def get_session(session_id, path=None):
    con = _conn(path)
    try:
        r = con.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        return dict(r) if r else None
    finally:
        con.close()


def events(session_id, path=None):
    con = _conn(path)
    try:
        rows = con.execute(
            "SELECT seq, kind, payload, state_after, created_at FROM state_events"
            " WHERE session_id=? ORDER BY seq", (session_id,)).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload"] or "{}")
        d["state_after"] = json.loads(d["state_after"] or "{}")
        out.append(d)
    return out


def _replay(session_id, path=None):
    row = get_session(session_id, path)
    if not row:
        return None, 0
    s = state_machine.init(session_id, goal=row.get("goal") or "",
                           concept=row.get("concept") or "", lang=row.get("lang") or "zh")
    n = 0
    for ev in events(session_id, path):
        if ev["kind"] != "step":
            continue
        p = ev["payload"]
        state_machine.step(s, p.get("event"), p.get("result"),
                           text=p.get("text"), rubric=p.get("rubric"),
                           expected=p.get("expected"))
        if ev.get("state_after", {}).get("mastery") is not None:
            s.mastery = ev["state_after"]["mastery"]
        n += 1
    return s, n


def load_state(session_id, path=None):
    return _replay(session_id, path)


def replay(session_id, path=None):
    s, n = _replay(session_id, path)
    if not s:
        return None
    return {"state": s.to_dict(), "summary": state_machine.summary(s),
            "allowed_events": state_machine.allowed(s), "events": n}
