import json
import os
import time

import numpy as np
from PIL import Image
from paddleocr import FormulaRecognitionPipeline, LayoutDetection

BASE = r"D:\Guo-Code\socratic-tutor\eval\p1\bakeoff"
OUT = os.path.join(BASE, "out", "formula-fast")
PAGES = [114, 118, 122, 126]
IMG = r"D:\Guo-Code\socratic-tutor\eval\p1\bakeoff\pages\线性代数 _ 数学专业用 = Linea_{p}_200.png"


def merge_boxes(rects, gap=12):
    rects = [list(map(float, r)) for r in rects]
    changed = True
    while changed:
        changed = False
        out = []
        while rects:
            a = rects.pop()
            merged = False
            for i, b in enumerate(rects):
                if (a[0] <= b[2] + gap and b[0] <= a[2] + gap and
                        a[1] <= b[3] + gap and b[1] <= a[3] + gap):
                    rects[i] = [min(a[0], b[0]), min(a[1], b[1]),
                                max(a[2], b[2]), max(a[3], b[3])]
                    merged = changed = True
                    break
            if not merged:
                out.append(a)
        rects = out
    return sorted(rects, key=lambda r: (r[1], r[0]))


def main():
    os.makedirs(OUT, exist_ok=True)
    layout = LayoutDetection(enable_mkldnn=False)
    rec = FormulaRecognitionPipeline(use_layout_detection=False,
                                     use_doc_orientation_classify=False,
                                     use_doc_unwarping=False,
                                     formula_recognition_batch_size=32,
                                     enable_mkldnn=False)
    rows = []
    for p in PAGES:
        img = Image.open(IMG.format(p=p)).convert("RGB")
        t0 = time.perf_counter()
        boxes = layout.predict(np.array(img))[0]["boxes"]
        rects = [[*map(float, b["coordinate"])] for b in boxes
                 if b["label"] == "formula"]
        merged = merge_boxes(rects, 12)
        crops = []
        for x1, y1, x2, y2 in merged:
            crops.append(np.array(img.crop((max(0, x1 - 4), max(0, y1 - 4),
                                            x2 + 4, y2 + 4))))
        t1 = time.perf_counter()
        res = rec.predict(crops) if crops else []
        t2 = time.perf_counter()
        formulas = []
        for item in res:
            for f in item.get("formula_res_list", []) if hasattr(item, "get") else []:
                formulas.append(f.get("rec_formula", ""))
        rows.append({"page": p, "layout_ms": round((t1 - t0) * 1000, 1),
                     "rec_ms": round((t2 - t1) * 1000, 1),
                     "total_ms": round((t2 - t0) * 1000, 1),
                     "regions_before": len(rects), "regions_after": len(merged),
                     "formulas": len(formulas), "chars": sum(len(x) for x in formulas)})
        json.dump({"page": p, "formulas": formulas},
                  open(os.path.join(OUT, f"p{p}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(rows[-1], flush=True)
    json.dump(rows, open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
