#!/usr/bin/env python
"""Probe any URL against the Socratic sidecar contract.

  python scripts/contract_check.py                        # localhost defaults
  python scripts/contract_check.py --base http://host:8765 --token abc
  python scripts/contract_check.py --expect-auth --json

Exit code 0 means "this service can be used by the plugin/MCP server".
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

REQUIRED_PATHS = ("/v1/search", "/v1/chunks/{chunk_id}", "/v1/pages",
                  "/v1/chapter", "/v1/compute", "/v1/state/init",
                  "/v1/critic", "/v1/citations/{session_id}", "/v1/review")


def request(base, path, token="", method="GET", payload=None, raw=False, timeout=30):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base.rstrip("/") + path, data=data, headers=headers,
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            if raw:
                return r.status, body
            try:
                return r.status, json.loads(body or b"{}")
            except Exception:
                return r.status, {"raw": body[:200].decode("utf-8", "replace")}
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body or b"{}")
        except Exception:
            return e.code, {"raw": body[:200].decode("utf-8", "replace")}
    except Exception as e:
        return 0, {"error": str(e)[:200]}


class Report:
    def __init__(self):
        self.rows = []

    def add(self, check, ok, detail=""):
        self.rows.append({"check": check, "ok": bool(ok), "detail": detail})
        mark = "ok  " if ok else "FAIL"
        print("%s %-28s %s" % (mark, check, detail))

    @property
    def ok(self):
        return all(r["ok"] for r in self.rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8765")
    ap.add_argument("--token", default="")
    ap.add_argument("--expect-auth", action="store_true",
                    help="also assert that a request without the token is rejected")
    ap.add_argument("--query", default="the", help="probe query (use a word your corpus has)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = Report()

    status, doc = request(args.base, "/openapi.json")
    rep.add("openapi", status == 200 and "paths" in doc,
            "HTTP %s, %d paths" % (status, len(doc.get("paths", {})) if isinstance(doc, dict) else 0))
    if isinstance(doc, dict) and "paths" in doc:
        missing = [p for p in REQUIRED_PATHS if p not in doc["paths"]]
        rep.add("required endpoints", not missing, ", ".join(missing) or "all present")

    status, health = request(args.base, "/health", args.token)
    rep.add("health", status == 200 and health.get("ok") is True,
            "HTTP %s chunks=%s" % (status, health.get("chunks")))

    status, search = request(args.base, "/v1/search?" + urllib.parse.urlencode(
        {"q": args.query, "limit": 3}), args.token)
    mode = search.get("mode") if isinstance(search, dict) else None
    rep.add("search", status == 200 and mode in ("fts", "bge+rerank", "page_only"),
            "HTTP %s mode=%s" % (status, mode))
    results = search.get("results") or []
    if results:
        first = results[0]
        fields = ("chunk_id", "document_id", "page", "citation", "score", "similarity")
        missing = [f for f in fields if f not in first]
        rep.add("result shape", not missing, ", ".join(missing) or "ok")
        image = (first.get("citation") or {}).get("page_image")
        if image:
            st, body = request(args.base, image, args.token, raw=True)
            rep.add("page image", st == 200 and len(body) > 1000,
                    "HTTP %s %d bytes" % (st, len(body)))
    else:
        rep.add("result shape", mode == "page_only", "no results (empty corpus?)")

    status, books = request(args.base, "/v1/books", args.token)
    rep.add("books", status == 200 and isinstance(books.get("books"), list),
            "HTTP %s %d books" % (status, len(books.get("books") or [])))
    if books.get("books"):
        b = books["books"][0]
        q = urllib.parse.urlencode({"source": b["source"], "book": b["book"]})
        st, toc = request(args.base, "/v1/toc?" + q, args.token)
        rep.add("toc", st == 200 and bool(toc.get("chapters")),
                "HTTP %s %d chapters" % (st, len(toc.get("chapters") or [])))
        st, ch = request(args.base, "/v1/chapter?" + q, args.token)
        rep.add("chapter", st == 200 and "chapter" in ch,
                "HTTP %s %s" % (st, (ch.get("chapter") or {}).get("title")))

    if args.expect_auth:
        st, _ = request(args.base, "/v1/books", "")
        rep.add("auth enforced", st == 401, "HTTP %s without token" % st)

    if args.json:
        print(json.dumps({"ok": rep.ok, "base": args.base, "rows": rep.rows},
                         ensure_ascii=False, indent=1))
    print("CONTRACT OK" if rep.ok else "CONTRACT FAILED")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
