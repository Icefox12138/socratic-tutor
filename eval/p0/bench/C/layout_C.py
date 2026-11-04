import json
import os

import cv2
import numpy as np
import pymupdf
from rapidocr_onnxruntime import RapidOCR

BASE = r"D:\Guo-Code"
C = os.path.join(BASE, "socratic-tutor", "eval", "p0", "bench", "C")
os.makedirs(os.path.join(C, "pages"), exist_ok=True)
manifest = json.load(open(os.path.join(BASE, "socratic-tutor", "eval", "p0", "catalog", "sample-manifest.json"), encoding="utf-8"))
S = {s["id"]: s for s in manifest["samples"]}
engine = RapidOCR()


def render(path, pno, dpi=200):
    d = pymupdf.open(path)
    pix = d.load_page(pno).get_pixmap(dpi=dpi)
    out = os.path.join(C, "pages", f"{os.path.basename(path)[:8]}_p{pno}.png")
    pix.save(out)
    d.close()
    return out


def imread_u(path, flags=cv2.IMREAD_GRAYSCALE):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), flags)


def imwrite_u(path, img):
    ok, buf = cv2.imencode(".png", img)
    if ok:
        buf.tofile(path)


def columns(img_path):
    img = imread_u(img_path)
    _, bw = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # crop to ink bbox
    ys, xs = np.where(bw > 0)
    if len(xs) == 0:
        return img, [], []
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    crop = bw[y0:y1 + 1, x0:x1 + 1]
    proj = (crop > 0).sum(axis=0).astype(float)
    thr = max(2.0, proj.max() * 0.02)
    ink = proj > thr
    segs = []
    start = None
    gap = 0
    for i, v in enumerate(ink):
        if v:
            if start is None:
                start = i
            gap = 0
        else:
            if start is not None:
                gap += 1
                if gap >= 6:
                    segs.append((start, i - gap))
                    start = None
    if start is not None:
        segs.append((start, len(ink) - 1))
    segs = [(a, b) for a, b in segs if 25 <= b - a <= crop.shape[1] * 0.6]
    segs.sort(key=lambda s: s[0], reverse=True)  # right to left
    return img, crop, [(int(a + x0), int(b + x0), int(y0), int(y1)) for a, b in segs]


def annotate(img_path, boxes, out_path):
    img = imread_u(img_path, cv2.IMREAD_COLOR)
    for i, (x0, x1, y0, y1) in enumerate(boxes, 1):
        cv2.rectangle(img, (x0, y0), (x1, y1), (0, 0, 255), 3)
        cv2.putText(img, str(i), (x1 - 20, y0 + 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 0, 0), 3)
    imwrite_u(out_path, img)


def ocr_columns(img_path, boxes, n=3):
    img = imread_u(img_path)
    out = []
    for idx, (x0, x1, y0, y1) in enumerate(boxes[:n], 1):
        col = img[y0:y1 + 1, x0:x1 + 1]
        rot = cv2.rotate(col, cv2.ROTATE_90_COUNTERCLOCKWISE)
        tmp = os.path.join(C, "pages", f"_col_{idx}.png")
        imwrite_u(tmp, rot)
        res, _ = engine(tmp)
        text = "\n".join(x[1] for x in (res or []))
        out.append({"col": idx, "chars": len(text), "sample": text[:120]})
    return out


report = {}
for sid, pno in (("C1", 76), ("C2", 103)):
    p = S[sid]["path"]
    img = render(p, pno)
    _, crop, boxes = columns(img)
    ann = os.path.join(C, "pages", f"{sid}_p{pno}_annot.png")
    annotate(img, boxes, ann)
    ocr = ocr_columns(img, boxes, 3)
    report[sid] = {"page": pno, "image": img, "columns": len(boxes),
                   "boxes": boxes[:12], "ocr_first3": ocr,
                   "annotated": ann}
    print(sid, "columns", len(boxes), "ocr chars", [o["chars"] for o in ocr])

json.dump(report, open(os.path.join(C, "C-layout.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("done")
