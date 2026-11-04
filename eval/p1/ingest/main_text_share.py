import json
import os
import re

import pymupdf

BASE = r"D:\Guo-Code"
OUT = os.path.join(BASE, "socratic-tutor", "eval", "p1", "ingest")
manifest_path = os.path.join(OUT, "steadman-manifest.json")
manifest = json.load(open(manifest_path, encoding="utf-8"))

GREEK = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
GREEK_FONTS = ("newathena", "gfsporson", "spionic", "gentium", "symbol")


def classify(span, prev):
    f = span["font"].lower()
    t = span["text"]
    if GREEK.search(t):
        return "text"
    if any(g in f for g in GREEK_FONTS):
        return "text"
    if "bold" in f or "italic" in f:
        return "note"
    if re.fullmatch(r"\d{1,3}", t.strip()):
        return "lineno"
    return "gloss"


for v in manifest["volumes"]:
    path = os.path.join(OUT, "..", "..", "..", "..", "PDF-new", "Steadman", v["lang"], v["volume"] + ".pdf")
    path = os.path.abspath(path)
    if not os.path.exists(path):
        v["main_text_share"] = None
        v["commentary_only"] = None
        continue
    doc = pymupdf.open(path)
    picks = sorted({max(0, min(doc.page_count - 1, int(doc.page_count * f))) for f in (0.15, 0.35, 0.55, 0.75, 0.9)})
    counts = {"text": 0, "gloss": 0, "note": 0, "lineno": 0}
    for p in picks:
        prev = None
        for b in doc.load_page(p).get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    k = classify(s, prev)
                    counts[k] += len(s["text"])
                    prev = k
    doc.close()
    total = sum(counts.values()) or 1
    share = round(counts["text"] / total, 3)
    v["main_text_share"] = share
    v["main_text_counts"] = counts
    v["commentary_only"] = share < 0.10

json.dump(manifest, open(manifest_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
co = [v for v in manifest["volumes"] if v.get("commentary_only")]
print(json.dumps({"volumes": len(manifest["volumes"]), "commentary_only": len(co),
                  "examples": [v["volume"] for v in co[:8]]}, ensure_ascii=False, indent=1))
