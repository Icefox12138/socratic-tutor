"""Segment a 章回 novel into 回 by its running header, then number the segments.

The header repeats the 回 title on every leaf of that 回, so a change of title
is a chapter boundary. Numbers are read from the leaves that also show
"第X回"; the rest are filled by counting, which is stable as long as the
boundaries are right. A similarity threshold absorbs OCR noise.

  python build_hui_segments.py --ocr out/hui.jsonl --out out/hui-index.json --report
"""
import argparse
import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(REPO, "sidecar"))

from app import toc as toc_mod  # noqa: E402

NUM = re.compile(r"第\s*([〇零一二三四五六七八九十百千]{1,6})\s*回")
CJK = re.compile(r"[\u3400-\u9fff]")


def clean(text):
    return "".join(CJK.findall(text or ""))


def load(path):
    pages = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        texts = [t for t in (rec.get("texts") or []) if t.strip()]
        num, titles = None, []
        for t in texts:
            m = NUM.search(t)
            if m:
                if num is None:
                    num = toc_mod.cn2int(m.group(1))
                continue
            c = clean(t)
            if 4 <= len(c) <= 16:
                titles.append(c)
        # OCR often splits the heading into "第" / "九" / "回"; join first.
        if num is None:
            m = NUM.search("".join(texts))
            if m:
                num = toc_mod.cn2int(m.group(1))
        appendix = any(clean(t) in ("附", "录", "錄", "附录", "附錄") for t in texts)
        best = max(titles, key=len) if titles else ""
        pages[int(rec["page"])] = {"num": num, "title": best, "appendix": appendix}
    return pages


def sim(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def merge_short(runs, min_pages=4):
    """A one- or two-leaf run is an OCR blip, not a chapter: fold it back."""
    out = []
    for r in runs:
        if out and (r["end"] - r["start"] + 1) < min_pages:
            out[-1]["end"] = r["end"]
            out[-1]["count"] += r.get("count", 1)
            out[-1]["appendix"] = out[-1].get("appendix") or r.get("appendix")
            continue
        out.append(r)
    return out


def mark_appendix(runs, pages):
    """A run is 附录 when any leaf in it carries the 附/录 marker."""
    for r in runs:
        r["appendix"] = any(pages.get(p, {}).get("appendix")
                            for p in range(r["start"], r["end"] + 1))
    return runs


def segment(pages, threshold=0.55):
    runs = []
    for pno in sorted(pages):
        rec = pages[pno]
        title = rec["title"]
        if not title:
            continue
        if runs and sim(title, runs[-1]["title"]) >= threshold:
            runs[-1]["end"] = pno
            runs[-1]["count"] += 1
            runs[-1]["appendix"] = runs[-1]["appendix"] or rec["appendix"]
            continue
        # A lone odd header is noise: look ahead before cutting.
        nxt = pages.get(pno + 1, {}).get("title", "")
        if (runs and not rec["num"] and nxt and sim(nxt, runs[-1]["title"]) >= threshold):
            runs[-1]["end"] = pno
            continue
        runs.append({"start": pno, "end": pno, "title": title, "count": 1,
                     "appendix": rec["appendix"]})
    return runs


def number(runs, pages):
    """Assign 回 numbers: trust detected ones, count the rest."""
    for r in runs:
        r["num"] = None
    for i, r in enumerate(runs):
        nums = [pages_num for pages_num in range(r["start"], r["end"] + 1)]
        found = None
        for p in range(r["start"], min(r["end"], r["start"] + 3) + 1):
            rec = pages.get(p) or {}
            if rec.get("num"):
                found = rec["num"]
                break
        if found:
            r["num"] = found
    # 附录 is inserted between two 回 and carries the same header, so it must
    # not consume a number: count only real 回.
    last = 0
    for r in runs:
        if r.get("appendix"):
            r["num"] = None
            continue
        if r["num"] is None and last:
            r["num"] = last + 1
        last = r["num"] or last
    for i in range(len(runs) - 1, -1, -1):
        if runs[i].get("appendix"):
            continue
        if runs[i]["num"] is None and i + 1 < len(runs):
            nxt = next((r["num"] for r in runs[i + 1:] if r["num"]), None)
            if nxt:
                runs[i]["num"] = nxt - 1
    return runs


def trim(runs):
    """Drop front-matter runs that precede the first numbered 回."""
    first = next((i for i, r in enumerate(runs) if r["num"]), 0)
    runs = runs[first:]
    for i, r in enumerate(runs):
        r["ord"] = i
        r["level"] = 2
        r["page_start"], r["page_end"] = r["start"], None
    for i, r in enumerate(runs):
        r["page_end"] = runs[i + 1]["start"] - 1 if i + 1 < len(runs) else r["end"]
        r["pages"] = r["page_end"] - r["page_start"] + 1
        r["printed"] = r["num"]          # what the header said, if anything
        r["num"] = i + 1                 # position in the sequence is the index
        r["title_text"] = ("附录 " + r["title"]) if r.get("appendix") else r["title"]
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ocr", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "out", "hui-index.json"))
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.55)
    ap.add_argument("--min-pages", type=int, default=4)
    ap.add_argument("--names", default="", help="1=西游记,2=水浒传 给分出来的书起名")
    args = ap.parse_args()
    pages = load(args.ocr)
    runs = segment(pages, args.threshold)
    runs = merge_short(runs, args.min_pages)
    runs = mark_appendix(runs, pages)
    runs = trim(number(runs, pages))
    nums = [r["num"] for r in runs]
    real = [n for n in nums if n]
    gaps = [(a, b) for a, b in zip(real, real[1:]) if b != a + 1]
    print("pages=%d rows=%d 回=%d appendix=%d first=%s last=%s gaps=%d"
          % (len(pages), len(runs), len(real), len(runs) - len(real),
             real[0] if real else None, real[-1] if real else None, len(gaps)))
    if args.report:
        for r in runs[:10]:
            print("  回%-4s p%-5d-%-5d %s" % (r["num"], r["page_start"], r["page_end"], r["title_text"][:24]))
        for g in gaps[:5]:
            print("  gap:", g)
    # A novel starts where the printed 回 number drops back to the beginning.
    books, cur, last = [], [], 0
    for r in runs:
        pr = r.get("printed") or 0
        if cur and pr and pr <= 3 and last >= 10:
            books.append(cur)
            cur = []
        cur.append(r)
        last = pr or last
    if cur:
        books.append(cur)
    names = {}
    for part in args.names.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            names[int(k)] = v.strip()
    for bi, rows in enumerate(books):
        for r in rows:
            r["book"] = bi + 1
            r["book_name"] = names.get(bi + 1, "第%d部" % (bi + 1))
    json.dump({"books": books, "runs": runs}, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for bi, rows in enumerate(books):
        print("  book%d: %d 回, p%d-%d" % (bi + 1, len(rows), rows[0]["page_start"], rows[-1]["page_end"]))
    print("-> " + args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
