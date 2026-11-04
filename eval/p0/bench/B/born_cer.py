import json
import os
import re

import pymupdf
from rapidocr_onnxruntime import RapidOCR

BASE = r"D:\Guo-Code"
B = os.path.join(BASE, "socratic-tutor", "eval", "p0", "bench", "B")
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


# born-digital Chinese candidate
path = os.path.join(BASE, "PDF", "计算机", "Linux-UNIX系统编程手册（上）.pdf")
if not os.path.exists(path):
    import glob
    hits = glob.glob(os.path.join(BASE, "PDF", "计算机", "**", "*Linux*系统编程*上*.pdf"), recursive=True)
    path = hits[0]

d = pymupdf.open(path)
rows = []
for pno in (200, 250, 300):
    if pno >= d.page_count:
        continue
    gt = d.load_page(pno).get_text("text") or ""
    pix = d.load_page(pno).get_pixmap(dpi=200)
    img = os.path.join(B, "pages", f"born_p{pno}.png")
    pix.save(img)
    res, _ = engine(img)
    got = "\n".join(x[1] for x in (res or []))
    a, b = norm(gt), norm(got)
    rows.append({"page": pno, "gt": len(a), "ocr": len(b), "cer": round(lev(a, b) / max(1, len(a)), 3)})
d.close()
json.dump({"path": path, "rows": rows}, open(os.path.join(B, "born-digital-cer.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(rows)
