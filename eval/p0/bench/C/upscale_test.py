import json
import os

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

C = os.path.dirname(os.path.abspath(__file__))
engine = RapidOCR()
d = json.load(open(os.path.join(C, "C-layout.json"), encoding="utf-8"))
boxes = [tuple(b) for b in d["C1"]["boxes"][:4]]
img_path = d["C1"]["image"]
img = cv2.imdecode(np.fromfile(img_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)

rows = []
for i, (x0, x1, y0, y1) in enumerate(boxes, 1):
    col = img[y0:y1 + 1, x0:x1 + 1]
    rot = cv2.rotate(col, cv2.ROTATE_90_COUNTERCLOCKWISE)
    up = cv2.resize(rot, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    up = cv2.copyMakeBorder(up, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
    tmp = os.path.join(C, "pages", f"_col_up_{i}.png")
    ok, buf = cv2.imencode(".png", up)
    buf.tofile(tmp)
    res, _ = engine(tmp)
    text = "\n".join(x[1] for x in (res or []))
    rows.append({"col": i, "shape": up.shape, "chars": len(text), "sample": text[:80]})
    print(i, up.shape, len(text), text[:60].encode("unicode_escape").decode())

json.dump(rows, open(os.path.join(C, "C-upscale-ocr.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
