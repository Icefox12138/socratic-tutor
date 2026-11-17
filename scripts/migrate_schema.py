"""Idempotent schema migration for rag-build data artifacts.

    python scripts/migrate_schema.py --db D:/Guo-Code/rag-build/data/indexes/search.db

What it does
  v1  -> ALTER chunks ADD COLUMN stream TEXT NOT NULL DEFAULT 'text'
  v2  -> ensure_v2() (adds documents.kind on older v2 files)
  other -> refuses

A timestamped backup is written next to the database before any change.
Safe to run repeatedly: existing columns are left alone.
"""
import argparse
import os
import shutil
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "sidecar"))

from app import schema  # noqa: E402


def columns(con, table):
    try:
        return {r[1] for r in con.execute("PRAGMA table_info(%s)" % table)}
    except sqlite3.Error:
        return set()


def report(path):
    con = sqlite3.connect(path)
    try:
        out = {"chunks": sorted(columns(con, "chunks"))}
        if "documents" in {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}:
            out["documents"] = sorted(columns(con, "documents"))
        out["version"] = schema.version(path)
        return out
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = os.path.abspath(args.db)
    if not os.path.exists(path):
        print("ERROR: no such database:", path)
        return 2

    before = report(path)
    ver = before["version"]
    print("db      :", path)
    print("version :", ver)
    print("chunks  :", ", ".join(before["chunks"]))
    if "documents" in before:
        print("docs    :", ", ".join(before["documents"]))

    planned = []
    if ver == "v2" and "kind" not in before.get("documents", set()):
        planned.append("ALTER documents ADD COLUMN kind TEXT")
    if ver == "v1" and "stream" not in before["chunks"]:
        planned.append("ALTER chunks ADD COLUMN stream TEXT NOT NULL DEFAULT 'text'")
    if not planned:
        print("no change needed")
        return 0
    for p in planned:
        print("plan    :", p)
    if args.dry_run:
        print("dry-run: nothing written")
        return 0

    backup = "%s.bak-%s" % (path, time.strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(path, backup)
    print("backup  :", backup)

    if ver == "v2":
        schema.ensure_v2(path)
    elif ver == "v1":
        schema.migrate_v1_stream(path)
    else:
        print("ERROR: unsupported version %r (refusing to touch it)" % ver)
        return 1

    after = report(path)
    ok = True
    if ver == "v2":
        ok = "kind" in after.get("documents", set())
    else:
        ok = "stream" in after["chunks"]
    print("after   :", ", ".join(after["chunks"]))
    if "documents" in after:
        print("after   :", ", ".join(after["documents"]))
    print("result  :", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
