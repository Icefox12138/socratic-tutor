import ast
import json
import os
import re

import pymupdf

BASE = r"D:\Guo-Code"
A = os.path.join(BASE, "socratic-tutor", "eval", "p0", "bench", "A")
manifest = json.load(open(os.path.join(BASE, "socratic-tutor", "eval", "p0", "catalog", "sample-manifest.json"), encoding="utf-8"))
S = {s["id"]: s for s in manifest["samples"]}

# --- A1 formula structure from text layer ---
d = pymupdf.open(S["A1"]["path"])
start, end = S["A1"]["window"]["start"], S["A1"]["window"]["end"]
lines = []
for i in range(start, end + 1):
    for ln in (d.load_page(i).get_text("text") or "").splitlines():
        ln = ln.strip()
        if ln:
            lines.append(ln)
d.close()

eq = [ln for ln in lines if "=" in ln and len(ln) < 80]
sym = [ln for ln in lines if re.search(r"[∫∑√≤≥±×÷∞→∂]", ln)]


def parseable(expr):
    e = expr.replace("×", "*").replace("÷", "/").replace("−", "-").replace("^", "**")
    e = e.replace("≤", "<=").replace("≥", ">=")
    try:
        ast.parse(e, mode="eval")
        return True
    except Exception:
        return False


parsed = sum(1 for e in eq if parseable(e.split("=")[0]))
a1 = {
    "lines": len(lines),
    "eq_lines": len(eq),
    "symbol_lines": len(sym),
    "parseable_lhs": parsed,
    "parse_rate": round(parsed / max(1, len(eq)), 3),
    "samples": eq[:12],
    "symbol_samples": sym[:6],
}

# --- OCR A2/A3/A4 ---
from rapidocr_onnxruntime import RapidOCR

engine = RapidOCR()
ocr = {}
targets = {
    "A2": ["A2_gold1_p119.png", "A2_mid_p143.png"],
    "A3": ["A3_mid_p186.png"],
    "A4": ["A4_gold1_p94.png"],
}
for sid, files in targets.items():
    texts = []
    for fn in files:
        p = os.path.join(A, "pages", fn)
        res, _ = engine(p)
        t = "\n".join(x[1] for x in (res or []))
        texts.append(t)
        open(os.path.join(A, fn.replace(".png", ".ocr.txt")), "w", encoding="utf-8").write(t)
    joined = "\n".join(texts)
    ocr[sid] = {
        "images": files,
        "chars": len(joined),
        "lines": len(joined.splitlines()),
        "eq_lines": sum(1 for ln in joined.splitlines() if "=" in ln),
        "chars_per_image": round(len(joined) / len(files), 1),
        "sample": joined[:400],
    }

out = {"A1": a1, "ocr": ocr}
json.dump(out, open(os.path.join(A, "A-extract2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: (v if k == "A1" else {kk: vv for kk, vv in v.items() if kk != "sample"}) for k, v in out.items()}, ensure_ascii=False, indent=1))
