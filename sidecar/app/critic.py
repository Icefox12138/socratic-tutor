"""Deterministic anti-pattern critic (P2-2 skeleton)."""
import re

LEAK = ("答案是", "所以答案", "最终答案", "正确选项是")
FACT = ("是指", "表示", "说明", "表明", "称为", "叫做", "等于", "满足",
        "定义为", "根据定义", "定理", "公式", "原文", "数据", "根据研究", "根据定理",
        "根据原文", "研究表明", "数据显示", "记载", "列出")
META = ("回答", "问题", "提示", "复述", "猜", "学习", "机会", "规则")
EMPTY = ("再想想", "仔细想想", "你再看看")
CITE = re.compile(r"p\.\s*\d+|第\s*\d+\s*页")


def _claim_sentence(p: str) -> bool:
    p = p.strip()
    if len(p) < 10 or "?" in p or "？" in p:
        return False
    if any(w in p for w in META):
        return False
    return any(w in p for w in FACT)


def _uncited_claims(text: str) -> list:
    return [p for p in re.split(r"(?<=[。！？!?；;\n])", text or "")
            if _claim_sentence(p) and not _has_cite(p)]


def _has_claim(text: str) -> bool:
    return bool(_uncited_claims(text))


def _has_cite(text: str) -> bool:
    return bool(CITE.search(text or ""))


def has_citation(text: str) -> bool:
    return _has_cite(text)


def soften_uncited(text: str, mode: str = "soften") -> dict:
    """Handle factual sentences without a locator.

    soften: replace each unsupported factual sentence with a disclaimer.
    mark: append a visible [uncited] note.
    off: unchanged.
    """
    t = text or ""
    if mode == "off":
        return {"text": t, "changed": False, "mode": mode, "removed": 0}
    sentences = [p for p in re.split(r"(?<=[。！？!?；;\n])", t) if p]
    factual = _uncited_claims(t)
    if not factual:
        return {"text": t, "changed": False, "mode": mode, "removed": 0}
    if mode == "mark":
        return {"text": t.rstrip() + "\n\n〔未引用：以上事实断言缺少 locator，需核验〕",
                "changed": True, "mode": mode, "removed": len(factual)}
    out = []
    for p in sentences:
        if _claim_sentence(p) and not _has_cite(p):
            out.append("这一点我尚未核验，先不下结论。")
        else:
            out.append(p)
    new = "".join(out).strip()
    return {"text": new, "changed": new != t, "mode": mode, "removed": len(factual)}


def rewrite_one_question(text: str) -> dict:
    """Keep the first question; drop later question sentences but keep hints."""
    t = text or ""
    m = re.search(r"[?？]", t)
    if not m:
        return {"text": t, "changed": False, "questions": 0}
    head = t[:m.end()].rstrip()
    rest = t[m.end():]
    parts = re.split(r"(?<=[。！？!?；;\n])", rest)
    keep = [p for p in parts if p.strip() and not re.search(r"[?？]", p)]
    out = head
    if keep:
        tail = "".join(keep).strip()
        if tail:
            sep = "\n" if "\n" in rest else (" " if tail[0].isascii() else "")
            out += sep + tail
    return {"text": out.rstrip(), "changed": out.rstrip() != t, "questions": 1}


def soften_leak(text: str, hint_level: int = 0, mode: str = "soften") -> dict:
    """Replace answer leaks before L4; L4/L5 may reveal."""
    t = text or ""
    if mode == "off" or hint_level >= 4:
        return {"text": t, "changed": False, "mode": mode, "removed": 0}
    parts = [p for p in re.split(r"(?<=[。！？!?；;\n])", t) if p]
    leaked = [p for p in parts if any(w in p for w in LEAK)]
    if not leaked:
        return {"text": t, "changed": False, "mode": mode, "removed": 0}
    if mode == "mark":
        return {"text": t.rstrip() + "\n\n〔未揭示：L4 前不给最终答案〕",
                "changed": True, "mode": mode, "removed": len(leaked)}
    out = [("这一步先不揭示最终答案；你先说说卡在哪一步？"
            if any(w in p for w in LEAK) else p) for p in parts]
    new = "".join(out).strip()
    return {"text": new, "changed": new != t, "mode": mode, "removed": len(leaked)}


def check(text: str, hint_level: int = 0, has_citation: bool = False) -> dict:
    t = text or ""
    q = t.count("?") + t.count("？")
    flags = []
    if 1 <= hint_level <= 3 and (len(t.strip()) < 15 or any(w in t for w in EMPTY)):
        flags.append("empty_hint")
    if q > 1:
        flags.append("multi_question")
    if ("答案：" in t or "答：" in t) and q:
        flags.append("self_answered")
    if hint_level < 4 and any(w in t for w in LEAK):
        flags.append("leak")
    if not (has_citation or _has_cite(t)) and _has_claim(t):
        flags.append("uncited_claim")
    critical = [f for f in flags if f in ("leak", "self_answered", "multi_question")]
    action = "rewrite" if critical else ("cite_or_soften" if "uncited_claim" in flags else "pass")
    return {
        "ok": not critical,
        "flags": flags,
        "critical": critical,
        "action": action,
        "questions": q,
        "rewrite": rewrite_one_question(t) if "multi_question" in flags else None,
        "citation_rewrite": soften_uncited(t) if "uncited_claim" in flags else None,
    }
