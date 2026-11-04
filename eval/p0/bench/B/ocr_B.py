import json
import os
import re

import pymupdf
from rapidocr_onnxruntime import RapidOCR

BASE = r"D:\Guo-Code"
B = os.path.join(BASE, "socratic-tutor", "eval", "p0", "bench", "B")
os.makedirs(os.path.join(B, "pages"), exist_ok=True)
manifest = json.load(open(os.path.join(BASE, "socratic-tutor", "eval", "p0", "catalog", "sample-manifest.json"), encoding="utf-8"))
S = {s["id"]: s for s in manifest["samples"]}
engine = RapidOCR()
CJK = re.compile(r"[\u3400-\u9fff]")


def norm(s):
    return re.sub(r"[^\u3400-\u9fffa-zA-Z0-9]", "", s)


def lev(a, b):
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def ocr_page(path, pno, dpi=200):
    d = pymupdf.open(path)
    pix = d.load_page(pno).get_pixmap(dpi=dpi)
    img = os.path.join(B, "pages", f"_tmp_{os.path.basename(path)[:10]}_{pno}.png")
    pix.save(img)
    d.close()
    res, _ = engine(img)
    text = "\n".join(x[1] for x in (res or []))
    return text, img


def footnotes(text):
    pats = [r"^\s*[①-⑳]", r"^\s*[*※]", r"^\s*\[\d+\]", r"^\s*〔\d+〕", r"^\s*\d+\s+[^\d]"]
    n = 0
    for ln in text.splitlines():
        if any(re.match(p, ln) for p in pats):
            n += 1
    return n


report = {}
for sid in ("B1", "B2", "B3", "B4"):
    s = S[sid]
    start, end = s["window"]["start"], s["window"]["end"]
    d = pymupdf.open(s["path"])
    lens = [len((d.load_page(i).get_text("text") or "")) for i in range(start, end + 1)]
    text_layer = "\n".join((d.load_page(i).get_text("text") or "") for i in range(start, end + 1))
    d.close()
    report[sid] = {
        "path": s["path"], "pages": s["pages"], "window": [start, end],
        "avg_chars": round(sum(lens) / max(1, len(lens)), 1),
        "zero_pages": sum(1 for n in lens if n == 0),
        "text_chars": len(text_layer),
        "footnote_lines_textlayer": footnotes(text_layer),
        "sample": text_layer[:300],
    }

# B1 synthetic OCR benchmark: render text-layer pages, OCR, CER vs text layer
b1 = S["B1"]
d = pymupdf.open(b1["path"])
cer_rows = []
for pno in [b1["window"]["start"] + k * 5 for k in range(8)]:
    gt = d.load_page(pno).get_text("text") or ""
    d.close() if False else None
    d2 = pymupdf.open(b1["path"])
    pix = d2.load_page(pno).get_pixmap(dpi=200)
    img = os.path.join(B, "pages", f"B1_p{pno}.png")
    pix.save(img)
    d2.close()
    res, _ = engine(img)
    got = "\n".join(x[1] for x in (res or []))
    a, b = norm(gt), norm(got)
    cer_rows.append({"page": pno, "gt": len(a), "ocr": len(b),
                     "cer": round(lev(a, b) / max(1, len(a)), 3),
                     "ocr_sample": got[:120]})
d.close()
report["B1_synthetic_ocr"] = cer_rows

# B2/B3 OCR 60/30 pages (subsample 12 pages each for time), B4 text stats only
for sid, pages in (("B2", 12), ("B3", 8)):
    s = S[sid]
    start, end = s["window"]["start"], s["window"]["end"]
    step = max(1, (end - start) // pages)
    texts = []
    for pno in range(start, end + 1, step):
        t, _ = ocr_page(s["path"], pno)
        texts.append(t)
    joined = "\n".join(texts)
    report[sid].update({
        "ocr_pages": len(texts),
        "ocr_chars": len(joined),
        "ocr_chars_per_page": round(len(joined) / max(1, len(texts)), 1),
        "ocr_sample": joined[:300],
        "footnote_lines_ocr": footnotes(joined),
    })
    open(os.path.join(B, f"{sid}_ocr.txt"), "w", encoding="utf-8").write(joined)

json.dump(report, open(os.path.join(B, "B-extract.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "sample" and kk != "ocr_sample"} if isinstance(v, dict) else v for k, v in report.items()}, ensure_ascii=False, indent=1)[:3000])
