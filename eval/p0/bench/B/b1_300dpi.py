import json
import os
import re

import pymupdf
from rapidocr_onnxruntime import RapidOCR

BASE = r"D:\Guo-Code"
B = os.path.join(BASE, "socratic-tutor", "eval", "p0", "bench", "B")
manifest = json.load(open(os.path.join(BASE, "socratic-tutor", "eval", "p0", "catalog", "sample-manifest.json"), encoding="utf-8"))
S = {s["id"]: s for s in manifest["samples"]}
b1 = S["B1"]
engine = RapidOCR()


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


rows = []
d = pymupdf.open(b1["path"])
for pno in [b1["window"]["start"] + k * 15 for k in range(3)]:
    gt = d.load_page(pno).get_text("text") or ""
    pix = d.load_page(pno).get_pixmap(dpi=300)
    img = os.path.join(B, "pages", f"B1_300dpi_p{pno}.png")
    pix.save(img)
    res, _ = engine(img)
    got = "\n".join(x[1] for x in (res or []))
    a, b = norm(gt), norm(got)
    rows.append({"page": pno, "gt": len(a), "ocr": len(b), "cer": round(lev(a, b) / max(1, len(a)), 3)})
d.close()
json.dump(rows, open(os.path.join(B, "B1-300dpi.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(rows)
