import json
import os

base = os.path.dirname(os.path.abspath(__file__))
m = json.load(open(os.path.join(base, "sample-manifest.json"), encoding="utf-8"))
lines = ["# P0 样本清单（20 本）", "",
         "| ID | 分支 | 类型 | 页数 | 窗口 | 金标页 | 文件 |",
         "|---|---|---|---:|---|---|---|"]
for s in m["samples"]:
    if "error" in s:
        lines.append(f"| {s['id']} | - | - | - | - | - | ERROR |")
        continue
    w = s["window"]
    g = ",".join(map(str, s["gold_pages"]))
    name = os.path.basename(s["path"])[:60]
    lines.append(f"| {s['id']} | {s['branch']} | {s['type']} | {s['pages']} | {w['start']}–{w['end']} | {g} | {name} |")
lines += [
    "",
    "## 说明",
    "",
    "- 深测 = 60 页 + 2–3 页人工金标；冒烟 = 30 页；参照 = 零 OCR 基线。",
    "- `K5` 对齐《申辩》开头（PDF p82）；`K6` 对齐 Aeneid I（p249）；`K7` 对齐 Conte 的 Aeneid I（p48）；`K8` 对齐 West 的 Rhapsody A（p62，TOC 1-based 63）。",
    "- 完整字段见 `sample-manifest.json`；全库清单见 `catalog.jsonl`（905 条 = 801 馆藏 + 100 Steadman + 2 Loeb + 2 Teubner）。",
    "",
]
open(os.path.join(base, "sample-manifest.md"), "w", encoding="utf-8").write("\n".join(lines))
print("ok", len(lines))
