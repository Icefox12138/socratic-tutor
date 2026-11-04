"""Detect 篇 openings across the whole book from the right-hand title band.

For every page: take the lines of the band, compute the page's median line
width (body glyph size), and keep lines that (a) name a 篇 and (b) are wider
than the page's body text - the title is set in larger type. Candidates are
then bound to their 卷, ordered by 第X, and turned into level-2 rows.

  python build_pian_pages.py --book C1 --toc out/C1-toc.json --titles out/C1_titles.jsonl --report
"""
import argparse
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..", "..")
sys.path.insert(0, os.path.join(REPO, "sidecar"))

from app import toc as toc_mod  # noqa: E402

PIAN = re.compile(r"(本紀|本纪|世家|列傳|列传|書|书|表|志)\s*第\s*([〇零一二三四五六七八九十百]{1,4})")
CN = {c: i for i, c in enumerate("〇零一二三四五六七八九", 0)}
CN.update({"十": 10, "百": 100})


def width(line):
    box = line.get("box") or [0, 0, 0, 0]
    try:
        return abs(int(box[2]) - int(box[0]))
    except Exception:
        return 0


def load_titles(path):
    pages = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        pages[int(rec["page"])] = rec.get("lines") or []
    return pages


def candidates(pages, ratio=1.35):
    """{page: [(width, text)]} - title-sized 篇 lines only."""
    out = {}
    for pno, lines in pages.items():
        widths = [width(l) for l in lines if width(l) > 0]
        if not widths:
            continue
        median = statistics.median(widths) if widths else 0
        hits = []
        for l in lines:
            text = str(l.get("text") or "").strip()
            w = width(l)
            if len(text) > 10 or not PIAN.search(text):
                continue
            # Title pages put the 篇 name alone on a short line; body prose only
            # mentions a 篇 name inside a long column. Width is a weak secondary
            # signal (running headers are as wide as titles), so ratio=0 keeps
            # every short match and lets the 卷 binding reject the rest.
            if ratio <= 0 or w >= median * ratio:
                hits.append((w, text))
        if hits:
            out[pno] = sorted(hits, reverse=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--toc", required=True)
    ap.add_argument("--titles", required=True)
    ap.add_argument("--source", default="library")
    ap.add_argument("--ratio", type=float, default=0.0)
    ap.add_argument("--state-db", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    chapters = json.load(open(args.toc, encoding="utf-8"))["chapters"]
    pages = load_titles(args.titles)
    hits = candidates(pages, args.ratio)
    if args.report:
        print("pages with title candidates: %d of %d" % (len(hits), len(pages)))
        for pno in sorted(hits):
            print("  p%d  %s" % (pno, " | ".join("%s(w%d)" % (t, w) for w, t in hits[pno][:3])))

    # Bind each candidate page to the 卷 that owns it.
    spans = [(c["page_start"], c["page_end"], c["volume"], c) for c in chapters if c.get("volume")]
    by_vol = {}
    for pno in sorted(hits):
        for start, end, vol, ch in spans:
            if start <= pno <= end:
                by_vol.setdefault(vol, []).append((pno, hits[pno][0][1]))
                break

    print("volumes with a 篇 title: %d / %d" % (len(by_vol), len(spans)))
    for vol in sorted(by_vol):
        print("  卷%d: %s" % (vol, " ; ".join("p%d %s" % (p, t) for p, t in by_vol[vol])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
