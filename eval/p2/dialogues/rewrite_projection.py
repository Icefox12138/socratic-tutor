import json
import os
import sys

ROOT = r"D:\Guo-Code\socratic-tutor"
sys.path.insert(0, ROOT)
from sidecar.app import critic  # noqa: E402

D = json.load(open(os.path.join(ROOT, "eval", "p2", "dialogues", "results.json"), encoding="utf-8"))
turns = [t for d in D["dialogues"] for t in d["turns"]]
before = sum(1 for t in turns if (t["text"].count("?") + t["text"].count("？")) <= 1)
after = 0
dropped = 0
changed = 0
for t in turns:
    r = critic.rewrite_one_question(t["text"])
    if r["changed"]:
        changed += 1
        dropped += len(t["text"]) - len(r["text"])
    if (r["text"].count("?") + r["text"].count("？")) <= 1:
        after += 1
out = {
    "turns": len(turns),
    "single_before": round(before / len(turns), 3),
    "single_after_rewrite": round(after / len(turns), 3),
    "changed_turns": changed,
    "avg_chars_dropped": round(dropped / changed, 1) if changed else 0,
}
json.dump(out, open(os.path.join(ROOT, "eval", "p2", "dialogues", "rewrite-projection.json"),
                    "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
