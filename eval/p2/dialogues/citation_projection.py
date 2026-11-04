import json
import os
import re
import sys

ROOT = r"D:\Guo-Code\socratic-tutor"
sys.path.insert(0, ROOT)
from sidecar.app import critic  # noqa: E402

D = json.load(open(os.path.join(ROOT, "eval", "p2", "dialogues", "results.json"), encoding="utf-8"))
turns = [t for d in D["dialogues"] for t in d["turns"]]
CITE = re.compile(r"p\.\s*\d+|第\s*\d+\s*页")


def single(t):
    return (t.count("?") + t.count("？")) <= 1


before = sum(len(t["text"]) for t in turns)
after = 0
uncited = 0
changed = 0
removed = 0
cite_before = 0
cite_after = 0
after_uncited = 0
for t in turns:
    txt = t["text"]
    has_c = bool(CITE.search(txt))
    factual = critic._has_claim(txt)
    if factual and not has_c:
        uncited += 1
    c = critic.soften_uncited(txt, "soften")
    r = critic.rewrite_one_question(c["text"])
    after += len(r["text"])
    changed += 1 if (c["changed"] or r["changed"]) else 0
    removed += c.get("removed", 0)
    cite_before += 1 if has_c else 0
    cite_after += 1 if CITE.search(r["text"]) else 0
    if critic._has_claim(r["text"]):
        after_uncited += 1

out = {
    "turns": len(turns),
    "uncited_factual_turns": uncited,
    "changed_turns": changed,
    "removed_sentences": removed,
    "chars_before": before,
    "chars_after": after,
    "chars_delta": after - before,
    "chars_delta_pct": round((after - before) / before, 3),
    "citation_turns_before": cite_before,
    "citation_turns_after": cite_after,
    "uncited_after": after_uncited,
    "single_before": round(sum(1 for t in turns if single(t["text"])) / len(turns), 3),
    "single_after": round(sum(1 for t in turns if single(critic.rewrite_one_question(
        critic.soften_uncited(t["text"], "soften")["text"])["text"])) / len(turns), 3),
}
json.dump(out, open(os.path.join(ROOT, "eval", "p2", "dialogues", "citation-projection.json"),
                    "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
