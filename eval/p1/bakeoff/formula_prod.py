import argparse
import json
import os
import time

import numpy as np
from PIL import Image
from paddleocr import FormulaRecognitionPipeline, LayoutDetection

BASE = r"D:\Guo-Code\socratic-tutor\eval\p1\bakeoff"
OUT = os.path.join(BASE, "out", "formula-prod")
IMG = r"D:\Guo-Code\socratic-tutor\eval\p1\bakeoff\pages\线性代数 _ 数学专业用 = Linea_{p}_200.png"
SPECIAL = {118}  # quality-sensitive page: crop but no merge, flag for review


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default="114,122,126")
    args = ap.parse_args()
    pages = [int(x) for x in args.pages.split(",") if x.strip()]
    os.makedirs(OUT, exist_ok=True)
    layout = LayoutDetection(enable_mkldnn=False)
    rec = FormulaRecognitionPipeline(use_layout_detection=False,
                                     use_doc_orientation_classify=False,
                                     use_doc_unwarping=False,
                                     formula_recognition_batch_size=32,
                                     enable_mkldnn=False)
    full = None
    rows = []
    for p in pages:
        img = Image.open(IMG.format(p=p)).convert("RGB")
        t0 = time.perf_counter()
        if p in SPECIAL:
            if full is None:
                full = FormulaRecognitionPipeline(enable_mkldnn=False)
            res = full.predict(np.array(img))
            formulas = [f.get("rec_formula", "") for f in res[0].get("formula_res_list", [])]
            rects = [None] * len(formulas)
            merged = []
            t1 = time.perf_counter()
            t2 = t1
        else:
            boxes = layout.predict(np.array(img))[0]["boxes"]
            rects = [[*map(float, b["coordinate"])] for b in boxes
                     if b["label"] == "formula"]
            crops = [np.array(img.crop((max(0, x1 - 4), max(0, y1 - 4), x2 + 4, y2 + 4)))
                     for x1, y1, x2, y2 in rects]
            t1 = time.perf_counter()
            res = rec.predict(crops) if crops else []
            t2 = time.perf_counter()
            formulas = []
            for item in res:
                for f in item.get("formula_res_list", []) if hasattr(item, "get") else []:
                    formulas.append(f.get("rec_formula", ""))
            merged = rects
        rows.append({"page": p, "layout_ms": round((t1 - t0) * 1000, 1),
                     "rec_ms": round((t2 - t1) * 1000, 1),
                     "total_ms": round((t2 - t0) * 1000, 1),
                     "regions": len(rects), "formulas": len(formulas),
                     "chars": sum(len(x) for x in formulas),
                     "special": p in SPECIAL})
        payload = {"page": p, "formulas": formulas}
        if p in SPECIAL and rows[-1]["total_ms"] > 120000:
            payload["fallback"] = "page_image"
            payload["reason"] = "CPU > 120s; use original page image"
        json.dump(payload,
                  open(os.path.join(OUT, f"p{p}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(rows[-1], flush=True)
    json.dump(rows, open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
