import json
import os
import re
import difflib
import xml.etree.ElementTree as ET

import pymupdf

BASE = r"D:\Guo-Code\socratic-tutor\eval\p1\bakeoff"
PDF = r"D:\Guo-Code\loeb\latin_L063N_vergil.pdf"
XML = r"D:\Guo-Code\socratic-tutor\eval\p0\gold\aeneid.xml"
OUT = os.path.join(BASE, "gold", "K6")


def norm(s):
    return re.sub(r"[^a-z]", "", (s or "").lower())


def xml_lines():
    root = ET.parse(XML).getroot()
    rows = []
    for div in root.iter():
        if not (div.tag.endswith("}div") or div.tag == "div"):
            continue
        if div.attrib.get("subtype") != "book":
            continue
        book = div.attrib.get("n", "?")
        for el in div.iter():
            if not (el.tag.endswith("}l") or el.tag == "l"):
                continue
            n = el.attrib.get("n")
            txt = "".join(el.itertext()).strip()
            m = re.match(r"(\d+)", n or "")
            if m and txt:
                rows.append((book, int(m.group(1)), txt))
    return rows


def page_first_line(text):
    for line in text.splitlines():
        s = line.strip()
        if len(s) < 12:
            continue
        if re.fullmatch(r"[\d\s\W]+", s):
            continue
        if s.upper().startswith(("LIBER", "BOOK", "AENEID")):
            continue
        return s
    return ""


def main():
    os.makedirs(OUT, exist_ok=True)
    lines = xml_lines()
    doc = pymupdf.open(PDF)
    last = 0
    report = []
    for p in range(251, 274, 2):
        text = doc.load_page(p - 1).get_text()
        first = page_first_line(text)
        target = norm(first)
        lo = max(0, last - 20)
        hi = min(len(lines), last + 40)
        best, best_r = lo, 0.0
        for i in range(lo, hi):
            r = difflib.SequenceMatcher(None, target, norm(lines[i][2])).ratio()
            if r > best_r:
                best, best_r = i, r
        page_norm = len(norm(text))
        page_lines = len([ln for ln in text.splitlines() if len(norm(ln)) >= 12])
        out = []
        total = 0
        for i in range(best, min(len(lines), best + 60)):
            out.append(lines[i][2])
            total += len(norm(lines[i][2]))
            if len(out) >= page_lines or total >= page_norm * 1.15:
                break
        gold = "\n".join(out)
        open(os.path.join(OUT, f"p{p}.txt"), "w", encoding="utf-8").write(gold)
        last = best + len(out)
        report.append({"page": p, "book": lines[best][0], "start_line": lines[best][1],
                       "end_book": lines[last - 1][0], "end_line": lines[last - 1][1],
                       "match": round(best_r, 3),
                       "gold_chars": len(norm(gold))})
        print(report[-1], flush=True)
    doc.close()
    json.dump(report, open(os.path.join(BASE, "k6-perseus-map.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
