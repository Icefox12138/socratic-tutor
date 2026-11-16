"""Compare a RAG database against the implemented contract, and against the
additions the data project has proposed.

    python scripts/schema_check.py --db <path> [--proposed] [--json]

Read-only. Reports, per database:

  * detected schema version (v1 / v2 / unknown);
  * v2 table and column presence (`documents.kind` is the known gap);
  * every `chunks.stream` value found, flagged when outside the implemented
    allowlist (`text|translation|commentary|apparatus`, plus whatever
    SOCRATIC_STUDENT_STREAMS opts in for reading);
  * every `locator_json.scheme` found, flagged when `locators.validate` would
    reject it, plus rows whose locator misses a required key.

With `--proposed` it also lists the additions proposed by the data project
(`rag-build/docs/CORPUS-PROFILES.md` §6.2) that this database cannot use yet.

The point is to make the delta mechanical: "does the writer's vocabulary fit the
reader's gates" instead of comparing prose in two repositories.
"""
import argparse
import json
import os
import sqlite3
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SIDECAR = os.path.join(os.path.dirname(HERE), "sidecar")
if SIDECAR not in sys.path:
    sys.path.insert(0, SIDECAR)

from app import config, locators, schema  # noqa: E402

# What the schema DDL documents as the stream vocabulary today.
IMPLEMENTED_STREAMS = ("text", "translation", "commentary", "apparatus")

# Proposed by rag-build/docs/CORPUS-PROFILES.md §6.2 (dictionary + grammar +
# textbook blocks). None of these is in the implemented allowlist yet.
PROPOSED = {
    "documents.kind": ["dictionary", "grammar"],
    "chunks.stream": ["definition", "paradigm", "example", "formula", "table", "code"],
    "locator scheme": ["dict", "grammar"],
    "tables": ["lexicon_headwords"],
}


def _rows(con, sql, params=()):
    return con.execute(sql, params).fetchall()


def inspect(path):
    out = {"db": path, "exists": os.path.exists(path)}
    if not out["exists"]:
        out["version"] = "none"
        return out
    out["version"] = schema.version(path)
    con = config.open_db(path)
    con.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in _rows(
            con, "SELECT name FROM sqlite_master WHERE type='table'")}
        out["tables"] = sorted(tables & {"chunks", "documents", "sources", "assets",
                                         "embeddings", "schema_meta", "chunks_fts"})
        out["missing_tables"] = sorted({"documents", "sources", "chunks"} - tables)
        if "documents" in tables:
            cols = {r[1] for r in _rows(con, "PRAGMA table_info(documents)")}
            out["documents_kind"] = "kind" in cols
        else:
            out["documents_kind"] = None

        if "chunks" in tables:
            cols = {r[1] for r in _rows(con, "PRAGMA table_info(chunks)")}
            out["chunks_columns"] = sorted(cols)
            if "stream" in cols:
                out["streams"] = dict(_rows(
                    con, "SELECT stream, count(*) FROM chunks GROUP BY stream"))
            else:
                out["streams"] = {}
            if "locator_json" in cols:
                schemes = Counter()
                broken = Counter()
                for (raw,) in _rows(con, "SELECT locator_json FROM chunks"):
                    loc = locators.loads(raw)
                    sch = str(loc.get("scheme") or "missing")
                    schemes[sch] += 1
                    if sch not in locators.SCHEMES:
                        broken[sch] += 1
                        continue
                    missing = [k for k in locators.REQUIRED[sch]
                               if loc.get(k) in (None, "")]
                    if missing:
                        broken["%s:missing %s" % (sch, ",".join(missing))] += 1
                out["schemes"] = dict(schemes)
                out["invalid_locators"] = dict(broken)
            else:
                out["schemes"] = {}
                out["invalid_locators"] = {}
        else:
            out["streams"] = {}
            out["schemes"] = {}
            out["invalid_locators"] = {}
    finally:
        con.close()
    return out


def gaps(report):
    """Implemented-vs-proposed deltas that this database cannot use yet."""
    out = []
    if report.get("documents_kind") is False:
        out.append("documents.kind: column absent -> proposed values %s unusable"
                   % PROPOSED["documents.kind"])
    allow = set(IMPLEMENTED_STREAMS) | set(report.get("_read_streams") or [])
    extra = sorted(set(report.get("streams") or {}) - allow)
    if extra:
        out.append("chunks.stream: values present but outside the implemented "
                   "allowlist: %s" % extra)
    unseen = sorted(set(PROPOSED["chunks.stream"]) - allow)
    if unseen:
        out.append("chunks.stream: proposed but not implemented: %s" % unseen)
    bad = sorted(k for k in (report.get("invalid_locators") or {}))
    if bad:
        out.append("locator_json: rejected by locators.validate: %s" % bad)
    unseen_schemes = sorted(set(PROPOSED["locator scheme"]) - set(locators.SCHEMES))
    if unseen_schemes:
        out.append("locator scheme: proposed but not implemented: %s" % unseen_schemes)
    missing_tables = sorted(set(PROPOSED["tables"]) - set(report.get("tables") or []))
    if report.get("version") == "v2" and missing_tables:
        out.append("tables: proposed but absent: %s" % missing_tables)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True)
    ap.add_argument("--proposed", action="store_true",
                    help="also list the data project's proposed additions")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = inspect(args.db)
    report["_read_streams"] = list(config.STUDENT_STREAMS or ("text",))
    report["gaps"] = gaps(report)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
        return 0

    print("db        : %s" % report["db"])
    print("exists    : %s   version: %s" % (report["exists"], report["version"]))
    if not report["exists"]:
        return 1
    print("tables    : %s" % ", ".join(report.get("tables") or []) or "(none)")
    if report.get("missing_tables"):
        print("missing   : %s" % ", ".join(report["missing_tables"]))
    if report.get("documents_kind") is not None:
        print("documents.kind: %s" % ("present" if report["documents_kind"] else "ABSENT"))
    print("streams   : %s" % json.dumps(report.get("streams") or {}, ensure_ascii=False))
    print("read allow: %s" % ", ".join(report["_read_streams"]))
    print("schemes   : %s" % json.dumps(report.get("schemes") or {}, ensure_ascii=False))
    if report.get("invalid_locators"):
        print("invalid   : %s" % json.dumps(report["invalid_locators"], ensure_ascii=False))
    print("gaps      : %d" % len(report["gaps"]))
    if args.proposed:
        for line in report["gaps"]:
            print("  - %s" % line)
    return 0 if not report["gaps"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
