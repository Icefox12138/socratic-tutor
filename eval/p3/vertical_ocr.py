"""OCR a vertical Chinese volume from pre-rendered page images (resumable).

  python vertical_ocr.py --book C1 --png-dir out/C1_pages --gpu --out out/C1.jsonl

Pages come from render_pages.py (run that in .venv-bge: it has pymupdf).
Output: one JSON object per page, {"page": n, "lines": [{"text", "score", "box"}]}.
Pages already in the output file are skipped, so a killed run resumes.
"""
import argparse
import glob
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


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
    for p in glob.glob(os.path.join(png_dir, book + "_p*.png")):
        m = re.search(r"_p(\d+)\.png$", p)
        if m:
            out[int(m.group(1))] = p
    return out


def make_ocr(use_gpu):
    from paddleocr import PaddleOCR
    kw = dict(use_doc_orientation_classify=False, use_doc_unwarping=False,
              use_textline_orientation=False, lang="ch", enable_mkldnn=False,
              text_detection_model_name="PP-OCRv5_mobile_det",
              text_recognition_model_name="PP-OCRv5_mobile_rec")
    if use_gpu:
        kw["device"] = "gpu"
    return PaddleOCR(**kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--png-dir", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--pages", default="")
    args = ap.parse_args()
    out = args.out or os.path.join(HERE, "out", args.book + ".jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    done = done_pages(out)
    imgs = page_images(args.png_dir, args.book)
    if not imgs:
        raise SystemExit("no page images in " + args.png_dir)
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
    print("book=%s pages=%d todo=%d out=%s" % (args.book, len(imgs), len(todo), out), flush=True)
    if not todo:
        return 0
    t0 = time.time()
    ocr = make_ocr(args.gpu)
    print("ocr ready in %.1fs" % (time.time() - t0), flush=True)
    t0 = time.time()
    with open(out, "a", encoding="utf-8") as fh:
        for n, pno in enumerate(todo, 1):
            res = ocr.predict(imgs[pno])
            lines = []
            for r in res or []:
                texts = r.get("rec_texts", []) if hasattr(r, "get") else []
                scores = r.get("rec_scores", []) if hasattr(r, "get") else []
                boxes = r.get("rec_boxes", []) if hasattr(r, "get") else []
                for i, t in enumerate(texts):
                    lines.append({"text": t,
                                  "score": round(float(scores[i]), 3) if i < len(scores) else None,
                                  "box": [int(x) for x in boxes[i]] if i < len(boxes) else None})
            fh.write(json.dumps({"page": pno, "lines": lines}, ensure_ascii=False) + "\n")
            fh.flush()
            if n % 10 == 0 or n == len(todo):
                rate = (time.time() - t0) / n
                print("p%d %.2fs/page eta %.0f min" % (pno, rate, rate * (len(todo) - n) / 60), flush=True)
    print("done %d pages in %.0fs" % (len(todo), time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
