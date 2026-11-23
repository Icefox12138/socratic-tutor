"""Curriculum lesson packs (schema v1): a framework, not content.

The engine does not ship courses. It ships the *contract* a course must satisfy
and the endpoint that serves one, so a third party can author lessons without
touching code:

    line → course → unit → lesson  (one JSON file per lesson)

A lesson names a passage (source/book/page range), a vocabulary list (headwords
resolved against the lexicon database when one is present), grammar references,
a short background, one worked example, reading questions with their page
anchors, and review-card seeds. See docs/CURRICULUM-SCHEMA.md for the contract.

Loading is deliberately lenient at runtime and strict in the checker
(scripts/curriculum_check.py): a malformed lesson is skipped, never fatal.
"""
import json
import os
import re

from . import config, lexicon

SCHEMA = 1
LESSON_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def _dir():
    return config.CURRICULUM


def _files():
    d = _dir()
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d) if f.endswith(".json"))


def validate(pack):
    """Return a list of human-readable problems (empty = valid)."""
    errs = []
    if not isinstance(pack, dict):
        return ["root must be an object"]
    if pack.get("schema") != SCHEMA:
        errs.append("schema must be %d" % SCHEMA)
    lesson_id = pack.get("lesson_id")
    if not isinstance(lesson_id, str) or not LESSON_ID.match(lesson_id or ""):
        errs.append("lesson_id must match [a-z0-9][a-z0-9._-]*")
    for key in ("line", "title"):
        if not isinstance(pack.get(key), str) or not pack.get(key).strip():
            errs.append("%s must be a non-empty string" % key)
    for key in ("unit", "lesson"):
        v = pack.get(key)
        if not isinstance(v, int) or v < 1:
            errs.append("%s must be an integer >= 1" % key)
    passage = pack.get("passage")
    if not isinstance(passage, dict):
        errs.append("passage must be an object")
    else:
        for key in ("source", "book"):
            if not isinstance(passage.get(key), str) or not passage.get(key).strip():
                errs.append("passage.%s must be a non-empty string" % key)
        start, end = passage.get("page_start"), passage.get("page_end")
        if not isinstance(start, int) or start < 1:
            errs.append("passage.page_start must be an integer >= 1")
        if not isinstance(end, int) or end < start:
            errs.append("passage.page_end must be an integer >= page_start")
    if not isinstance(pack.get("background"), str):
        errs.append("background must be a string (may be empty)")
    questions = pack.get("questions")
    if not isinstance(questions, list) or not questions:
        errs.append("questions must be a non-empty list")
    else:
        for i, q in enumerate(questions):
            if not isinstance(q, dict) or not isinstance(q.get("q"), str) or not q["q"].strip():
                errs.append("questions[%d].q must be a non-empty string" % i)
    cards = pack.get("review_cards")
    if not isinstance(cards, list) or not cards:
        errs.append("review_cards must be a non-empty list")
    else:
        for i, c in enumerate(cards):
            if not isinstance(c, dict) or not isinstance(c.get("term"), str) or not c["term"].strip():
                errs.append("review_cards[%d].term must be a non-empty string" % i)
    vocab = pack.get("vocab", [])
    if not isinstance(vocab, list):
        errs.append("vocab must be a list")
    else:
        for i, v in enumerate(vocab):
            if not isinstance(v, dict) or not isinstance(v.get("headword"), str) or not v["headword"].strip():
                errs.append("vocab[%d].headword must be a non-empty string" % i)
    grammar = pack.get("grammar", [])
    if not isinstance(grammar, list):
        errs.append("grammar must be a list")
    return errs


def _load(path):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def catalog():
    """Summaries of every lesson pack in the curriculum directory."""
    items = []
    for name in _files():
        pack = _load(os.path.join(_dir(), name))
        if pack is None or validate(pack):
            continue
        items.append({
            "lesson_id": pack["lesson_id"],
            "line": pack["line"],
            "title": pack["title"],
            "unit": pack["unit"],
            "lesson": pack["lesson"],
            "passage": pack["passage"],
            "file": name,
        })
    items.sort(key=lambda x: (x["line"], x["unit"], x["lesson"]))
    return {"schema": SCHEMA, "curriculum_dir": _dir(), "lessons": items}


def _resolve_vocab(pack):
    """Attach the first lexicon entry for each headword (None when no lexicon)."""
    out = []
    for item in pack.get("vocab") or []:
        entry = None
        try:
            lookup = lexicon.lookup(item["headword"],
                                    lang=item.get("lang"),
                                    area="dict", limit=1)
            if lookup.get("entries"):
                first = lookup["entries"][0]
                entry = {"headword": first.get("headword"),
                         "lemma": first.get("lemma"),
                         "pos": first.get("pos"),
                         "definition": (first.get("definition") or "")[:400],
                         "citation": first.get("citation")}
        except Exception:                    # no lexicon, bad db: degrade to None
            entry = None
        out.append({"headword": item["headword"], "lang": item.get("lang"),
                    "gloss": item.get("gloss"), "entry": entry})
    return out


def lesson(lesson_id):
    """One lesson, with vocab resolved; None if absent or invalid."""
    for name in _files():
        pack = _load(os.path.join(_dir(), name))
        if pack is None or pack.get("lesson_id") != lesson_id:
            continue
        if validate(pack):
            return None
        out = dict(pack)
        out["vocab"] = _resolve_vocab(pack)
        out["available"] = True
        return out
    return None
