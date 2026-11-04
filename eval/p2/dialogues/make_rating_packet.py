import json
import os

D = json.load(open(r"D:\Guo-Code\socratic-tutor\eval\p2\dialogues\results-rewritten.json",
                   encoding="utf-8"))
by_id = {d["id"]: d for d in D["dialogues"]}
# 8 zh, 4 latin, 4 greek, 4 en; mixed pressure/quality/target
picks = [24, 25, 26, 33, 34, 35, 42, 43,
         12, 13, 14, 21,
         0, 1, 2, 3,
         74, 75, 76, 77]
rows = [by_id[i] for i in picks]
mapping = {}
lines = ["# P2-6 人工评分包（20 段）", "",
         "> 盲评：样本编号 R01–R20；映射见 `rating-mapping.json`（评分人不要看）。",
         "> 每维 1–5 分；5 最好。只评导师文本，不评学生。", ""]
for n, d in enumerate(rows, 1):
    rid = f"R{n:02d}"
    mapping[rid] = d["id"]
    lines += [f"## {rid}", "",
              f"- 问题：{d['question']}",
              f"- 语言：{d['lang']}；目标提示：L{d['target_hint']}；压力：{d['pressure'] or '无'}；学生回答质量：{d['quality']}",
              f"- 最终阶段：{d['final_state']['phase']}；掌握度：{d['mastery']['level'] if d.get('mastery') else 'n/a'}", ""]
    for t in d["turns"]:
        tag = f"第 {t['turn']} 回合"
        if t.get("pressure"):
            tag += f"（施压：{t['pressure']}）"
        lines += [f"**导师 {tag}**", "", t["text"], ""]
    lines += ["---", ""]
open(r"D:\Guo-Code\socratic-tutor\eval\p2\dialogues\rating-packet.md", "w", encoding="utf-8").write("\n".join(lines))
json.dump(mapping, open(r"D:\Guo-Code\socratic-tutor\eval\p2\dialogues\rating-mapping.json",
                        "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(rows))
