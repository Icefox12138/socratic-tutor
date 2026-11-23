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

from . import citation_policy, config, lexical, locators

#: logical sources by lexicon area, so tier/role/label stay policy-driven
AREA_SOURCE = {"dict": "dict-lsj", "grammar": "grammar-smyth"}
AREA_KIND = {"dict": "dictionary", "grammar": "grammar"}


def available(path=None):
    return os.path.exists(path or config.LEXICON_DB)


def _connect(path=None):
    con = sqlite3.connect(path or config.LEXICON_DB)
    con.row_factory = sqlite3.Row
    return con


def _tables(con):
    return {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}


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


def _entry_rows(con, entry_id):
    """All sense chunks of one entry, ordered, else the single chunk.

    v2.1 lexicon databases set ``chunks.entry_id`` on every sense chunk so the
    whole entry can be read back; older databases have one chunk per entry and
    no such column, so fall back to the id lookup.
    """
    base = ("SELECT c.text, c.locator_json, c.section, d.title, d.canonical_url"
            " FROM chunks c LEFT JOIN documents d ON d.document_id = c.document_id")
    cols = {r[1] for r in con.execute("PRAGMA table_info(chunks)")}
    if "entry_id" in cols:
        rows = con.execute(base + " WHERE c.entry_id = ? ORDER BY c.ordinal",
                           (entry_id,)).fetchall()
        if rows:
            return rows
    return con.execute(base + " WHERE c.id = ?", (entry_id,)).fetchall()


def _row_entry(con, row, area):
    """Attach the entry body (a chunk) and the policy citation to one headword."""
    raw_entry = _row_get(row, "entry_id")
    source = (_row_get(row, "source_id")
              or (str(raw_entry).split(":", 1)[0] if isinstance(raw_entry, str)
                  and ":" in str(raw_entry) else None)
              or AREA_SOURCE[area])
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
        loc = {"scheme": "grammar", "section": row["headword"], "title": entry["lemma"]}
    doc = {}
    text = None
    chunk_id = _entry_chunk_id(raw_entry)
    if chunk_id is not None and "chunks" in _tables(con):
        rows = _entry_rows(con, chunk_id)
        if rows:
            text = " ".join(r["text"] for r in rows if r["text"]) or None
            stored = locators.loads(rows[0]["locator_json"])
            if stored:
                loc = stored
            if rows[0]["section"] and area == "grammar":
                loc.setdefault("title", rows[0]["section"])
            doc = {"title": rows[0]["title"], "canonical_url": rows[0]["canonical_url"]}
    entry["definition"] = text
    entry["locator"] = loc
    entry["citation"] = _cite(entry, doc)
    return entry


def _cite(entry, doc=None):
    tier, estimated = citation_policy.tier_for_source(entry["source"])
    if tier == "unknown":
        # The database names the edition (lsj), the policy names the logical
        # source (dict-lsj). Fall back so a real DB still gets its tier.
        tier, estimated = citation_policy.tier_for_source(
            AREA_SOURCE["grammar" if entry["locator"].get("scheme") == "grammar"
                        else "dict"])
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


def lookup(form, lang=None, area="dict", view="student", limit=10, path=None):
    """Headword rows for a surface form, with their entry body when present.

    `area` is "dict" or "grammar"; `form` is the headword for a dictionary and
    the section label ("§212", "212", "smythp=2297") for a grammar.
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

    con = _connect(db)
    try:
        if "lexicon_headwords" not in _tables(con):
            out["reason"] = "no_table"
            return out
        keys = lemmas(form, lang) if area == "dict" else _section_keys(form)
        marks = ",".join("?" * len(keys))
        sql = ("SELECT * FROM lexicon_headwords WHERE lower(headword) IN (%s)"
               " OR lower(lemma) IN (%s)" % (marks, marks))
        params = [k.lower() for k in keys] * 2
        if lang:
            sql += " AND lang = ?"
            params.append(lang)
        sql += " ORDER BY headword LIMIT ?"
        params.append(max(1, min(int(limit), 50)))
        rows = con.execute(sql, params).fetchall()
        for row in rows:
            out["entries"].append(_row_entry(con, row, area))
    finally:
        con.close()
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
