"""Turn an adapter :class:`Document` into schema-v2 rows.

Ingestion is deliberately separate from fetching: a failed HTTP call never
leaves half a document behind, and re-ingesting a document replaces its chunks
atomically inside one transaction.
"""
import json

from . import locators, schema, textutil
from .adapters.base import Document, SourceSpec


def ensure_source(con, spec: SourceSpec):
    con.execute(
        "INSERT INTO sources(source_id, adapter, base_url, auth_env,"
        " rate_limit, license, redistribution, enabled, config_json)"
        " VALUES(?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(source_id) DO UPDATE SET adapter=excluded.adapter,"
        " base_url=excluded.base_url, auth_env=excluded.auth_env,"
        " rate_limit=excluded.rate_limit, license=excluded.license,"
        " redistribution=excluded.redistribution, enabled=excluded.enabled,"
        " config_json=excluded.config_json",
        (spec.source_id, spec.adapter, spec.base_url, spec.auth_env,
         spec.rate_limit, spec.license, spec.redistribution, 1,
         json.dumps(spec.config, ensure_ascii=False)))


def document_dict(doc: Document) -> dict:
    return {
        "document_id": doc.document_id, "source_id": doc.source_id,
        "title": doc.title, "author": doc.author, "edition": doc.edition,
        "lang": doc.lang, "script": doc.script, "license": doc.license,
        "provenance": doc.provenance, "canonical_url": doc.canonical_url,
    }


def ingest_document(con, doc: Document, spec: SourceSpec | None = None,
                    max_chars: int = 1200):
    """Replace one document and its chunks. Returns insertion statistics."""
    if not doc.sections:
        raise ValueError("document %r has no sections" % doc.document_id)
    if spec is not None:
        ensure_source(con, spec)

    meta = document_dict(doc)
    con.execute(
        "INSERT INTO documents(document_id, source_id, title, author,"
        " edition, lang, script, license, provenance, canonical_url, metadata_json)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(document_id) DO UPDATE SET source_id=excluded.source_id,"
        " title=excluded.title, author=excluded.author, edition=excluded.edition,"
        " lang=excluded.lang, script=excluded.script, license=excluded.license,"
        " provenance=excluded.provenance, canonical_url=excluded.canonical_url,"
        " metadata_json=excluded.metadata_json",
        (doc.document_id, doc.source_id, doc.title, doc.author, doc.edition,
         doc.lang, doc.script, doc.license, doc.provenance, doc.canonical_url,
         json.dumps(doc.metadata, ensure_ascii=False)))

    old = [r[0] for r in con.execute(
        "SELECT id FROM chunks WHERE document_id = ?", (doc.document_id,))]
    if old:
        con.executemany("DELETE FROM chunks_fts WHERE rowid = ?", [(i,) for i in old])
        con.executemany("DELETE FROM chunks WHERE id = ?", [(i,) for i in old])

    ordinal = 0
    for section in doc.sections:
        locators.validate(section.locator)
        for piece, start, end in textutil.chunk_paragraphs(section.text, max_chars):
            loc = dict(section.locator)
            loc["char_start"] = start
            loc["char_end"] = end
            label = locators.default_label(loc, meta)
            cur = con.execute(
                "INSERT INTO chunks(document_id, ordinal, section, text, lang,"
                " stream, visibility, locator_json, citation_label, quality,"
                " char_start, char_end, source_version)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (doc.document_id, ordinal, section.title, piece, doc.lang,
                 "text", "tutor", locators.dumps(loc), label,
                 section.quality or "public-text", start, end,
                 doc.source_version))
            con.execute("INSERT INTO chunks_fts(rowid, text) VALUES(?, ?)",
                        (cur.lastrowid, " ".join(textutil.tokens_v2(piece))))
            ordinal += 1
    con.commit()
    return {"document_id": doc.document_id, "sections": len(doc.sections),
            "chunks": ordinal, "revision": doc.source_version}


def ingest(db_path, doc: Document, spec: SourceSpec | None = None,
           max_chars: int = 1200):
    """Ensure the v2 schema, ingest one document, close the connection."""
    schema.ensure_v2(db_path)
    con = schema.connect(db_path)
    try:
        return ingest_document(con, doc, spec=spec, max_chars=max_chars)
    finally:
        con.close()
