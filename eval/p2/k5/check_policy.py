"""End-to-end check of the page-image-only policy against a running sidecar."""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8765"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=120) as r:
        return r.status, r.read()


def main():
    status, body = get("/health")
    health = json.loads(body)
    print("health:", {k: health[k] for k in ("chunks", "bge", "image_only_langs")})
    status, body = get("/v1/search?q=Socrates%20on%20courage&limit=8")
    payload = json.loads(body)
    print("search mode=%s took=%sms results=%d" % (payload["mode"], payload["took_ms"], len(payload["results"])))
    greek = [r for r in payload["results"] if r["lang"] == "greek"]
    other = [r for r in payload["results"] if r["lang"] != "greek"]
    print("greek hits=%d other=%d" % (len(greek), len(other)))
    for r in greek[:3]:
        ok_text = r["text"] == ""
        img = r["citation"]["page_image"]
        st, data = get(img)
        print("  greek p%d text_empty=%s image_only=%s pages=%s %d bytes" % (
            r["page"], ok_text, r.get("image_only"), st, len(data)))
    for r in other[:2]:
        print("  %s p%d text_len=%d" % (r["lang"], r["page"], len(r["text"])))
    if greek:
        cid = greek[0]["chunk_id"]
        st, body = get("/v1/chunks/%d" % cid)
        chunk = json.loads(body)
        print("chunk %d: text=%r image_only=%s locator=%s" % (
            cid, chunk["text"], chunk.get("image_only"), chunk["citation"]["locator"]))
    bad = [r for r in greek if r["text"] != ""]
    print("VIOLATIONS:", len(bad))
    return 0 if not bad and greek else 1


if __name__ == "__main__":
    sys.exit(main())
