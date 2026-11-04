import json
import os
import re

BASE = r"D:\Guo-Code\socratic-tutor\eval\p1\bakeoff"
OUT = os.path.join(BASE, "out")
MAN = r"D:\Guo-Code\socratic-tutor\eval\p0\catalog\sample-manifest.json"
GREEK = re.compile("[\u0370-\u03ff\u1f00-\u1fff]")
POLY = re.compile("[\u1f00-\u1fff]")
CJK = re.compile("[\u3400-\u9fff]")
LATIN = re.compile(r"[A-Za-z]")

man = {s["id"]: s for s in json.load(open(MAN, encoding="utf-8"))["samples"]}
rows = []
for eng in ("rapidocr", "paddleocr", "mineru"):
    for g in ("C1", "B2", "K5", "K6", "A2"):
        s = man[g]
        start, end = s["window"]["start"], s["window"]["end"]
        step = max(1, (end - start) // 12)
        pages = list(range(start, end + 1, step))[:12]
        for p in pages:
            d = os.path.join(OUT, eng, g)
            txt = ""
            for ext in (".md", ".txt"):
                fp = os.path.join(d, f"p{p}{ext}")
                if os.path.exists(fp):
                    txt = open(fp, encoding="utf-8").read()
                    break
            rows.append({"engine": eng, "group": g, "page": p, "chars": len(txt),
                         "cjk": len(CJK.findall(txt)), "greek": len(GREEK.findall(txt)),
                         "latin": len(LATIN.findall(txt)), "poly": len(POLY.findall(txt)),
                         "ok": bool(txt)})
json.dump(rows, open(os.path.join(BASE, "scorecard-all.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
lines = ["# OCR 三引擎 60 页对比（本地）", "",
         "| 引擎 | 组 | 页数 | 平均字符 | 平均希腊 | 平均拉丁 | 平均 CJK |",
         "|---|---|---:|---:|---:|---:|---:|"]
for eng in ("rapidocr", "paddleocr", "mineru"):
    for g in ("C1", "B2", "K5", "K6", "A2"):
        sub = [r for r in rows if r["engine"] == eng and r["group"] == g and r["ok"]]
        n = len(sub)
        lines.append(f"| {eng} | {g} | {n} | {sum(r['chars'] for r in sub)/n:.0f} |"
                     f" {sum(r['greek'] for r in sub)/n:.0f} |"
                     f" {sum(r['latin'] for r in sub)/n:.0f} |"
                     f" {sum(r['cjk'] for r in sub)/n:.0f} |" if n else
                     f"| {eng} | {g} | 0 | - | - | - | - |")
lines += ["", "> CER/变音符召回需要 gold；K5/K6 公版对齐尚未生成。",
          "> OCRFlux 按用户决定推迟，未跑云。", ""]
open(os.path.join(BASE, "scorecard-all.md"), "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
