"""章回小说: turn per-page header OCR into 回 segments.

A 章回 novel prints the current 回 title in the running header of every leaf,
so a change of header title is a chapter boundary. Numbers come from leaves
that also show "第X回"; the rest are filled by counting. An inserted 附录
(common in 西游记) repeats the previous header and must not consume a number.

Pure functions: pass in the parsed pages, get rows back.
"""
import difflib
import re

from . import core

# Chinese numerals dominate old typesetting, but modern reprints print 第12回.
NUM = re.compile(r"第\s*([〇零一二三四五六七八九十百千]{1,6}|\d{1,4})\s*回")
CJK = re.compile(r"[\u3400-\u9fff]")


def clean(text):
    return "".join(CJK.findall(text or ""))


def parse_records(records):
    """OCR records -> {page: {"num", "title", "appendix"}}.

    Accepts the JSONL objects written by novel_hui_ocr.py: {"page", "texts"}.
    """
    pages = {}
    for rec in records:
        texts = [t for t in (rec.get("texts") or []) if str(t).strip()]
        num, titles = None, []
        for t in texts:
            m = NUM.search(t)
            if m:
                if num is None:
                    num = core.cn2int(m.group(1))
                continue
            c = clean(t)
            if 4 <= len(c) <= 16:
                titles.append(c)
        if num is None:
            m = NUM.search("".join(texts))
            if m:
                num = core.cn2int(m.group(1))
        appendix = any(clean(t) in ("附", "录", "錄", "附录", "附錄") for t in texts)
        pages[int(rec["page"])] = {"num": num,
                                   "title": max(titles, key=len) if titles else "",
                                   "appendix": appendix}
    return pages


def sim(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def segment(pages, threshold=0.55):
    """Split pages into runs of one header title."""
    runs = []
    for pno in sorted(pages):
        rec = pages[pno]
        title = rec["title"]
        if not title:
            continue
        if runs and sim(title, runs[-1]["title"]) >= threshold:
            runs[-1]["end"] = pno
            runs[-1]["count"] += 1
            continue
        nxt = pages.get(pno + 1, {}).get("title", "")
        if runs and not rec["num"] and nxt and sim(nxt, runs[-1]["title"]) >= threshold:
            runs[-1]["end"] = pno
            continue
        runs.append({"start": pno, "end": pno, "title": title, "count": 1})
    return runs


def merge_short(runs, min_pages=4):
    """A one- or two-leaf run is an OCR blip, not a chapter: fold it back."""
    out = []
    for r in runs:
        if out and (r["end"] - r["start"] + 1) < min_pages:
            out[-1]["end"] = r["end"]
            out[-1]["count"] += r.get("count", 1)
            continue
        out.append(r)
    return out


def mark_appendix(runs, pages):
    for r in runs:
        r["appendix"] = any(pages.get(p, {}).get("appendix")
                            for p in range(r["start"], r["end"] + 1))
    return runs


def number(runs, pages):
    """Assign 回 numbers: trust detected ones, count the rest, skip 附录."""
    for r in runs:
        r["num"] = None
        r["detected"] = None
    for r in runs:
        for p in range(r["start"], min(r["end"], r["start"] + 3) + 1):
            rec = pages.get(p) or {}
            if rec.get("num"):
                r["num"] = rec["num"]
                r["detected"] = rec["num"]
                break
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
    """Drop front matter before the first numbered 回; number rows by position."""
    first = next((i for i, r in enumerate(runs) if r["num"]), 0)
    runs = runs[first:]
    for i, r in enumerate(runs):
        r["page_start"], r["page_end"] = r["start"], r["end"]
        r["ord"] = i
        r["level"] = 2
    for i, r in enumerate(runs):
        r["page_end"] = runs[i + 1]["start"] - 1 if i + 1 < len(runs) else r["end"]
        r["pages"] = r["page_end"] - r["page_start"] + 1
        r["printed"] = r["num"]
        r["num"] = i + 1
        r["title_text"] = ("附录 " + r["title"]) if r.get("appendix") else r["title"]
    return runs


def split_books(runs):
    """A new novel starts where the printed 回 number falls back to the top."""
    books, cur, last = [], [], 0
    for r in runs:
        # The printed number resets to 1 at a new novel; the counted number does
        # not, so the split must look at what the header actually said.
        pr = r.get("detected") or 0
        if cur and pr and pr <= 3 and last >= 10:
            books.append(cur)
            cur = []
        cur.append(r)
        last = pr or last
    if cur:
        books.append(cur)
    return books


def build(records, threshold=0.55, min_pages=4, names=None):
    pages = parse_records(records)
    runs = segment(pages, threshold)
    runs = merge_short(runs, min_pages)
    runs = mark_appendix(runs, pages)
    runs = trim(number(runs, pages))
    books = split_books(runs)
    names = names or {}
    for bi, rows in enumerate(books):
        for r in rows:
            r["book"] = bi + 1
            r["book_name"] = names.get(bi + 1, "第%d部" % (bi + 1))
    return books
