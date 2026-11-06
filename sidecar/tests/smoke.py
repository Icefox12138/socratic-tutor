import json
import os
import sqlite3
import sys

import requests

BASE = "http://127.0.0.1:8765"
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROOT = os.path.dirname(REPO)
MANIFEST = os.environ.get(
    "SOCRATIC_MANIFEST",
    os.path.join(REPO, "eval", "p0", "catalog", "sample-manifest.json"))
DB = os.environ.get("SOCRATIC_DB",
                    os.path.join(REPO, "samples", "search.db"))


def main():
    c1 = next(s for s in json.load(open(MANIFEST, encoding="utf-8"))["samples"] if s["id"] == "C1")
    book = os.path.relpath(c1["path"], os.path.join(ROOT, "PDF"))
    con = sqlite3.connect(DB)
    canary_id = con.execute("SELECT id FROM chunks WHERE text LIKE '%CANARY-7F3A%'").fetchone()[0]
    con.close()

    out = {}
    r = requests.get(BASE + "/health", timeout=10)
    out["health"] = {"status": r.status_code, "body": r.json()}

    r = requests.get(BASE + "/v1/search", params={"q": "微分", "view": "student", "limit": 3}, timeout=120)
    d = r.json()
    out["search"] = {"status": r.status_code, "mode": d.get("mode"), "n": len(d.get("results", [])),
                     "first": d.get("results", [{}])[0].get("citation") if d.get("results") else None}

    for view in ("student", "tutor"):
        r = requests.get(BASE + "/v1/search", params={"q": "CANARY-7F3A", "view": view}, timeout=120)
        d = r.json()
        ids = [x.get("chunk_id") for x in d.get("results", [])]
        out["canary_" + view] = {"status": r.status_code, "n": len(ids),
                                 "answer_key_hit": canary_id in ids}

    r = requests.get(BASE + "/v1/pages", params={"source": "library", "book": book, "page": 76, "dpi": 120}, timeout=30)
    out["page"] = {"status": r.status_code, "bytes": len(r.content),
                   "png": r.content[:8] == b"\x89PNG\r\n\x1a\n"}

    r = requests.post(BASE + "/v1/compute", json={"expression": "x^2", "operation": "diff"}, timeout=20)
    out["compute_diff"] = {"status": r.status_code, "body": r.json()}

    r = requests.post(BASE + "/v1/compute", json={"expression": "__import__('os')", "operation": "simplify"}, timeout=20)
    out["compute_forbidden"] = {"status": r.status_code, "body": r.json()}

    ok = (
        out["health"]["status"] == 200
        and out["search"]["n"] > 0
        and out["canary_student"]["answer_key_hit"] is False
        and out["canary_tutor"]["answer_key_hit"] is False
        and out["page"]["png"]
        and out["compute_diff"]["body"].get("result") == "2*x"
        and out["compute_forbidden"]["status"] == 400
    )
    out["ok"] = ok
    with open(os.path.join(os.path.dirname(__file__), "smoke.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
