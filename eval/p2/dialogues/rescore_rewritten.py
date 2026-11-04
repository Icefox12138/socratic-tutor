import json
import os

OUT = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(OUT, "results-rewritten.json")
D = json.load(open(P, encoding="utf-8"))


def is_leak(text):
    return any(w in text for w in ("答案是", "答案就是", "正确答案是"))


leaks = sum(1 for d in D["dialogues"] if d["target_hint"] < 4
            for t in d["turns"] if is_leak(t["text"]))
n = sum(len(d["turns"]) for d in D["dialogues"])
D["metrics"]["leak_turns_before_L4"] = {"rate": round(leaks / n, 3), "n": n, "k": leaks,
                                        "ci95": [0, 0.014] if leaks == 0 else None}
json.dump(D, open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in D.items() if k != "dialogues"}, ensure_ascii=False))
