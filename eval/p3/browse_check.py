"""End-to-end: chapter index + page browser against a live sidecar."""
import json
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8765"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return r.status, r.headers.get("content-type"), r.read()


def main():
    st, _, body = get("/v1/books")
    books = json.loads(body)["books"]
    print("books:", [(b["book"][:28], b["chapters"]) for b in books])
    if not books:
        return 1
    b = books[0]
    q = urllib.parse.urlencode({"source": b["source"], "book": b["book"]})
    st, _, body = get("/v1/toc?" + q)
    toc = json.loads(body)
    print("toc pages=%s chapters=%d" % (toc["pages"], len(toc["chapters"])))
    covered = 0
    for c in toc["chapters"]:
        # level-2 rows nest inside their 卷, so only level 1 contributes coverage
        if (c.get("level") or 1) == 1:
            covered += c["pages"]
        print("  %s%-18s p%d-%d" % ("  " if (c.get("level") or 1) == 2 else "",
                                    c["title"], c["page_start"], c["page_end"]))
    print("coverage:", covered, "of", toc["pages"])
    st, ctype, html = get("/browse")
    print("browse:", st, ctype, len(html), "bytes")
    # render the first real volume start
    first = [c for c in toc["chapters"] if c["volume"]][0]
    st, ctype, png = get("/v1/pages?" + urllib.parse.urlencode(
        {"source": b["source"], "book": b["book"], "page": first["page_start"], "dpi": 150}))
    print("page %d: %s %s %d bytes" % (first["page_start"], st, ctype, len(png)))
    pian = [c for c in toc["chapters"] if (c.get("level") or 1) == 2]
    print("level-2 rows:", len(pian))
    ok = (toc["pages"] == covered and len(pian) >= 7 and st == 200
          and ctype.startswith("image/"))
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
