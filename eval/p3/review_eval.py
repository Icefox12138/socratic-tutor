"""P3 review v1 eval: mutation-labelled claims.

Each base answer is a correct answer to a question. For every error class we
inject the mutation that a student would plausibly make, and the review must
recover (a) that the claim is wrong and (b) which class it is, from the claim
and the recorded expected answer alone.

  python eval/p3/review_eval.py            # full grid
  python eval/p3/review_eval.py --show     # print every case
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "sidecar"))
from app import review  # noqa: E402

# Each base is a correct answer plus the mutations a student would plausibly
# make. The review sees only (claim, expected) - the class names are the gold.
BASES = [
    {"question": "求 x^3 的导数", "expected": "3*x**2", "correct": "3*x**2",
     "muts": {"sign": "-3*x**2", "arithmetic": "4*x**2",
              "formula": "x**3", "misread": "3*y**2"}},
    {"question": "求 x^2 的积分", "expected": "x**3/3", "correct": "x**3/3",
     "muts": {"sign": "-x**3/3", "arithmetic": "x**3/4",
              "formula": "x**2/3", "misread": "y**3/3"}},
    {"question": "解方程 x^2 - 4 = 0", "expected": "[2, -2]", "correct": "[2, -2]",
     "muts": {"condition": "[2]", "formula": "[2, -2, 3]"}},
    {"question": "lim_{x->0} sin(x)/x", "expected": "1", "correct": "1",
     "muts": {"sign": "-1", "unit": "1000"}},
    {"question": "化简 (x^2-1)/(x-1)", "expected": "x + 1", "correct": "x + 1",
     "muts": {"arithmetic": "x + 2", "incomplete": "1", "misread": "y + 1"}},
    {"question": "展开 (x+1)^2", "expected": "x**2 + 2*x + 1", "correct": "x**2 + 2*x + 1",
     "muts": {"sign": "-(x**2 + 2*x + 1)", "formula": "x**3 + 2*x + 1",
              "incomplete": "x**2 + 2*x"}},
    {"question": "1000 m 等于多少 km", "expected": "1", "correct": "1",
     "muts": {"unit": "1000"}},
    {"question": "求 sin(x) 的导数", "expected": "cos(x)", "correct": "cos(x)",
     "muts": {"sign": "-cos(x)", "formula": "sin(x)", "misread": "cos(y)"}},
]


# Written after the tuned grid was frozen, with different expressions and
# notation, and run once: this is the number that counts as held-out.
HELDOUT = [
    {"question": "求 1/x 的导数", "expected": "-1/x**2", "correct": "-1/x**2",
     "muts": {"sign": "1/x**2", "formula": "-2/x**3"}},
    {"question": "解 2x + 3 = 7", "expected": "[2]", "correct": "[2]",
     "muts": {"formula": "[2, -2]"}},
    {"question": "求 cos(x) 的积分", "expected": "sin(x)", "correct": "sin(x)",
     "muts": {"sign": "-sin(x)", "formula": "cos(x)", "misread": "sin(t)"}},
    {"question": "化简 x + x", "expected": "2*x", "correct": "2*x",
     "muts": {"arithmetic": "3*x", "misread": "2*y", "incomplete": "x"}},
    {"question": "100 cm 等于多少 m", "expected": "1", "correct": "1",
     "muts": {"unit": "100"}},
    {"question": "求 e^x 的导数", "expected": "e**x", "correct": "e**x",
     "muts": {"sign": "-e**x", "formula": "x*e**x"}},
    {"question": "解 x^2 = 9", "expected": "[3, -3]", "correct": "[3, -3]",
     "muts": {"condition": "[3]"}},
    {"question": "计算 2^10", "expected": "1024", "correct": "1024",
     "muts": {"arithmetic": "512", "unit": "1024000"}},
]


def build_cases(split="tuned"):
    bases = BASES if split == "tuned" else HELDOUT
    cases = []
    for base in bases:
        cases.append({"question": base["question"], "expected": base["expected"],
                      "claim": base["correct"], "want_verdict": "correct",
                      "want_error": None, "class": "baseline"})
        for cls, claim in base["muts"].items():
            if claim == base["correct"]:
                continue
            cases.append({"question": base["question"], "expected": base["expected"],
                          "claim": claim, "want_verdict": "incorrect",
                          "want_error": cls, "class": cls})
    return cases




    cases = []
    for base in BASES:
        cases.append({"question": base["question"], "expected": base["expected"],
                      "claim": base["correct"], "want_verdict": "correct",
                      "want_error": None, "class": "baseline"})
        for cls, claim in base["muts"].items():
            if claim == base["correct"]:
                continue
            cases.append({"question": base["question"], "expected": base["expected"],
                          "claim": claim, "want_verdict": "incorrect",
                          "want_error": cls, "class": cls})
    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--split", default="tuned", choices=["tuned", "holdout"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    if args.out is None:
        args.out = os.path.join(HERE, "review-results.json" if args.split == "tuned"
                                else "review-holdout.json")

    cases = build_cases(args.split)
    rows = []
    for c in cases:
        verdict, evidence = review.judge(c["claim"], c["expected"])
        err = review.classify(c["claim"], c["expected"]) if verdict == "incorrect" else None
        rows.append({**c, "got_verdict": verdict, "got_error": err, "evidence": evidence,
                     "verdict_ok": verdict == c["want_verdict"],
                     "class_ok": (c["want_error"] is None and err is None) or err == c["want_error"]})
        if args.show:
            print("%-10s %-34s %-16s -> %-12s %-11s %s" % (
                c["class"], c["expected"][:34], c["claim"][:16], verdict, err,
                "ok" if rows[-1]["class_ok"] else "MISS"))

    wrong = [r for r in rows if r["want_verdict"] == "incorrect"]
    right = [r for r in rows if r["want_verdict"] == "correct"]
    undetermined = [r for r in rows if r["got_verdict"] == "undetermined"]
    class_ok = sum(1 for r in wrong if r["class_ok"])
    metrics = {
        "n": len(rows),
        "n_wrong": len(wrong),
        "n_right": len(right),
        "verdict_accuracy": round(sum(1 for r in rows if r["verdict_ok"]) / len(rows), 4),
        "wrong_detected": round(sum(1 for r in wrong if r["got_verdict"] == "incorrect") / len(wrong), 4),
        "correct_accepted": round(sum(1 for r in right if r["got_verdict"] == "correct") / len(right), 4),
        "class_accuracy": round(class_ok / len(wrong), 4),
        "undetermined_rate": round(len(undetermined) / len(rows), 4),
        "per_class": {},
    }
    for cls in sorted({r["class"] for r in wrong}):
        sub = [r for r in wrong if r["class"] == cls]
        metrics["per_class"][cls] = {
            "n": len(sub),
            "ok": sum(1 for r in sub if r["class_ok"]),
            "hits": round(sum(1 for r in sub if r["class_ok"]) / len(sub), 3),
        }
    out = {"cases": rows, "metrics": metrics}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(metrics, ensure_ascii=False, indent=1))
    print("-> " + args.out)
    return 0 if metrics["class_accuracy"] >= 0.8 and metrics["undetermined_rate"] < 0.2 else 1


if __name__ == "__main__":
    sys.exit(main())
