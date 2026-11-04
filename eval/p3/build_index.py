"""Build 卷 + 篇 index from one title-band OCR pass.

The band (right ~40% of the page) carries both the running header ("史記卷X")
and, on an opening page, the 篇 name in larger type. So one pass yields both
levels: headers -> 卷 boundaries, wide 篇 lines -> 篇 starts.

  python build_index.py --book S2 --band out/S2_titles.jsonl --title "三国志 二"
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

PIAN = re.compile(r"(本紀|本纪|紀|纪|世家|列傳|列传|傳|传|書|书|表|志)\s*第\s*[〇零一二三四五六七八九十百]{1,4}")
# 目录 entries put leader dots between the 篇 name and its page number; opening
# pages never do. This is what separates a real title page from a list page.
LEADER = re.compile(r"…|\.{2,}|·{2,}|(……)")


def width(line):
    box = line.get("box") or [0, 0, 0, 0]
    try:
        return abs(int(box[2]) - int(box[0]))
    except Exception:
        return 0


def load(path):
    pages = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        pages[int(rec["page"])] = rec.get("lines") or []
    return pages


def pian_hits(pages, ratio):
    """{page: (text, width)} for title-sized 篇 lines."""
    out = {}
    for pno in sorted(pages):
        lines = pages[pno]
        widths = [width(l) for l in lines if width(l) > 0]
        if not widths:
            continue
        median = statistics.median(widths)
        best = None
        for l in lines:
            text = str(l.get("text") or "").strip()
            w = width(l)
            m = PIAN.search(text)
            if len(text) > 12 or not m or w < median * ratio:
                continue
            # A real title ends at the numeral; 目录 entries carry leader dots or
            # a colon after it ("春申君列傳第十八：").
            tail = text[m.end():].strip()
            if LEADER.search(text) or (tail and re.search(r"[：:.。…·・]", tail)):
                continue
            key = (len(text), w)
            if best is None or key > best[0]:
                best = (key, (text, w))
        if best:
            out[pno] = best[1]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--band", required=True, help="title-band OCR (篇 candidates)")
    ap.add_argument("--headers", default="", help="header-strip OCR (卷 boundaries; preferred)")
    ap.add_argument("--toc", default="", help="existing volume index JSON")
    ap.add_argument("--source", default="library")
    ap.add_argument("--pdf", default="", help="PDF path (unused by the index itself)")
    ap.add_argument("--key", default="", help="book key as pages.resolve() expects it (library-relative path)")
    ap.add_argument("--ratio", type=float, default=0.0,
                    help="width filter vs page median; 0 keeps every short 篇 line (the 卷 binding rejects 目录 noise)")
    ap.add_argument("--min-run", type=int, default=5)
    ap.add_argument("--state-db", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    pages = load(args.band)
    if args.toc:
        chapters = json.load(open(args.toc, encoding="utf-8"))["chapters"]
        chapters = [dict(c, level=1) for c in chapters if (c.get("level") or 1) == 1]
    elif args.headers:
        vols = {}
        for line in open(args.headers, encoding="utf-8"):
            line = line.strip()
            if line:
                rec = json.loads(line)
                vols[int(rec["page"])] = rec.get("vol")
        vols = {p: v for p, v in vols.items() if v}
        chapters = toc_mod.build_from_volumes(toc_mod.clean_volumes(vols, min_run=args.min_run))
    else:
        vols = {p: toc_mod.volume_of(lines) for p, lines in pages.items()}
        vols = toc_mod.clean_volumes(vols, min_run=args.min_run)
        chapters = toc_mod.build_from_volumes(vols)
    total = max(pages)
    if chapters and chapters[0]["page_start"] > 1 and not any(c.get("volume") is None for c in chapters):
        chapters.insert(0, {"ord": 0, "level": 1, "title": "卷首（目錄/出版說明）",
                            "page_start": 1, "page_end": chapters[0]["page_start"] - 1,
                            "volume": None, "pages": chapters[0]["page_start"] - 1})
    if chapters and chapters[-1]["page_end"] < total and not any(c.get("volume") is None for c in chapters):
        chapters.append({"ord": len(chapters), "level": 1, "title": "卷末（附錄）",
                         "page_start": chapters[-1]["page_end"] + 1, "page_end": total,
                         "volume": None, "pages": total - chapters[-1]["page_end"]})

    hits = pian_hits(pages, args.ratio)
    by_vol = {}
    for pno in sorted(hits):
        vol = toc_mod.bind_to_volume(pno, chapters)
        if vol is not None:
            by_vol.setdefault(vol, []).append((pno, hits[pno][0]))
    by_vol = {vol: toc_mod.pian_sequence(items) for vol, items in by_vol.items()}
    by_vol = {vol: items for vol, items in by_vol.items() if items}

    rows = toc_mod.merge_pian(chapters, by_vol, total=total)
    level1 = [r for r in rows if r["level"] == 1]
    pian_count = len(rows) - len(level1)
    print("pages=%d volumes=%d pian=%d coverage=%d/%d"
          % (total, len(level1), pian_count,
             sum(r["pages"] for r in level1), total))
    if args.report:
        for r in rows:
            print("  %sL%d %-24s p%d-%d (%d)"
                  % ("  " if r["level"] == 2 else "", r["level"], r["title"],
                     r["page_start"], r["page_end"], r["pages"]))
        orphans = [p for p in hits if toc_mod.bind_to_volume(p, chapters) is None]
        if orphans:
            print("  unbound title pages:", orphans)

    key = args.key or (args.book + ".pdf" if args.pdf else args.book)
    if not args.key:
        # Sample books: reuse the library-relative path the sidecar resolves.
        try:
            man = json.load(open(os.path.join(REPO, "eval", "p0", "catalog", "sample-manifest.json"),
                                 encoding="utf-8"))
            for s in man["samples"]:
                if s["id"] == args.book:
                    key = s["rel"].split("PDF\\", 1)[-1]
        except Exception:
            pass
    toc_mod.save(args.source, key, rows,
                 meta={"band_pages": len(pages), "pian": pian_count}, path=args.state_db)
    out = args.out or os.path.join(HERE, "out", args.book + "-index.json")
    json.dump({"source": args.source, "book": key, "chapters": rows},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("-> " + out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
