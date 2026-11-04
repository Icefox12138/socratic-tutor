"""OCR only the top band of a horizontal 章回 novel page, looking for 第X回.

  python novel_hui_ocr.py --pdf <path> --pages 1-300 --out out/hui.jsonl
"""
import argparse
import json
import os
import re
import sys
import time

import pymupdf
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
HUI = re.compile(r"第\s*([〇零一二三四五六七八九十百千]{1,6})\s*回")


def done(path):
    seen = set()
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                seen.add(int(json.loads(line)["page"]))
            except Exception:
                pass
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "out", "hui.jsonl"))
    ap.add_argument("--pages", default="")
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--band", default="0.0,0.0,1.0,0.22")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    doc = pymupdf.open(args.pdf)
    x0, y0, x1, y1 = [float(v) for v in args.band.split(",")]
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
    wanted = wanted or list(range(1, doc.page_count + 1))
    seen = done(args.out)
    todo = [p for p in wanted if p not in seen]
    if args.limit:
        todo = todo[: args.limit]
    print("pages=%d todo=%d" % (doc.page_count, len(todo)), flush=True)
    if not todo:
        return 0

    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False,
                    use_textline_orientation=False, lang="ch", enable_mkldnn=False,
                    text_detection_model_name="PP-OCRv5_mobile_det",
                    text_recognition_model_name="PP-OCRv5_mobile_rec")
    tmp = os.path.join(HERE, "out", "_hui_tmp.png")
    t0 = time.time()
    with open(args.out, "a", encoding="utf-8") as fh:
        for n, pno in enumerate(todo, 1):
            page = doc.load_page(pno - 1)
            r = page.rect
            pix = page.get_pixmap(dpi=args.dpi, clip=pymupdf.Rect(
                r.x0 + x0 * r.width, r.y0 + y0 * r.height,
                r.x0 + x1 * r.width, r.y0 + y1 * r.height))
            pix.save(tmp)
            res = ocr.predict(tmp)
            texts = []
            for item in res or []:
                if hasattr(item, "get"):
                    texts.extend(item.get("rec_texts", []))
            hits = [t for t in texts if HUI.search(t)]
            fh.write(json.dumps({"page": pno, "texts": texts[:6], "hui": hits},
                                ensure_ascii=False) + "\n")
            fh.flush()
            if n % 25 == 0 or n == len(todo):
                rate = (time.time() - t0) / n
                print("p%d %.2fs/page eta %.1f min" % (pno, rate, rate * (len(todo) - n) / 60), flush=True)
    print("done %d pages in %.0fs" % (len(todo), time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
