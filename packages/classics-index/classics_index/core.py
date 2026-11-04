"""Chapter-index core: 卷 / 篇 / 回 from OCR of a scanned book's running headers.

Pure functions only - no storage, no OCR, no I/O beyond dicts and lists, so the
same code can back a CLI, a service, or a notebook.

Pipeline it supports:

  1. per-page header OCR  -> {page: [{"text": ...}], ...}
     volume_of + clean_volumes + build_from_volumes  -> level-1 卷 rows
  2. title-band OCR       -> 篇 candidates
     bind_to_volume + pian_sequence + merge_pian      -> level-2 篇 rows
  3. 章回小说 header OCR   -> 回 segments (see hui.py)

Extracted from the sidecar's app/toc.py; the sidecar keeps a superset with
SQLite storage, so changes here should be mirrored there (or the sidecar should
depend on this package).
"""
import json
import re
import sqlite3


CN_DIGITS = {"〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
             "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}

# "史記卷二十七", "卷二十七", "史记卷 12"
VOL = re.compile(r"卷\s*([0-9]{1,3}|[〇零一二三四五六七八九十百千]{1,6})")
PIAN = re.compile(r"(本紀|本纪|紀|纪|世家|列傳|列传|傳|传|書|书|表|志)\s*第\s*([〇零一二三四五六七八九十百]{1,4})")


def cn2int(text):
    """二十七 -> 27; 12 -> 12."""
    if not text:
        return None
    if text.isdigit():
        return int(text)
    total, cur = 0, 0
    for ch in text:
        if ch in CN_DIGITS:
            cur = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            total += (cur or 1) * CN_UNITS[ch]
            cur = 0
        else:
            return None
    return total + cur


def volume_of(lines):
    """The volume number a page belongs to, from its running header."""
    for line in lines:
        m = VOL.search(str(line.get("text") or ""))
        if m:
            n = cn2int(m.group(1))
            if n:
                return n
    return None


def build(pages):
    """pages: {page_no: [ {text, box, score}, ... ]} -> chapter list."""
    return build_from_volumes({p: volume_of(lines) for p, lines in pages.items()})


def clean_volumes(vols, min_run=5):
    """Drop volume labels that do not survive as a run of pages.

    Front matter (目录) also names volumes, and those names appear in OCR of
    the same header strip. A real 卷 spans many consecutive pages, so a label
    that shows up on one or two pages is noise, not a chapter boundary.
    """
    runs = []
    for pno in sorted(vols):
        vol = vols[pno]
        if vol is None:
            continue
        if runs and runs[-1]["volume"] == vol and pno - runs[-1]["last"] <= 2:
            runs[-1]["last"] = pno
            runs[-1]["pages"] += 1
        else:
            runs.append({"volume": vol, "first": pno, "last": pno, "pages": 1})
    kept = [r for r in runs if r["pages"] >= min_run]
    out = {}
    for r in kept:
        for p in range(r["first"], r["last"] + 1):
            out[p] = r["volume"]
    return out


def build_from_volumes(vols):
    """vols: {page_no: volume|None} -> chapter list with contiguous page ranges."""
    chapters = []
    for pno in sorted(vols):
        vol = vols[pno]
        if vol is None:
            continue
        if not chapters or chapters[-1]["volume"] != vol:
            chapters.append({"volume": vol, "page_start": pno, "title": "卷%d" % vol})
    for i, ch in enumerate(chapters):
        ch["page_end"] = (chapters[i + 1]["page_start"] - 1
                          if i + 1 < len(chapters) else max(vols or {1: None}))
        ch["ord"] = i
        ch["level"] = 1
        ch["pages"] = ch["page_end"] - ch["page_start"] + 1
    return chapters


def enrich(chapters, pages):
    """Append a 篇 name to a volume title when its first page carries one."""
    for ch in chapters:
        for line in pages.get(ch["page_start"], []):
            m = PIAN.search(str(line.get("text") or ""))
            if m:
                ch["title"] = "卷%d %s第%s" % (ch["volume"], m.group(1), m.group(2))
                break
    return chapters


def bind_to_volume(page, chapters, slack=6):
    """Which 卷 does a candidate title page open?

    Preference order: a chapter that contains the page; otherwise the chapter
    that starts within slack pages after it (the title page can sit just
    before the first running header). Front matter stays unbound.
    """
    # A 篇 opens the 卷 whose start it sits closest to: the title page can sit a
    # few leaves before the first running header (the header pass misses early
    # leaves), so containment alone would bind it to the previous 卷.
    near = [ch for ch in chapters
            if ch.get("volume") and abs(ch["page_start"] - page) <= slack]
    if near:
        return min(near, key=lambda ch: abs(ch["page_start"] - page))["volume"]
    for ch in chapters:
        if ch.get("volume") and ch["page_start"] <= page <= ch["page_end"]:
            return ch["volume"]
    return None


def pian_sequence(cands, min_gap=3):
    """Keep a strictly increasing run of 第X titles; drop list-page noise.

    cands: [(page, text)] for one 卷. 目录 pages also spell out 篇 names, so a
    candidate only survives when its 第X is greater than the previous kept one
    and it is at least min_gap pages away.
    """
    import re as _re

    kept = []
    last_num = 0
    last_page = -10
    for page, text in sorted(cands):
        m = _re.search(r"第\s*([〇零一二三四五六七八九十百]{1,4})", text)
        num = cn2int(m.group(1)) if m else None
        if not num:
            continue
        if num <= last_num or page - last_page < min_gap:
            continue
        kept.append((page, text))
        last_num, last_page = num, page
    return kept


def enrich(chapters, pages):
    """Append a 篇 name to a volume title when its first page carries one."""
    for ch in chapters:
        for line in pages.get(ch.get("page_start"), []):
            m = PIAN.search(str(line.get("text") or ""))
            if m:
                ch["title"] = "卷%s %s第%s" % (ch.get("volume"), m.group(1), m.group(2))
                break
    return chapters


def merge_pian(chapters, hits, total=None):
    """Fold 篇 title hits into the 卷 rows.

    chapters: level-1 rows from the volume index (may include 卷首/卷末).
    hits:     {volume: (page, title)} for each 卷 where a 篇 title was found.
    Returns rows ordered 卷 -> its 篇, with contiguous 卷 ranges; a 卷 start
    moves earlier when its 篇 title page precedes the running-header page.
    """
    rows = []
    for ch in chapters:
        ch = dict(ch)
        ch["level"] = 1
        hit = hits.get(ch.get("volume"))
        if hit and isinstance(hit, tuple):
            hit = [hit]                      # one 篇 per 卷 is the common case
        items = sorted(hit or [], key=lambda x: x[0])
        if items:
            ch["page_start"] = min(ch["page_start"], items[0][0])
            ch["title"] = "卷%d %s" % (ch["volume"], items[0][1])
        rows.append(ch)
        for page, title in items:
            rows.append({"level": 2, "title": title, "page_start": page,
                         "page_end": page, "volume": ch["volume"],
                         "parent": ch["volume"]})
    total = total or max(r["page_end"] for r in chapters)
    level1 = [r for r in rows if r["level"] == 1]
    level1.sort(key=lambda r: r["page_start"])
    for i, r in enumerate(level1):
        r["page_end"] = level1[i + 1]["page_start"] - 1 if i + 1 < len(level1) else total
    for vol in {r.get("volume") for r in rows if r["level"] == 2}:
        parent = next(x for x in level1 if x.get("volume") == vol)
        pian = sorted((r for r in rows if r["level"] == 2 and r["volume"] == vol),
                      key=lambda r: r["page_start"])
        for i, r in enumerate(pian):
            r["page_end"] = (pian[i + 1]["page_start"] - 1) if i + 1 < len(pian) else parent["page_end"]
            r["page_end"] = max(r["page_end"], r["page_start"])
    for i, r in enumerate(rows):
        r["ord"] = i
        r["pages"] = r["page_end"] - r["page_start"] + 1
    return rows


def at(rows, page):
    """The chapter row that contains a page (innermost wins)."""
    best = None
    for r in rows:
        if r["page_start"] <= page <= r["page_end"]:
            if best is None or (r.get("level") or 1) > (best.get("level") or 1):
                best = r
    return best


# OCR output and 点校本 titles are traditional; readers type simplified. A
# full converter is overkill, so cover the characters that actually appear in
# the chapter names of the indexed books.
_TRAD = {
    "紀": "纪", "傳": "传", "書": "书", "項": "项", "賈": "贾", "詡": "诩",
    "張": "张", "涼": "凉", "國": "国", "鮑": "鲍", "馬": "马", "鍾": "钟",
    "華": "华", "劉": "刘", "蔣": "蒋", "繇": "繇", "歆": "歆", "毓": "毓",
    "禮": "礼", "樂": "乐", "曆": "历", "曆": "历", "邊": "边", "衛": "卫",
    "權": "权", "陰": "阴", "陽": "阳", "東": "东", "車": "车", "軍": "军",
    "吳": "吴", "魯": "鲁", "齊": "齐", "鄭": "郑", "晉": "晋", "衛": "卫",
    "陳": "陈", "韓": "韩", "魏": "魏", "趙": "赵", "楚": "楚", "燕": "燕",
    "漢": "汉", "秦": "秦", "夏": "夏", "殷": "殷", "周": "周", "帝": "帝",
}


def _simp(text):
    return "".join(_TRAD.get(ch, ch) for ch in str(text or ""))


def _num_in(title, kind):
    """Pull the printed number out of a title: 卷12 / 第三回."""
    m = re.search(r"%s\s*(\d{1,4}|[〇零一二三四五六七八九十百千]{1,6})" % kind, title or "")
    return cn2int(m.group(1)) if m else None


def find(rows, query):
    """Locate a chapter by ordinal, printed number, or a title fragment.

    Accepts "3", "卷3", "第三回", "第7回", "五帝本纪", "项王".
    """
    q = str(query or "").strip()
    if not q:
        return None
    m = re.search(r"(卷|第)\s*(\d{1,4}|[〇零一二三四五六七八九十百千]{1,6})", q)
    if m:
        kind = "卷" if m.group(1) == "卷" else "第"
        num = cn2int(m.group(2))
        if num:
            hits = [r for r in rows if _num_in(r.get("title"), kind) == num]
            if hits:
                return max(hits, key=lambda r: r.get("level") or 1)
            for r in rows:
                if kind == "卷" and (r.get("level") or 1) == 1 and r.get("volume") == num:
                    return r
                if kind == "第" and r.get("ord") == num - 1:
                    return r
            return None
    if q.isdigit():
        n = int(q)
        for r in rows:
            if r.get("ord") == n:
                return r
        for r in rows:
            if r.get("ord") == n - 1:
                return r
    needle = _simp(q.replace("第", "").replace("回", "").replace("卷", "").strip())
    if needle:
        hits = [r for r in rows if needle in _simp(r.get("title"))]
        if hits:
            return max(hits, key=lambda r: r.get("level") or 1)
    return None

