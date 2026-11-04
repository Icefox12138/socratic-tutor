"""Rule-based question classifier (P2-1 skeleton).

Types follow DESIGN §12.2: clarify / hypothesis / evidence / perspective /
inference / meta. This is deterministic and intentionally small; the LLM can
override only with an explicit reason.
"""
import re

TYPES = {
    "clarify": "澄清",
    "hypothesis": "假设",
    "evidence": "证据",
    "perspective": "视角",
    "inference": "推论",
    "meta": "元问题",
}

_RULES = [
    ("meta", ("怎么知道", "凭什么", "如何判断", "为什么这样", "反思", "方法为何")),
    ("evidence", ("依据", "证据", "出处", "哪一卷", "哪一章", "哪个词", "引用", "原文")),
    ("inference", ("会怎样", "推出", "导致", "接下来", "后果")),
    ("hypothesis", ("如果", "若", "假如", "假设", "换成")),
    ("perspective", ("怎么看", "立场", "反驳", "视角", "会怎么想")),
    ("clarify", ("你说的", "指的是", "哪个", "哪一层", "什么意思")),
]


def classify(text: str) -> dict:
    text = text or ""
    q = text.count("?") + text.count("？")
    kind = "clarify"
    for k, kws in _RULES:
        if any(w in text for w in kws):
            kind = k
            break
    return {"type": kind, "label": TYPES[kind], "questions": q, "multi": q > 1}
