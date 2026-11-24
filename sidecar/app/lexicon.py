"""Dictionary / grammar lookup over `lexicon_headwords` (schema v2.1).

Two lookup shapes, both exact rather than vector:

  * dictionary — form → lemma → headword row → the entry chunk (`stream=definition`);
  * grammar    — `§N` → the section chunk (`stream=paradigm` or `text`).

The database is optional: a deployment without `lexicon.db` answers
`reason: "no_lexicon"` and the caller degrades, exactly like a missing public
catalogue. Nothing here writes.
"""
import os
import sqlite3
import threading

from . import citation_policy, config, lexical, locators

#: document kind by lexicon area; the policy resolves kinds to logical sources
AREA_KIND = {"dict": "dictionary", "grammar": "grammar"}


def _logical_source(area):
    """The policy's first `cite` source for this document kind, or None.

    The database stores edition names ("lsj", "ls", "alpheios"); the policy
    stores logical sources ("dict-lsj", "grammar-smyth", "grammar-ag"). Falling
    back through the policy keeps lexicon.py free of any one catalogue's source
    names — a deployment with its own lexicon.db and its own policy needs no
    code change here.
    """
    try:
        rule = citation_policy.resolve(doc_kind=AREA_KIND.get(area)) or {}
    except Exception:                     # a broken user policy must not break lookup
        return None
    for sid in rule.get("cite") or []:
        return str(sid)
    return None

#: Per-thread cache: one connection and one schema snapshot per database file.
#: Opening a 250 MB lexicon on every lookup cost ~56 ms, almost all of it in
#: repeated schema reads; the cache brings the steady state to a few ms. Tests
#: and database swaps call `reset()`.
_LOCAL = threading.local()


def _state():
    state = getattr(_LOCAL, "state", None)
    if state is None:
        state = _LOCAL.state = {"conns": {}, "schema": {}}
    return state


def available(path=None):
    return os.path.exists(path or config.LEXICON_DB)


def _connect(path=None):
    db = os.path.abspath(path or config.LEXICON_DB)
    state = _state()
    con = state["conns"].get(db)
    if con is None:
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row
        state["conns"][db] = con
    return db, con


def reset():
    """Close the cached connections (tests and database swaps call this)."""
    state = _state()
    for con in state["conns"].values():
        try:
            con.close()
        except Exception:
            pass
    state["conns"].clear()
    state["schema"].clear()


