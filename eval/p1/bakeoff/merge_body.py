import json
import os

B = r"D:\Guo-Code\socratic-tutor\eval\p1\bakeoff"
k5 = [r for r in json.load(open(os.path.join(B, "body-scorecard-k5.json"), encoding="utf-8"))
      if r["group"] == "K5"]
k6 = [r for r in json.load(open(os.path.join(B, "body-scorecard.json"), encoding="utf-8"))
      if r["group"] == "K6"]
seen = set()
rows = []
for r in k5 + k6:
    key = (r["group"], r["engine"], r["page"])
    if key not in seen:
        seen.add(key)
        rows.append(r)
json.dump(rows, open(os.path.join(B, "body-scorecard.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
lines = ["# K5/K6 正文页 OCR 对比（K5 silver；K6 Perseus）", "",
         "| 引擎 | 组 | 页数 | 平均 CER | 变音符召回 |", "|---|---|---:|---:|---:|"]
for eng in ("rapidocr", "paddleocr", "mineru"):
    for g in ("K5", "K6"):
        sub = [r for r in rows if r["engine"] == eng and r["group"] == g and r["cer"] is not None]
        n = len(sub)
        if n:
            lines.append(f"| {eng} | {g} | {n} | {sum(r['cer'] for r in sub)/n:.3f} |"
                         f" {sum(r['poly_recall'] or 0 for r in sub)/n:.3f} |")
        else:
            lines.append(f"| {eng} | {g} | 0 | - | - |")
open(os.path.join(B, "body-scorecard.md"), "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
