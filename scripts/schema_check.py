"""Compare a RAG database against the implemented contract, read from the code.

    python scripts/schema_check.py --db <path> [--explain] [--json]

Read-only. The contract is not hardcoded here — it comes from
`citation_policy.STREAMS` (chunk streams), `locators.SCHEMES` (locator schemes
and their required keys) and `schema.DDL` (expected tables). That way the check
cannot go stale after a schema change.

Reports, per database:

  * detected schema version (v1 / v2 / unknown);
  * v2 table presence (`documents.kind` is the column that arrived in v2.1);
  * every `chunks.stream` value found, flagged when outside the vocabulary;
  * every `locator_json.scheme` found, flagged when `locators.validate` would
    reject it, plus rows whose locator misses a required key.

`--explain` prints the implemented vocabulary the database is being measured
against.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SIDECAR = os.path.join(os.path.dirname(HERE), "sidecar")
if SIDECAR not in sys.path:
    sys.path.insert(0, SIDECAR)

from app import citation_policy, config, locators, schema  # noqa: E402

_DDL_TABLE = re.compile(r"CREATE TABLE IF NOT EXISTS (\w+)", re.I)


def expected_tables():
    out = set()
    for stmt in schema.DDL:
        out.update(m.group(1) for m in _DDL_TABLE.finditer(stmt))
    return sorted(out)


def inspect(path):
    out = {"db": path, "exists": os.path.exists(path)}
    if not out["exists"]:
        out["version"] = "none"
        return out
    out["version"] = schema.version(path)
    con = config.open_db(path)
    con.row_factory = sqlite3.Row
    try:
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        out["tables"] = sorted(tables & set(expected_tables()))
        out["missing_tables"] = sorted(set(expected_tables()) - tables)
        if "documents" in tables:
            cols = {r[1] for r in con.execute("PRAGMA table_info(documents)")}
            out["documents_kind"] = "kind" in cols
        else:
            out["documents_kind"] = None

        out["streams"], out["schemes"], out["invalid_locators"] = {}, {}, {}
        if "chunks" in tables:
            cols = {r[1] for r in con.execute("PRAGMA table_info(chunks)")}
            out["chunks_columns"] = sorted(cols)
            if "stream" in cols:
                out["streams"] = dict(con.execute(
                    "SELECT stream, count(*) FROM chunks GROUP BY stream"))
            if "locator_json" in cols:
                schemes, broken = Counter(), Counter()
                for (raw,) in con.execute("SELECT locator_json FROM chunks"):
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
    finally:
        con.close()
    return out


def gaps(report):
    """Contract violations in this database, measured against the code."""
    out = []
    if report.get("documents_kind") is False:
        out.append("documents.kind: column absent (v2.1 expects it)")
    if report.get("version") == "v2" and report.get("missing_tables"):
        out.append("tables: expected by schema.DDL but absent: %s"
                   % report["missing_tables"])
    unknown = sorted(set(report.get("streams") or {}) - set(citation_policy.STREAMS))
    if unknown:
        out.append("chunks.stream: values outside citation_policy.STREAMS: %s" % unknown)
    bad = sorted(report.get("invalid_locators") or {})
    if bad:
        out.append("locator_json: rejected by locators.validate: %s" % bad)
    return out


def explain():
    print("streams   : %s" % ", ".join(citation_policy.STREAMS))
    print("schemes   : %s" % ", ".join(sorted(locators.SCHEMES)))
    required = {k: sorted(v) for k, v in locators.REQUIRED.items()}
    print("required  : %s" % json.dumps(required, ensure_ascii=False))
    print("catalogues: v1 | v2 | lexicon")
    print("tables    : %s" % ", ".join(expected_tables()))
    kinds = (citation_policy._builtin().get("education") or {}).get("streams") or {}
    print("education : %s" % json.dumps(kinds, ensure_ascii=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True)
    ap.add_argument("--explain", "--proposed", dest="explain", action="store_true",
                    help="also print the implemented vocabulary (--proposed is the old name)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = inspect(args.db)
    report["gaps"] = gaps(report)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1, default=str))
        return 0

    print("db        : %s" % report["db"])
    print("exists    : %s   version: %s" % (report["exists"], report["version"]))
    if not report["exists"]:
        return 1
    print("tables    : %s" % (", ".join(report.get("tables") or []) or "(none)"))
    if report.get("version") == "v2" and report.get("missing_tables"):
        print("missing   : %s" % ", ".join(report["missing_tables"]))
    if report.get("documents_kind") is not None:
        print("documents.kind: %s" % ("present" if report["documents_kind"] else "ABSENT"))
    print("streams   : %s" % json.dumps(report.get("streams") or {}, ensure_ascii=False))
    print("schemes   : %s" % json.dumps(report.get("schemes") or {}, ensure_ascii=False))
    if report.get("invalid_locators"):
        print("invalid   : %s" % json.dumps(report["invalid_locators"], ensure_ascii=False))
    print("gaps      : %d" % len(report["gaps"]))
    for line in report["gaps"]:
        print("  - %s" % line)
    if args.explain:
        print("\n-- implemented contract --")
        explain()
    return 0 if not report["gaps"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
