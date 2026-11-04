import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pymupdf
import run_bakeoff as rb

BASE = r"D:\Guo-Code\socratic-tutor\eval\p1\bakeoff"
GOLD = os.path.join(BASE, "gold")
OUT = os.path.join(BASE, "out")
MAN = r"D:\Guo-Code\socratic-tutor\eval\p0\catalog\sample-manifest.json"
GREEK = re.compile("[\u0370-\u03ff\u1f00-\u1fff]")
POLY = re.compile("[\u1f00-\u1fff]")

PAGES = {
    "K5": [],
    "K6": list(range(251, 274, 2)),
}


def gold_text(pdf, page):
    d = pymupdf.open(pdf)
    t = d.load_page(page - 1).get_text()
    d.close()
    lines = [ln for ln in t.splitlines()
             if "Digitized" not in ln and "Google" not in ln]
    return "\n".join(lines).strip()


def main():
    man = {s["id"]: s for s in json.load(open(MAN, encoding="utf-8"))["samples"]}
    rows = []
    for g, pages in PAGES.items():
        os.makedirs(os.path.join(GOLD, g), exist_ok=True)
        for p in pages:
            gt = gold_text(man[g]["path"], p)
            open(os.path.join(GOLD, g, f"p{p}.txt"), "w", encoding="utf-8").write(gt)
            img = rb.page_png(man[g]["path"], p, 200)
            for eng in ("rapidocr", "paddleocr", "mineru"):
                t0 = time.perf_counter()
                try:
                    if eng == "rapidocr":
                        text = rb.run_rapidocr(img)
                    elif eng == "paddleocr":
                        text = rb.run_paddleocr(img)
                    else:
                        text = rb.run_mineru(man[g]["path"], p, os.path.join(OUT, "mineru-body", g))
                    err = ""
                except Exception as e:
                    text, err = "", str(e)[:160]
                ms = (time.perf_counter() - t0) * 1000
                a, b = rb.norm(gt), rb.norm(text)
                cer = round(rb.lev(a, b) / len(a), 4) if a else None
                gr = len(POLY.findall(gt))
                pr = round(len(POLY.findall(text)) / gr, 3) if gr else None
                rows.append({"group": g, "page": p, "engine": eng, "chars": len(text),
                             "gold_chars": len(a), "ms": round(ms, 1), "cer": cer,
                             "poly_recall": pr, "error": err})
                sd = os.path.join(OUT, eng + "-body", g)
                os.makedirs(sd, exist_ok=True)
                open(os.path.join(sd, f"p{p}.txt"), "w", encoding="utf-8").write(text)
                print(g, p, eng, len(text), cer, pr, flush=True)
    json.dump(rows, open(os.path.join(BASE, "body-scorecard.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    lines = ["# K5/K6 正文页 OCR 对比（silver gold = PDF 文本层）", "",
             "| 引擎 | 组 | 页数 | 平均 CER | 平均变音符召回 |", "|---|---|---:|---:|---:|"]
    for eng in ("rapidocr", "paddleocr", "mineru"):
        for g in ("K5", "K6"):
            sub = [r for r in rows if r["engine"] == eng and r["group"] == g and r["cer"] is not None]
            n = len(sub)
            lines.append(f"| {eng} | {g} | {n} | {sum(r['cer'] for r in sub)/n:.3f} |"
                         f" {sum(r['poly_recall'] or 0 for r in sub)/n:.3f} |" if n else
                         f"| {eng} | {g} | 0 | - | - |")
    open(os.path.join(BASE, "body-scorecard.md"), "w", encoding="utf-8").write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
