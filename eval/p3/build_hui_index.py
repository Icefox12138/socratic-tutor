"""Turn per-page header OCR into a 回 index for a 章回 novel.

Only pages whose band shows "第X回" start a chapter; the title is the most
common header title inside that chapter's page range (the header repeats the
回 title on every leaf, so a vote is far steadier than any single OCR line).
A backwards jump of the number means the next novel in the bundle started.

  python build_hui_index.py --ocr out/hui.jsonl --out out/hui-index.json --report
"""
import argparse
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
        pages[int(rec["page"])] = {"num": num, "titles": titles}
    return pages


def vote_title(pages, start, end):
    counts = {}
    for p in range(start, end + 1):
        for t in pages.get(p, {}).get("titles", []):
            counts[t] = counts.get(t, 0) + 1
    if not counts:
        return ""
    return max(counts, key=lambda t: (counts[t], len(t)))


def split_books(starts):
    """Split 回 starts into novels when the number jumps backwards."""
    books, cur, last = [], [], 0
    for page, num in starts:
        if num <= last and num <= 3:
            books.append(cur)
            cur = []
        cur.append((page, num))
        last = num
    if cur:
        books.append(cur)
    return books


def build(pages):
    starts = []
    last = 0
    for pno in sorted(pages):
        n = pages[pno]["num"]
        if n and n > last:
            starts.append((pno, n))
            last = n
    out = []
    for rows in split_books(starts):
        built = []
        for i, (page, num) in enumerate(rows):
            end = (rows[i + 1][0] - 1) if i + 1 < len(rows) else max(pages)
            built.append({"num": num, "page_start": page, "page_end": end,
                          "pages": end - page + 1,
                          "title": vote_title(pages, page, end)})
        for i, r in enumerate(built):
            r["ord"] = i
            r["level"] = 2
        out.append(built)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ocr", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "out", "hui-index.json"))
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    pages = load(args.ocr)
    books = build(pages)
    print("pages=%d books=%d" % (len(pages), len(books)))
    for bi, rows in enumerate(books):
        nums = [r["num"] for r in rows]
        gaps = [b - a for a, b in zip(nums, nums[1:]) if b - a != 1]
        print("  book%d: %d 回, p%d-%d, gaps=%s"
              % (bi + 1, len(rows), rows[0]["page_start"], rows[-1]["page_end"], gaps[:5]))
        if args.report:
            for r in rows[:6]:
                print("     p%-5d 第%d回 %s" % (r["page_start"], r["num"], r["title"]))
    json.dump({"books": books}, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("-> " + args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
