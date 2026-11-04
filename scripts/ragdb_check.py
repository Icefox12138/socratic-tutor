#!/usr/bin/env python
"""Check the RAG database a sidecar would read, without starting the sidecar.

  python scripts/ragdb_check.py            # human readable
  python scripts/ragdb_check.py --json

Exit 0 when the configured data is usable. Answers "which files am I actually
reading?" — the question that matters after moving data somewhere else.
"""
import argparse
import json
import os
import sqlite3
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "sidecar"))

from app import config  # noqa: E402


def size_mb(path):
    try:
        return round(os.path.getsize(path) / (1024 * 1024), 1)
    except OSError:
        return None


def db_stats(path):
    """chunks / tutor / answer_key / fts rows, or the error that stopped us."""
    if not os.path.exists(path):
        return {"ok": False, "error": "missing"}
    try:
        con = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True, timeout=5)
        try:
            chunks = con.execute("SELECT count(*) FROM chunks").fetchone()[0]
            tutor = con.execute("SELECT count(*) FROM chunks WHERE visibility='tutor'").fetchone()[0]
            secret = con.execute("SELECT count(*) FROM chunks WHERE visibility='answer_key'").fetchone()[0]
            try:
                fts = con.execute("SELECT count(*) FROM chunks_fts").fetchone()[0]
            except sqlite3.Error:
                fts = None
            return {"ok": True, "chunks": chunks, "tutor": tutor,
                    "answer_key": secret, "fts": fts}
        finally:
            con.close()
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def vector_stats(vectors, ids):
    if not os.path.exists(vectors):
        return {"ok": False, "error": "missing"}
    try:
        import numpy as np
    except ImportError:
        return {"ok": False, "error": "numpy not installed"}
    try:
        v = np.load(vectors, mmap_mode="r")
        shape = list(v.shape)
        dtype = str(v.dtype)
        n_ids = None
        if os.path.exists(ids):
            i = np.load(ids, mmap_mode="r")
            n_ids = int(i.shape[0]) if i.ndim else 1
        aligned = (n_ids == shape[0]) if (n_ids is not None and len(shape) == 2) else None
        return {"ok": True, "rows": shape[0] if len(shape) == 2 else None,
                "dim": shape[1] if len(shape) == 2 else None,
                "dtype": dtype, "ids": n_ids, "aligned": aligned}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def toc_stats(path):
    if not os.path.exists(path):
        return {"ok": False, "error": "missing"}
    try:
        con = sqlite3.connect("file:%s?mode=ro" % path.replace("\\", "/"), uri=True, timeout=5)
        try:
            n = con.execute("SELECT count(*) FROM toc").fetchone()[0]
            books = con.execute("SELECT count(DISTINCT source || ':' || book) FROM toc").fetchone()[0]
            return {"ok": True, "chapters": n, "books": books}
        finally:
            con.close()
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    db = db_stats(config.DB)
    vec = vector_stats(config.BGE_VECTORS, config.BGE_IDS)
    toc = toc_stats(config.toc_db())

    problems = []
    if not db.get("ok"):
        problems.append("database: %s" % db.get("error"))
    elif not db.get("chunks"):
        problems.append("database has no chunks")
    elif db.get("fts") is not None and db["fts"] != db["chunks"]:
        problems.append("chunks_fts rows (%s) != chunks rows (%s)" % (db["fts"], db["chunks"]))
    if config.BGE and not vec.get("ok"):
        problems.append("vectors: %s" % vec.get("error"))
    if vec.get("ok") and vec.get("aligned") is False:
        problems.append("bge-ids rows (%s) != vector rows (%s)" % (vec.get("ids"), vec.get("rows")))
    if not toc.get("ok") and config.TOC_IN == "search":
        problems.append("toc (from search db): %s" % toc.get("error"))

    report = {
        "ok": not problems,
        "data": config.DATA,
        "database": {"path": config.DB, "size_mb": size_mb(config.DB), **db},
        "vectors": {"path": config.BGE_VECTORS, "size_mb": size_mb(config.BGE_VECTORS), **vec},
        "ids": {"path": config.BGE_IDS, "size_mb": size_mb(config.BGE_IDS)},
        "toc": {"path": config.toc_db(), "source": config.TOC_IN, **toc},
        "bge_enabled": config.BGE,
        "library": config.LIBRARY,
        "problems": problems,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print("data root : %s" % report["data"])
        print("library   : %s" % report["library"])
        print("database  : %s  %s MB  %s" % (
            report["database"]["path"], report["database"]["size_mb"],
            ("chunks=%s tutor=%s answer_key=%s fts=%s" % (
                db.get("chunks"), db.get("tutor"), db.get("answer_key"), db.get("fts")))
            if db.get("ok") else "ERROR: " + str(db.get("error"))))
        print("vectors   : %s  %s MB  %s" % (
            report["vectors"]["path"], report["vectors"]["size_mb"],
            ("%sx%s %s ids=%s aligned=%s" % (vec.get("rows"), vec.get("dim"),
                                             vec.get("dtype"), vec.get("ids"), vec.get("aligned")))
            if vec.get("ok") else "ERROR: " + str(vec.get("error"))))
        print("ids       : %s  %s MB" % (report["ids"]["path"], report["ids"]["size_mb"]))
        print("toc       : %s  (%s)  %s" % (
            report["toc"]["path"], report["toc"]["source"],
            ("%s chapters / %s books" % (toc.get("chapters"), toc.get("books")))
            if toc.get("ok") else "ERROR: " + str(toc.get("error"))))
        print("bge       : %s" % ("enabled" if config.BGE else "disabled"))
        print()
        if problems:
            for p in problems:
                print("PROBLEM: %s" % p)
            print("RAG DB NOT USABLE")
        else:
            print("RAG DB OK")

    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
