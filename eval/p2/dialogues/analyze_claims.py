import json
import re

D = json.load(open(r"D:\Guo-Code\socratic-tutor\eval\p2\dialogues\results.json", encoding="utf-8"))
turns = [t for d in D["dialogues"] for t in d["turns"]]
VERB = re.compile(r"(是指|表示|说明|表明|称为|叫做|等于|满足|定义|定理|公式|原文|数据|研究|根据)")
CITE = re.compile(r"p\.\s*\d+|第\s*\d+\s*页")
rows = []
for t in turns:
    if CITE.search(t["text"]):
        continue
    sents = [s for s in re.split(r"(?<=[。！？!?；;\n])", t["text"]) if s.strip()]
    claims = [s for s in sents if "?" not in s and "？" not in s and len(s.strip()) >= 20 and VERB.search(s)]
    if claims:
        rows.append((len(claims), t["text"]))
with open(r"D:\Guo-Code\socratic-tutor\eval\p2\dialogues\claims-sample.txt", "w", encoding="utf-8") as f:
    f.write(f"uncited_declarative_turns={len(rows)}\n\n")
    for n, text in rows[:20]:
        f.write(f"--- claims={n}\n{text[:400]}\n\n")
print(len(rows))
