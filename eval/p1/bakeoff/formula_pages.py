import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_bakeoff as rb
from paddleocr import FormulaRecognitionPipeline

BASE = r"D:\Guo-Code\socratic-tutor\eval\p1\bakeoff"
OUT = os.path.join(BASE, "out", "formula")
MAN = r"D:\Guo-Code\socratic-tutor\eval\p0\catalog\sample-manifest.json"
PAGES = [114, 118, 122, 126, 130, 134, 138, 142, 146, 150, 154, 158]


def main():
    os.makedirs(OUT, exist_ok=True)
    man = {s["id"]: s for s in json.load(open(MAN, encoding="utf-8"))["samples"]}
    pdf = man["A2"]["path"]
    pipe = FormulaRecognitionPipeline(enable_mkldnn=False)
    rows = []
    for p in PAGES:
        img = rb.page_png(pdf, p, 200)
        t = time.perf_counter()
        res = pipe.predict(img)
        ms = (time.perf_counter() - t) * 1000
        out = res[0] if res else {}
        fs = out.get("formula_res_list", []) if hasattr(out, "get") else []
        formulas = [{"latex": f.get("rec_formula", ""),
                     "bbox": str(f.get("dt_polys"))[:200]} for f in fs if hasattr(f, "get")]
        json.dump({"page": p, "ms": round(ms, 1), "formulas": formulas},
                  open(os.path.join(OUT, f"p{p}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        rows.append({"page": p, "ms": round(ms, 1), "n": len(formulas),
                     "chars": sum(len(f["latex"]) for f in formulas)})
        print(rows[-1], flush=True)
    total = sum(r["n"] for r in rows)
    json.dump({"rows": rows, "pages": len(rows), "formulas": total},
              open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("TOTAL", total, "pages", len(rows))


if __name__ == "__main__":
    main()
