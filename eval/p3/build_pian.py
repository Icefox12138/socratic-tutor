"""Split each 卷 into its 篇 (本紀/書/表/世家/列傳) using the title page.

Vertical volumes put the 篇 name in large characters on the page where the 篇
starts (史记: "五帝本紀第一"). The chapter index knows where each 卷 starts, so
this only has to look at the pages around that boundary and pick the line with
the widest box (biggest glyphs) that matches 第X.

  python eval/p3/build_pian.py --book C1 --toc out/C1-toc.json \
      --shards out/C1_window.jsonl out/C1_front.jsonl
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

MANIFEST = os.path.join(REPO, "eval", "p0", "catalog", "sample-manifest.json")
PIAN = re.compile(r"(本紀|本纪|世家|列傳|列传|書|书|表)\s*第\s*([〇零一二三四五六七八九十百]{1,4})")


def sample(book_id):
    man = json.load(open(MANIFEST, encoding="utf-8"))
    for s in man["samples"]:
        if s["id"] == book_id:
            return s
    raise SystemExit("unknown book " + book_id)


def load(paths):
    pages = {}
    for p in paths:
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            pages[int(rec["page"])] = rec.get("lines") or []
    return pages


def width(line):
    box = line.get("box") or [0, 0, 0, 0]
    try:
        return abs(int(box[2]) - int(box[0]))
    except Exception:
        return 0


def find_title(pages, chapter, window=2):
    """Best 篇 title near a 卷 boundary: (page, title, width)."""
    start = chapter["page_start"]
    best = None
    for p in range(max(1, start - window), start + window + 1):
        for line in pages.get(p, []):
            text = str(line.get("text") or "").strip()
            if len(text) > 10:
                continue
            m = PIAN.search(text)
            if not m:
                continue
            cand = (p, text, width(line))
            # Prefer the longest title ("五帝本紀第一" over a split "本紀第一"),
            # then the page nearest the 卷 boundary, then the widest box.
            key = (len(text), -abs(p - start), cand[2])
            if best is None or key > best[0]:
                best = (key, cand)
    return best[1] if best else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--source", default="library")
    ap.add_argument("--toc", required=True)
    ap.add_argument("--shards", nargs="+", required=True)
    ap.add_argument("--state-db", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--window", type=int, default=2)
    args = ap.parse_args()

    s = sample(args.book)
    book_key = s["rel"].split("PDF\\", 1)[-1] if args.source == "library" else s["id"]
    chapters = json.load(open(args.toc, encoding="utf-8"))["chapters"]
    pages = load(args.shards)

    hits = {}
    for ch in chapters:
        if not ch.get("volume"):
            continue
        hit = find_title(pages, ch, args.window)
        if hit:
            hits[ch["volume"]] = (hit[0], hit[1])
            print("  卷%d -> %s @p%d (width %d)" % (ch["volume"], hit[1], hit[0], hit[2]))
    total = max(ch["page_end"] for ch in chapters) if chapters else 0
    rows = toc_mod.merge_pian(chapters, hits, total=total)
    level1 = [r for r in rows if r["level"] == 1]
    coverage = sum(r["pages"] for r in level1)
    print("rows=%d (level2=%d) level1 coverage=%d/%d"
          % (len(rows), len(hits), coverage, total))

    toc_mod.save(args.source, book_key, rows,
                 meta={"ocr_pages": len(pages), "pian": len(hits)}, path=args.state_db)
    out = args.out or os.path.join(HERE, "out", args.book + "-toc-pian.json")
    json.dump({"source": args.source, "book": book_key, "chapters": rows},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("-> " + out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
