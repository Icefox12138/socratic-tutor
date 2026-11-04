import json
import os

import run_bakeoff as rb

B = r"D:\Guo-Code\socratic-tutor\eval\p1\bakeoff"
pages = list(range(251, 274, 2))
rows = []
for eng in ("rapidocr", "paddleocr", "mineru"):
    for p in pages:
        g = open(os.path.join(B, "gold", "K6", f"p{p}.txt"), encoding="utf-8").read()
        t = open(os.path.join(B, "out", eng + "-body", "K6", f"p{p}.txt"),
                 encoding="utf-8").read()
        a, b = rb.norm(g), rb.norm(t)
        rows.append({"engine": eng, "page": p, "cer": round(rb.lev(a, b) / len(a), 4)})
json.dump(rows, open(os.path.join(B, "body-scorecard-k6-perseus.json"), "w",
                     encoding="utf-8"), ensure_ascii=False, indent=1)
lines = ["# K6 拉丁：Perseus 金标", "", "| 引擎 | 页数 | 平均 CER |", "|---|---:|---:|"]
for eng in ("rapidocr", "paddleocr", "mineru"):
    sub = [r for r in rows if r["engine"] == eng]
    lines.append(f"| {eng} | {len(sub)} | {sum(r['cer'] for r in sub)/len(sub):.3f} |")
open(os.path.join(B, "body-scorecard-k6-perseus.md"), "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
