"""Read-only views over a v2 catalogue: sources, documents, one chunk.

These are the endpoints a client uses to discover what is indexed without
searching. They never render page images; a public document has a URL instead.
"""
import json

from . import citation_policy, config, locators, schema


def _rows(sql, params=()):
    con = schema.connect()
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def _one(sql, params=()):
    rows = _rows(sql, params)
    return rows[0] if rows else None


def source_list():
    out = _rows("SELECT * FROM sources ORDER BY source_id")
    for row in out:
        try:
            row["config"] = json.loads(row.pop("config_json") or "{}")
        except ValueError:
            row["config"] = {}
    return out


def document_list(source=None, lang=None, limit=100, offset=0):
    sql = ("SELECT d.document_id, d.source_id, d.title, d.author, d.edition,"
           " d.lang, d.license, d.canonical_url,"
           " (SELECT count(*) FROM chunks c WHERE c.document_id = d.document_id) AS chunks "
           "FROM documents d WHERE 1=1")
    params = []
    if source:
        sql += " AND d.source_id = ?"
        params.append(source)
    if lang:
        sql += " AND d.lang = ?"
        params.append(lang)
    sql += " ORDER BY d.title LIMIT ? OFFSET ?"
    params.extend([max(1, min(int(limit), 500)), max(0, int(offset))])
    return _rows(sql, params)


def document(document_id):
    doc = _one("SELECT * FROM documents WHERE document_id = ?", (document_id,))
    if not doc:
        return None
    try:
        doc["metadata"] = json.loads(doc.pop("metadata_json") or "{}")
    except ValueError:
        doc["metadata"] = {}
    sections = _rows(
        "SELECT section, min(ordinal) AS ord, count(*) AS chunks"
        " FROM chunks WHERE document_id = ? GROUP BY section ORDER BY ord",
        (document_id,))
    first = _one("SELECT locator_json FROM chunks WHERE document_id = ?"
                 " ORDER BY ordinal LIMIT 1", (document_id,))
    doc["sections"] = sections
    doc["chunks"] = sum(s["chunks"] for s in sections)
    doc["scheme"] = locators.scheme(first["locator_json"]) if first else None
    return doc


CHUNK_COLUMNS = (
    "SELECT c.id, c.document_id, c.ordinal, c.section, c.text, c.lang,"
    " c.stream, c.locator_json, c.citation_label, c.quality,"
    " c.char_start, c.char_end, d.title, d.author, d.license,"
    " d.canonical_url, d.source_id FROM chunks c"
    " JOIN documents d ON d.document_id = c.document_id ")


def chunk(chunk_id, view="student"):
    row = _one(CHUNK_COLUMNS + "WHERE c.id = ?", (chunk_id,))
    if not row:
        return None
    if view == "student" and row["stream"] not in (config.STUDENT_STREAMS or ("text",)):
        return None
    return result_for_row(row, 1.0)


def result_for_row(row, score=1.0):
    """Shape one v2 row exactly like a search hit."""
    loc = locators.loads(row["locator_json"])
    doc = {"title": row["title"], "author": row["author"],
           "license": row["license"], "canonical_url": row["canonical_url"],
           "lang": row["lang"]}
    label = row["citation_label"] or locators.default_label(loc, doc)
    href = locators.url(loc, doc)
    score = round(float(score), 4)
    return {
        "chunk_id": row["id"],
        "document_id": row["document_id"],
        "source": row["source_id"],
        "book": row["title"],
        "lang": row["lang"],
        "page": None,
        "section": row["section"],
        "stream": row["stream"],
        "positions": {"char_start": row["char_start"], "char_end": row["char_end"]},
        "bbox": None,
        "similarity": score,
        "text": row["text"],
        "score": score,
        "citation": {
            "scheme": loc.get("scheme"),
            "locator": label,
            "label": label,
            "url": href,
            "image": None,
            "page_image": None,
            "tier": "A",
            "role": "cite",
            "policy_version": citation_policy.version(),
            "license": row["license"],
            "document_id": row["document_id"],
            "revision": loc.get("revision"),
        },
    }
