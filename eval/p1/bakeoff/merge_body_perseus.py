import json
import os

B = r"D:\Guo-Code\socratic-tutor\eval\p1\bakeoff"
k5 = [r for r in json.load(open(os.path.join(B, "body-scorecard-k5.json"), encoding="utf-8"))
      if r["group"] == "K5"]
k6 = json.load(open(os.path.join(B, "body-scorecard-k6-perseus.json"), encoding="utf-8"))
for r in k6:
    r["group"] = "K6"
rows = k5 + k6
json.dump(rows, open(os.path.join(B, "body-scorecard.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
lines = ["# K5/K6 正文页 OCR 对比（K5 silver；K6 Perseus）", "",
         "| 引擎 | 组 | 页数 | 平均 CER |", "|---|---|---:|---:|"]
for eng in ("rapidocr", "paddleocr", "mineru"):
    for g in ("K5", "K6"):
        sub = [r for r in rows if r["engine"] == eng and r["group"] == g and r["cer"] is not None]
        lines.append(f"| {eng} | {g} | {len(sub)} | {sum(r['cer'] for r in sub)/len(sub):.3f} |")
open(os.path.join(B, "body-scorecard.md"), "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
