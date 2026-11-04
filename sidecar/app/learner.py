"""Learner model: BKT mastery per concept + FSRS cards (P2-3)."""
import os
import sqlite3
import time
from datetime import datetime, timezone

from . import config

P_INIT = 0.3
P_LEARN = 0.15
P_GUESS = 0.2
P_SLIP = 0.1

try:
    from fsrs import Card, Rating, Scheduler, State
except Exception:  # pragma: no cover
    Card = Rating = Scheduler = State = None

_SCHED = Scheduler() if Scheduler else None


def _path(path=None):
    return path or config.STATE_DB


def _conn(path=None):
    p = _path(path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.execute(
        "CREATE TABLE IF NOT EXISTS mastery ("
        "concept TEXT PRIMARY KEY, p REAL NOT NULL, attempts INTEGER DEFAULT 0,"
        "correct INTEGER DEFAULT 0, partial INTEGER DEFAULT 0, wrong INTEGER DEFAULT 0,"
        "updated_at REAL)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS cards ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, term TEXT NOT NULL, definition TEXT,"
        "lang TEXT, state INTEGER, step INTEGER, stability REAL, difficulty REAL,"
        "due TEXT, last_review TEXT, reps INTEGER DEFAULT 0, lapses INTEGER DEFAULT 0)"
    )
    con.commit()
    return con


def level(p: float) -> str:
    if p < 0.35:
        return "未掌握"
    if p <= 0.75:
        return "在学"
    return "已掌握"


def bkt_update(p: float, result: str, revealed: bool = False) -> float:
    p = max(0.001, min(0.999, p))
    if result == "correct":
        num = p * (1 - P_SLIP)
        den = num + (1 - p) * P_GUESS
        post = num / den if den else p
    elif result == "wrong":
        num = p * P_SLIP
        den = num + (1 - p) * (1 - P_GUESS)
        post = num / den if den else p
    else:
        num_c = p * (1 - P_SLIP)
        den_c = num_c + (1 - p) * P_GUESS
        num_w = p * P_SLIP
        den_w = num_w + (1 - p) * (1 - P_GUESS)
        post = 0.5 * (num_c / den_c + num_w / den_w)
    p2 = post + (1 - post) * P_LEARN
    if revealed:
        p2 *= 0.5
    return max(0.001, min(0.999, p2))


def get(concept: str, path=None) -> dict:
    con = _conn(path)
    try:
        r = con.execute("SELECT * FROM mastery WHERE concept=?", (concept,)).fetchone()
    finally:
        con.close()
    if not r:
        return {"concept": concept, "p": P_INIT, "level": level(P_INIT),
                "attempts": 0, "correct": 0, "partial": 0, "wrong": 0}
    d = dict(r)
    d["level"] = level(d["p"])
    return d


def record(concept: str, result: str, revealed: bool = False, path=None) -> dict:
    if result not in ("correct", "partial", "wrong"):
        raise ValueError("result must be correct/partial/wrong")
    before = get(concept, path)
    after = bkt_update(before["p"], result, revealed)
    con = _conn(path)
    try:
        con.execute(
            "INSERT INTO mastery(concept,p,attempts,correct,partial,wrong,updated_at) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(concept) DO UPDATE SET "
            "p=excluded.p, attempts=mastery.attempts+1, "
            "correct=mastery.correct+excluded.correct, "
            "partial=mastery.partial+excluded.partial, "
            "wrong=mastery.wrong+excluded.wrong, updated_at=excluded.updated_at",
            (concept, after, 1,
             1 if result == "correct" else 0,
             1 if result == "partial" else 0,
             1 if result == "wrong" else 0, time.time()))
        con.commit()
    finally:
        con.close()
    return {"concept": concept, "before": round(before["p"], 4), "after": round(after, 4),
            "level_before": before["level"], "level": level(after),
            "result": result, "revealed": revealed}


def list_all(path=None) -> list:
    con = _conn(path)
    try:
        rows = con.execute("SELECT * FROM mastery ORDER BY concept").fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        d = dict(r)
        d["level"] = level(d["p"])
        out.append(d)
    return out


_RATINGS = {"again": "Again", "hard": "Hard", "good": "Good", "easy": "Easy"}


def add_card(term: str, definition: str = "", lang: str = "zh", path=None) -> dict:
    if not _SCHED:
        raise RuntimeError("fsrs not installed")
    now = datetime.now(timezone.utc)
    card = Card(state=State.Learning, due=now)
    con = _conn(path)
    try:
        cur = con.execute(
            "INSERT INTO cards(term,definition,lang,state,step,stability,difficulty,due,"
            "last_review,reps,lapses) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (term, definition, lang, int(card.state), card.step or 0,
             card.stability, card.difficulty, card.due.isoformat(), None, 0, 0))
        con.commit()
        return {"id": cur.lastrowid, "term": term, "due": card.due.isoformat(),
                "state": int(card.state)}
    finally:
        con.close()


def review_card(card_id: int, rating: str, path=None) -> dict:
    if not _SCHED:
        raise RuntimeError("fsrs not installed")
    key = _RATINGS.get(str(rating).lower())
    if not key:
        raise ValueError("rating must be again/hard/good/easy")
    con = _conn(path)
    try:
        r = con.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        if not r:
            raise KeyError("card not found")
        d = dict(r)
        card = Card(card_id=d["id"], state=State(d["state"]) if d["state"] else State.Learning,
                    step=d["step"] or 0, stability=d["stability"],
                    difficulty=d["difficulty"],
                    due=datetime.fromisoformat(d["due"]) if d["due"] else None,
                    last_review=datetime.fromisoformat(d["last_review"]) if d["last_review"] else None)
        new, _log = _SCHED.review_card(card, getattr(Rating, key))
        reps = (d["reps"] or 0) + 1
        lapses = (d["lapses"] or 0) + (1 if key == "Again" else 0)
        con.execute(
            "UPDATE cards SET state=?,step=?,stability=?,difficulty=?,due=?,last_review=?,"
            "reps=?,lapses=? WHERE id=?",
            (int(new.state), new.step or 0, new.stability, new.difficulty,
             new.due.isoformat() if new.due else None,
             datetime.now(timezone.utc).isoformat(), reps, lapses, card_id))
        con.commit()
        return {"id": card_id, "due": new.due.isoformat() if new.due else None,
                "state": int(new.state), "stability": new.stability,
                "difficulty": new.difficulty, "reps": reps, "lapses": lapses}
    finally:
        con.close()


def due_cards(limit: int = 20, path=None) -> list:
    now = datetime.now(timezone.utc).isoformat()
    con = _conn(path)
    try:
        rows = con.execute(
            "SELECT * FROM cards WHERE due IS NULL OR due <= ? ORDER BY due LIMIT ?",
            (now, max(1, min(int(limit), 100)))).fetchall()
    finally:
        con.close()
    return [dict(r) for r in rows]
