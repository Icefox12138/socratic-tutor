"""Command line for building 卷/篇/回 indexes from OCR dumps.

  classics-index volumes --headers heads.jsonl --out toc.json
  classics-index pian    --toc toc.json --band titles.jsonl --out toc-pian.json
  classics-index hui     --ocr hui.jsonl --names "1=西游记,2=水浒传" --out hui.json
  classics-index find    --toc toc.json --q 卷3
  classics-index at      --toc toc.json --page 50
"""
import argparse
import json
import os
import re
import sys

from . import core, hui

PIAN = re.compile(r"(本紀|本纪|紀|纪|世家|列傳|列传|傳|传|書|书|表|志)\s*第\s*[〇零一二三四五六七八九十百]{1,4}")
LEADER = re.compile(r"…|\.{2,}|·{2,}|(……)")


def _read_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _width(line):
    box = line.get("box") or [0, 0, 0, 0]
    try:
        return abs(int(box[2]) - int(box[0]))
    except Exception:
        return 0


def _volumes_from_headers(records, min_run):
    vols = {int(r["page"]): r.get("vol") for r in records if r.get("vol")}
    return core.build_from_volumes(core.clean_volumes(vols, min_run=min_run))


def _volumes_from_band(records, min_run):
    vols = {}
    for rec in records:
        lines = rec.get("lines") or []
        vols[int(rec["page"])] = core.volume_of(lines)
    return core.build_from_volumes(core.clean_volumes(vols, min_run=min_run))


def _with_matter(chapters, total):
    chapters = [dict(c, level=1) for c in chapters]
    if chapters and chapters[0]["page_start"] > 1:
        chapters.insert(0, {"ord": 0, "level": 1, "title": "卷首（目錄/出版說明）",
                            "page_start": 1, "page_end": chapters[0]["page_start"] - 1,
                            "volume": None, "pages": chapters[0]["page_start"] - 1})
    if chapters and chapters[-1]["page_end"] < total:
        last = chapters[-1]
        chapters.append({"ord": len(chapters), "level": 1, "title": "卷末（附錄）",
                         "page_start": last["page_end"] + 1, "page_end": total,
                         "volume": None, "pages": total - last["page_end"]})
    for i, c in enumerate(chapters):
        c["ord"] = i
        c["pages"] = c["page_end"] - c["page_start"] + 1
    return chapters


def _pian_candidates(records, ratio=0.0):
    """{page: (text, width)} for title-sized 篇 lines."""
    out = {}
    for rec in records:
        lines = rec.get("lines") or []
        widths = [_width(l) for l in lines if _width(l)]
        median = sorted(widths)[len(widths) // 2] if widths else 0
        best = None
        for line in lines:
            text = str(line.get("text") or "").strip()
            m = PIAN.search(text)
            if len(text) > 12 or not m:
                continue
            w = _width(line)
            if ratio and median and w < median * ratio:
                continue
            tail = text[m.end():].strip()
            if LEADER.search(text) or (tail and re.search(r"[：:.。…·・]", tail)):
                continue
            key = (len(text), w)
            if best is None or key > best[0]:
                best = (key, (text, w))
        if best:
            out[int(rec["page"])] = best[1]
    return out


def cmd_volumes(args):
    records = _read_jsonl(args.headers or args.band)
    chapters = (_volumes_from_headers(records, args.min_run) if args.headers
                else _volumes_from_band(records, args.min_run))
    total = args.total or max(int(r["page"]) for r in records)
    chapters = _with_matter(chapters, total)
    json.dump({"chapters": chapters}, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("volumes=%d pages=%d -> %s" % (len(chapters), total, args.out))


def cmd_pian(args):
    toc = json.load(open(args.toc, encoding="utf-8"))
    chapters = [c for c in toc["chapters"] if (c.get("level") or 1) == 1]
    total = max(c["page_end"] for c in chapters)
    hits = _pian_candidates(_read_jsonl(args.band), args.ratio)
    by_vol = {}
    for page in sorted(hits):
        vol = core.bind_to_volume(page, chapters)
        if vol is not None:
            by_vol.setdefault(vol, []).append((page, hits[page][0]))
    by_vol = {v: core.pian_sequence(items) for v, items in by_vol.items()}
    by_vol = {v: items for v, items in by_vol.items() if items}
    rows = core.merge_pian(chapters, by_vol, total=total)
    json.dump({"chapters": rows}, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    level1 = [r for r in rows if r["level"] == 1]
    print("rows=%d (篇=%d) coverage=%d/%d -> %s"
          % (len(rows), len(rows) - len(level1), sum(r["pages"] for r in level1), total, args.out))


def cmd_hui(args):
    names = {}
    for part in (args.names or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            names[int(k)] = v.strip()
    books = hui.build(_read_jsonl(args.ocr), threshold=args.threshold,
                      min_pages=args.min_pages, names=names)
    json.dump({"books": books}, open(args.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for bi, rows in enumerate(books):
        print("book%d %s: %d 回, p%d-%d"
              % (bi + 1, rows[0].get("book_name", ""), len(rows),
                 rows[0]["page_start"], rows[-1]["page_end"]))
    print("-> " + args.out)


def _load(path):
    return json.load(open(path, encoding="utf-8"))["chapters"]


def cmd_find(args):
    row = core.find(_load(args.toc), args.q)
    print(json.dumps(row, ensure_ascii=False, indent=1) if row else "not found")
    return 0 if row else 1


def cmd_at(args):
    row = core.at(_load(args.toc), args.page)
    print(json.dumps(row, ensure_ascii=False, indent=1) if row else "not found")
    return 0 if row else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="classics-index", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("volumes", help="卷 boundaries from running-header OCR")
    v.add_argument("--headers", help="header-strip OCR JSONL (page/vol)")
    v.add_argument("--band", help="title-band OCR JSONL (page/lines)")
    v.add_argument("--min-run", type=int, default=5)
    v.add_argument("--total", type=int, default=0)
    v.add_argument("--out", required=True)
    v.set_defaults(func=cmd_volumes)

    p = sub.add_parser("pian", help="篇 rows from title-band OCR")
    p.add_argument("--toc", required=True)
    p.add_argument("--band", required=True)
    p.add_argument("--ratio", type=float, default=0.0)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_pian)

    h = sub.add_parser("hui", help="回 segments for 章回 novels")
    h.add_argument("--ocr", required=True)
    h.add_argument("--threshold", type=float, default=0.55)
    h.add_argument("--min-pages", type=int, default=4)
    h.add_argument("--names", default="")
    h.add_argument("--out", required=True)
    h.set_defaults(func=cmd_hui)

    f = sub.add_parser("find", help="locate a chapter by number or title")
    f.add_argument("--toc", required=True)
    f.add_argument("--q", required=True)
    f.set_defaults(func=cmd_find)

    a = sub.add_parser("at", help="chapter containing a page")
    a.add_argument("--toc", required=True)
    a.add_argument("--page", type=int, required=True)
    a.set_defaults(func=cmd_at)

    args = ap.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
