import json
import os
import re

import pymupdf

BASE = r"D:\Guo-Code"
D = os.path.join(BASE, "socratic-tutor", "eval", "p0", "bench", "D")
os.makedirs(D, exist_ok=True)
manifest = json.load(open(os.path.join(BASE, "socratic-tutor", "eval", "p0", "catalog", "sample-manifest.json"), encoding="utf-8"))
S = {s["id"]: s for s in manifest["samples"]}

GREEK = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
GREEK_FONTS = ("newathena", "gfsporson", "spionic", "gentium", "symbol")
LEMMA = re.compile(r"^[^\s:]{2,30}\s*:")


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
    if prev == "text" and LEMMA.match(t.strip()):
        return "gloss"
    return "gloss" if "times" in f else "note"


def parse(path, pages=12):
    d = pymupdf.open(path)
    counts = {"text": 0, "gloss": 0, "note": 0, "lineno": 0}
    samples = {"text": [], "gloss": [], "note": []}
    picks = sorted({max(0, min(d.page_count - 1, int(d.page_count * f))) for f in (0.15, 0.35, 0.55, 0.75, 0.9)})
    for p in picks:
        prev = None
        for b in d.load_page(p).get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    kind = classify(s, prev)
                    counts[kind] += len(s["text"])
                    if kind in samples and len(samples[kind]) < 5 and len(s["text"].strip()) > 8:
                        samples[kind].append(s["text"].strip()[:60])
                    prev = kind
    d.close()
    return counts, samples


out = {}
for sid in ("K1", "K2", "K3", "K4"):
    counts, samples = parse(S[sid]["path"])
    total = sum(counts.values()) or 1
    out[sid] = {"counts": counts, "share": {k: round(v / total, 3) for k, v in counts.items()},
                "samples": samples}
    print(sid, counts, out[sid]["share"])

json.dump(out, open(os.path.join(D, "D-streams.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
