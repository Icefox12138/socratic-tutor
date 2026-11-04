"""End-to-end: chapter-scoped retrieval against a live sidecar."""
import json
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8765"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read())


def main():
    books = get("/v1/books")["books"]
    if not books:
        print("no indexed book")
        return 1
    b = books[0]
    q = urllib.parse.urlencode({"source": b["source"], "book": b["book"]})
    print("book:", b["book"][-28:], "chapters:", b["chapters"])

    ch = get("/v1/chapter?" + q + "&q=" + urllib.parse.quote("卷3"))
    c = ch["chapter"]
    print("chapter:", c["title"], "p%d-%d" % (c["page_start"], c["page_end"]),
          "pages:", len(ch["pages"]), "next:", (ch["next"] or {}).get("title"))
    assert c["title"].startswith("卷3"), c["title"]
    assert len(ch["pages"]) == c["page_end"] - c["page_start"] + 1

    at = get("/v1/chapter?" + q + "&page=50")["chapter"]
    print("page 50 ->", at["title"])
    assert at["page_start"] <= 50 <= at["page_end"]

    s = get("/v1/search?" + q + "&q=" + urllib.parse.quote("测试")
            + "&chapter=" + urllib.parse.quote("卷3") + "&session_id=p3-chapter")
    cites = get("/v1/citations/p3-chapter")["citations"]
    page_cites = [c for c in cites if c["lang"] == "page"]
    print("citations:", len(cites), "| chapter cards:", len(page_cites),
          "| locator:", page_cites[0]["locator"] if page_cites else None)
    assert page_cites, "no chapter citation recorded"
    assert "p.109" in page_cites[0]["locator"]
    browse = urllib.request.urlopen(
        BASE + "/browse?book=" + urllib.parse.quote(b["book"]) + "&page=109", timeout=30)
    print("browse deep link:", browse.status, len(browse.read()), "bytes")
    assert browse.status == 200
    print("search mode:", s["mode"], "results:", len(s["results"]),
          "pages:", len(s.get("pages") or []), "chapter:", s["chapter"]["title"])
    assert s["mode"] == "page_only"
    assert (s["chapter"]["page_start"], s["chapter"]["page_end"]) == (109, 128)

    first = s["pages"][0]["page_image"]
    with urllib.request.urlopen(BASE + first, timeout=60) as r:
        data = r.read()
    print("first page image:", len(data), "bytes")

    # a book without a chapter index still searches normally
    plain = get("/v1/search?q=" + urllib.parse.quote("列宁"))
    print("plain search:", plain["mode"], "results:", len(plain["results"]))
    assert plain["mode"] in ("bge+rerank", "fts")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