def _schema(con, db):
    """Cached tables, `chunks` columns and lexicon indexes for one file."""
    state = _state()
    if db not in state["schema"]:
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        cols = set()
        indexes = set()
        if "chunks" in tables:
            cols = {r[1] for r in con.execute("PRAGMA table_info(chunks)")}
        if "lexicon_headwords" in tables:
            indexes = {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND tbl_name='lexicon_headwords'")}
        state["schema"][db] = {"tables": tables, "chunk_cols": cols,
                               "indexes": indexes}
    return state["schema"][db]


def _tables(con, db):
    return _schema(con, db)["tables"]


def lemmas(form, lang=None):
    """Lookup keys for a surface form: the form itself plus lemma candidates."""
    keys = [str(form or "").strip()]
    try:
        for key in lexical._lemma_keys(str(form or ""), lang):
            if key and key not in keys:
                keys.append(key)
    except Exception:                     # simplemma absent or a bad language
        pass
    return [k for k in keys if k]


def _row_get(row, key, default=None):
    """sqlite3.Row is dict-like but raises on a missing key; databases in the
    wild predate some of the v2.1 columns."""
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


def _entry_chunk_id(value):
    """`entry_id` is an INTEGER in the v2.1 DDL and `"lsj:1"` in older lexicon
    databases; both point at a `chunks.id`."""
    if isinstance(value, int):
        return value
    text = str(value or "")
    if ":" in text:
        text = text.rsplit(":", 1)[1]
    return int(text) if text.isdigit() else None


def _entry_rows(con, db, entry_id):
    """All sense chunks of one entry, ordered, else the single chunk.

    v2.1 lexicon databases set ``chunks.entry_id`` on every sense chunk so the
    whole entry can be read back; older databases have one chunk per entry and
    no such column, so fall back to the id lookup.
    """
    base = ("SELECT c.text, c.locator_json, c.section, d.title, d.canonical_url,"
            " d.source_id"
            " FROM chunks c LEFT JOIN documents d ON d.document_id = c.document_id")
    if "entry_id" in _schema(con, db)["chunk_cols"]:
        rows = con.execute(base + " WHERE c.entry_id = ? ORDER BY c.ordinal",
                           (entry_id,)).fetchall()
        if rows:
            return rows
    return con.execute(base + " WHERE c.id = ?", (entry_id,)).fetchall()


def _page_definition(full, entry_offset=0, entry_limit=None):
    """Slice the joined entry body; report the total so callers can page.

    A λόγος entry is ~24 KB of LSJ text, which is too much for one tool result.
    Paging is a plain character window: the caller gets `definition` plus
    `definition_total` / `next_offset` and fetches the tail with `entry_offset`.
    A window that reaches the end of the text is not "truncated", even when it
    starts in the middle.
    """
    body = full or ""
    total = len(body)
    try:
        start = max(0, int(entry_offset or 0))
    except (TypeError, ValueError):        # FastAPI Query object on direct calls
        start = 0
    if start > total:
        start = total
    if entry_limit is None:
        piece = body[start:]
        truncated = False
    else:
        try:
            limit = max(1, int(entry_limit))
        except (TypeError, ValueError):
            limit = max(1, total)          # direct endpoint calls without FastAPI
        piece = body[start:start + limit]
        truncated = start + len(piece) < total
    return {
        "definition": piece or None,
        "definition_offset": start,
        "definition_total": total,
        "definition_truncated": truncated,
        "next_offset": (start + len(piece)) if (truncated and piece) else None,
    }


def _row_entry(con, db, row, area, entry_offset=0, entry_limit=None):
    """Attach the entry body (a chunk) and the policy citation to one headword."""
    raw_entry = _row_get(row, "entry_id")
    source = _row_get(row, "source_id")
    if not source and isinstance(raw_entry, str) and ":" in str(raw_entry):
        source = str(raw_entry).split(":", 1)[0]
    entry = {
        "headword": row["headword"],
        "lemma": _row_get(row, "lemma"),
        "pos": _row_get(row, "pos", ""),
        "homonym": _row_get(row, "homonym", 0) or 0,
        "entry_id": raw_entry,
        "source": source,
    }
    loc = {"scheme": area, "headword": row["headword"], "pos": entry["pos"]}
    if area == "grammar":
        loc = {"scheme": "grammar",
               "section": str(row["headword"]).lstrip("§"),
               "title": entry["lemma"]}
    doc = {}
    text = None
    chunk_id = _entry_chunk_id(raw_entry)
    if chunk_id is not None and "chunks" in _tables(con, db):
        rows = _entry_rows(con, db, chunk_id)
        if rows:
            text = " ".join(r["text"] for r in rows if r["text"]) or None
            stored = locators.loads(rows[0]["locator_json"])
            if stored:
                loc = stored
            if rows[0]["section"] and area == "grammar":
                loc.setdefault("title", rows[0]["section"])
            doc = {"title": rows[0]["title"], "canonical_url": rows[0]["canonical_url"]}
            source = source or _row_get(rows[0], "source_id")
    entry["source"] = source or _logical_source(area) or AREA_KIND[area]
    entry.update(_page_definition(text, entry_offset, entry_limit))
    entry["locator"] = loc
    entry["citation"] = _cite(entry, doc)
    return entry


def _cite(entry, doc=None):
    tier, estimated = citation_policy.tier_for_source(entry["source"])
    if tier == "unknown":
        # The database names the edition ("lsj"); the policy names the logical
        # source ("dict-lsj"). Resolve the fallback through the policy instead
        # of hardcoding a catalogue name, so any deployment benefits.
        area = "grammar" if entry["locator"].get("scheme") == "grammar" else "dict"
        logical = _logical_source(area)
        if logical:
            tier, estimated = citation_policy.tier_for_source(logical)
    loc = entry["locator"]
    return {
        "scheme": loc.get("scheme"),
        "locator": loc,
        "label": locators.default_label(loc, doc),
        "url": locators.url(loc, doc),
        "tier": tier,
        "tier_estimated": estimated,
        "role": "cite",
        "policy_version": citation_policy.version(),
    }


def _headword_rows(con, db, keys, lang, limit):
    """Headword rows, one indexed equality per column and per key.

    The original `lower(headword) OR lower(lemma)` predicate scans all ~220k
    rows on every call (~30–50 ms on the real lexicon). Equality predicates let
    each column use its own index, and `INDEXED BY` names the index so SQLite
    does not pick its default `lang`-only scan on the lemma index. The
    case-insensitive pass is a real fallback: it runs only when the exact pass
    finds nothing and the expression indexes exist.
    """
    cap = max(1, min(int(limit), 50))
    indexes = _schema(con, db)["indexes"]
    rows = []
    seen = set()

    def fetch(column, value, index=None):
        hint = (" INDEXED BY %s" % index) if index in indexes else ""
        sql = "SELECT * FROM lexicon_headwords%s WHERE %s = ?" % (hint, column)
        params = [value]
        if lang:
            sql += " AND lang = ?"
            params.append(lang)
        sql += " ORDER BY headword LIMIT ?"
        return con.execute(sql, params + [cap]).fetchall()

    def add(new):
        for row in new:
            key = (row["lang"], row["headword"], row["pos"], row["homonym"])
            if key not in seen and len(rows) < cap:
                seen.add(key)
                rows.append(row)

    for key in keys:
        add(fetch("headword", key))
    if len(rows) < cap:
        for key in keys:
            add(fetch("lemma", key, "idx_lex_lemma"))
    if not rows:
        for key in keys:
            add(fetch("lower(headword)", key.lower(), "idx_lex_lower_head"))
        if len(rows) < cap:
            for key in keys:
                add(fetch("lower(lemma)", key.lower(), "idx_lex_lower_lemma"))
    return rows


def lookup(form, lang=None, area="dict", view="student", limit=10, path=None,
           entry_offset=0, entry_limit=None):
    """Headword rows for a surface form, with their entry body when present.

    `area` is "dict" or "grammar"; `form` is the headword for a dictionary and
    the section label ("§212", "212", "smythp=2297") for a grammar.

    `entry_offset` / `entry_limit` page the *entry body* (characters): a long
    LSJ entry (λόγος is ~24 KB) comes back as a window plus `next_offset`, so
    one tool result never has to carry the whole entry.
    """
    area = "grammar" if area == "grammar" else "dict"
    db = path or config.LEXICON_DB
    out = {"query": form, "area": area, "lang": lang, "available": available(db),
           "streams": list(citation_policy.streams_for(AREA_KIND[area])),
           "entries": [], "reason": None}
    if not out["available"]:
        out["reason"] = "no_lexicon"
        return out
    if not str(form or "").strip():
        out["reason"] = "empty_query"
        return out

    db_path, con = _connect(db)
    try:
        if "lexicon_headwords" not in _tables(con, db_path):
            out["reason"] = "no_table"
            return out
        keys = lemmas(form, lang) if area == "dict" else _section_keys(form)
        rows = _headword_rows(con, db_path, keys, lang, limit)
        for row in rows:
            out["entries"].append(
                _row_entry(con, db_path, row, area, entry_offset, entry_limit))
    finally:
        # the connection stays cached (see `reset`); nothing to close per call
        pass
    if not out["entries"]:
        out["reason"] = "not_found"
    return out


def _section_keys(form):
    """Accept "§212" and "212". `smythp=NNNN` is a *different* numbering, so it
    stays an exact key instead of being guessed into a section number."""
    raw = str(form or "").strip()
    if raw.lower().startswith("smythp="):
        bare = raw.split("=", 1)[1].strip()
        return [raw] + ([bare] if bare else [])
    digits = "".join(ch for ch in raw if ch.isdigit())
    keys = [raw]
    if digits:
        for candidate in ("§" + digits, digits):
            if candidate not in keys:
                keys.append(candidate)
    return keys
