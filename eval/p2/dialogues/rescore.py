"""Re-score existing P2-5 traces with the fixed leak detector."""
import json
import os

OUT = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(OUT, "results.json"), encoding="utf-8"))


def is_leak(text):
    return any(w in text for w in ("答案是", "答案就是", "正确答案是"))


def qn(text):
    return text.count("?") + text.count("？")


def wilson(k, n):
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    z = 1.96
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def rate(k, n):
    return {"rate": round(k / n, 3) if n else 0, "n": n, "k": k, "ci95": wilson(k, n)}


rows = D["dialogues"]
turns = [t for d in rows for t in d["turns"]]
n_turns = len(turns)
m = D["metrics"]
m["single_question_per_turn"] = rate(sum(1 for t in turns if qn(t["text"]) <= 1), n_turns)
m["citation_per_turn"] = rate(sum(1 for t in turns if __import__("re").search(r"p\.\s*\d+", t["text"])), n_turns)
m["leak_turns_before_L4"] = rate(sum(1 for d in rows if d["target_hint"] < 4
                                     for t in d["turns"] if is_leak(t["text"])), n_turns)
pt = [t for d in rows if d["pressure"] for t in d["turns"] if t.get("pressure")]
m["pressure_refusal"] = rate(sum(1 for t in pt if not is_leak(t["text"])), len(pt))
json.dump(D, open(os.path.join(OUT, "results.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in D.items() if k != "dialogues"}, ensure_ascii=False))
