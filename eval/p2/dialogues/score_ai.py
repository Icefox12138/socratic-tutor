"""AI preliminary blind rating for the 20-sample packet.

NOT human scoring. Two human raters should fill human-ratings-template.csv.
"""
import csv
import json
import os
import statistics

ROOT = r"D:\Guo-Code\socratic-tutor\eval\p2\dialogues"
MAP = json.load(open(os.path.join(ROOT, "rating-mapping.json"), encoding="utf-8"))
DATA = json.load(open(os.path.join(ROOT, "results-rewritten.json"), encoding="utf-8"))
BY = {d["id"]: d for d in DATA["dialogues"]}

# scores: socratic, single, citation, no_leak, mastery
S = {
    "R01": (5, 5, 3, 5, 4, "问题链清楚；未给 locator；掌握判定偏乐观"),
    "R02": (5, 5, 5, 5, 4, "p.36 定位；学生答 partial 后降提示"),
    "R03": (4, 5, 4, 5, 4, "逐步缩小；直接给 C=Ctrl，引用不足"),
    "R04": (5, 5, 3, 5, 4, "开放式追问好；无 citation"),
    "R05": (5, 5, 5, 5, 3, "p.51 引导；学生仍 partial，未进一步诊断"),
    "R06": (4, 5, 4, 5, 3, "L5 目标但只给定义问题；p.43 引用"),
    "R07": (5, 5, 3, 5, 4, "数学追问清楚；无 citation"),
    "R08": (5, 5, 5, 5, 3, "p.687/621 引用；学生 partial 未区分误区"),
    "R09": (4, 5, 3, 5, 4, "英文追问较泛；无 citation"),
    "R10": (5, 5, 5, 5, 3, "p.26 定位；学生 partial 未诊断"),
    "R11": (5, 5, 5, 5, 3, "p.140 引导；学生 wrong 未归因"),
    "R12": (5, 5, 5, 5, 4, "p.155 子步骤；学生答对但未迁移"),
    "R13": (4, 5, 3, 5, 4, "两次都停在复述；无 citation"),
    "R14": (5, 5, 3, 5, 3, "类比好；无 citation；未处理 partial"),
    "R15": (5, 5, 2, 5, 3, "脚手架好；无 citation；学生 wrong 未归因"),
    "R16": (5, 5, 5, 5, 4, "p.34 定位；学生答对后未迁移"),
    "R17": (5, 5, 3, 5, 3, "数学追问好；无 citation"),
    "R18": (4, 5, 3, 5, 4, "问题清楚；无 citation；学生答对后未迁移"),
    "R19": (5, 5, 5, 5, 3, "p.149/151 澄清；学生 partial 未诊断"),
    "R20": (4, 5, 5, 5, 3, "p.176 引用；turn2/3 重复同一问题"),
}

rows, summary = [], {}
for rid, (soc, single, cite, leak, master, note) in S.items():
    rows.append({"id": rid, "dialogue_id": MAP[rid], "socratic": soc,
                 "single_question": single, "citation": cite,
                 "no_leak": leak, "mastery": master, "notes": note})

for key in ("socratic", "single_question", "citation", "no_leak", "mastery"):
    vals = [r[key] for r in rows]
    mean = statistics.mean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0
    ci = 2.093 * sd / (len(vals) ** 0.5) if len(vals) > 1 else 0
    summary[key] = {"mean": round(mean, 2), "sd": round(sd, 2),
                    "ci95": [round(mean - ci, 2), round(mean + ci, 2)]}

overall = [sum(r[k] for k in ("socratic", "single_question", "citation", "no_leak", "mastery")) / 5
           for r in rows]
mean = statistics.mean(overall)
sd = statistics.stdev(overall)
ci = 2.093 * sd / (len(overall) ** 0.5)
summary["overall"] = {"mean": round(mean, 2), "sd": round(sd, 2),
                      "ci95": [round(mean - ci, 2), round(mean + ci, 2)]}
summary["n"] = len(rows)
summary["rater"] = "AI preliminary (single rater, NOT human)"

with open(os.path.join(ROOT, "ratings-ai.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
json.dump(summary, open(os.path.join(ROOT, "rating-summary.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))

with open(os.path.join(ROOT, "human-ratings-template.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "rater", "socratic", "single_question", "citation", "no_leak", "mastery", "notes"])
    for rid in S:
        w.writerow([rid, "human-1", "", "", "", "", "", ""])
        w.writerow([rid, "human-2", "", "", "", "", "", ""])
