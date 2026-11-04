"""OCR only the right-edge running header (版心) of a vertical volume.

Full-page OCR costs ~10 s/page; the header crop costs ~1.2 s/page and carries
exactly what the chapter index needs: "史記卷X". Resumable like vertical_ocr.

  python vertical_header_ocr.py --book C1 --png-dir out/C1_pages --out out/C1_heads.jsonl
"""
import argparse
import json
import os
import re
import sys
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "sidecar"))
from app import toc as toc_mod  # noqa: E402


def done_pages(path):
    seen = set()
    if not os.path.exists(path):
        return seen
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                seen.add(int(json.loads(line)["page"]))
            except Exception:
                continue
    return seen


def page_images(png_dir, book):
    out = {}
    for f in os.listdir(png_dir):
        m = re.match(book + r"_p(\d+)\.png$", f)
        if m:
            out[int(m.group(1))] = os.path.join(png_dir, f)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--png-dir", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--crop", default="0.82,0.08,1.0,0.55")
    ap.add_argument("--pages", default="")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    out = args.out or os.path.join(HERE, "out", args.book + "_heads.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    x0, y0, x1, y1 = [float(v) for v in args.crop.split(",")]
    imgs = page_images(args.png_dir, args.book)
    if not imgs:
        raise SystemExit("no page images in " + args.png_dir)
    done = done_pages(out)
    wanted = []
    for part in args.pages.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            wanted.extend(range(int(a), int(b) + 1))
        else:
            wanted.append(int(part))
    wanted = wanted or sorted(imgs)
    todo = [p for p in wanted if p not in done and p in imgs]
    if args.limit:
        todo = todo[: args.limit]
    print("todo=%d out=%s" % (len(todo), out), flush=True)
    if not todo:
        return 0

    from paddleocr import PaddleOCR
    t0 = time.time()
    ocr = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False,
                    use_textline_orientation=False, lang="ch", enable_mkldnn=False,
                    text_detection_model_name="PP-OCRv5_mobile_det",
                    text_recognition_model_name="PP-OCRv5_mobile_rec")
    print("ocr ready %.1fs" % (time.time() - t0), flush=True)
    tmp = os.path.join(HERE, "out", "_head.png")
    t0 = time.time()
    with open(out, "a", encoding="utf-8") as fh:
        for n, pno in enumerate(todo, 1):
            im = Image.open(imgs[pno])
            w, h = im.size
            im.crop((int(w * x0), int(h * y0), int(w * x1), int(h * y1))).save(tmp)
            res = ocr.predict(tmp)
            texts, boxes = [], []
            for r in res or []:
                if not hasattr(r, "get"):
                    continue
                texts.extend(r.get("rec_texts", []))
                boxes.extend([list(b) for b in r.get("rec_boxes", [])])
            # The running header is the TOPMOST short line naming a 卷: TOC pages
            # also name volumes, but lower on the crop.
            cands = []
            for i, t in enumerate(texts):
                if "卷" not in t or len(t) > 14:
                    continue
                top = boxes[i][1] if i < len(boxes) else 1e9
                cands.append((top, t))
            cands.sort()
            head = cands[0][1] if cands else ""
            vol = toc_mod.volume_of([{"text": head}]) if head else None
            fh.write(json.dumps({"page": pno, "vol": vol, "head": head,
                                 "texts": texts[:6]}, ensure_ascii=False) + "\n")
            fh.flush()
            if n % 25 == 0 or n == len(todo):
                rate = (time.time() - t0) / n
                print("p%d %.2fs/page eta %.1f min" % (pno, rate, rate * (len(todo) - n) / 60), flush=True)
    print("done %d pages in %.0fs" % (len(todo), time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
