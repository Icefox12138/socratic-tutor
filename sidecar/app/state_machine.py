"""Deterministic teaching state machine (P2-1 skeleton).

The LLM only writes wording; which phase comes next is computed here.
"""
from dataclasses import asdict, dataclass, field


class InvalidTransition(ValueError):
    pass


HINTS = {0: "L0 重述问题", 1: "L1 指向概念/章节", 2: "L2 类比/例子",
         3: "L3 子步骤", 4: "L4 近乎完整推导", 5: "L5 答案+讲解"}

PHASES = ["ALIGN", "DIAGNOSE", "PLAN", "ASK", "WAIT", "EVALUATE",
          "HINT", "ADVANCE", "TRANSFER", "SUMMARY"]


@dataclass
class State:
    session_id: str
    phase: str = "ALIGN"
    goal: str = ""
    concept: str = ""
    question: str = ""
    rubric: str = ""
    expected: str = ""
    lang: str = "zh"
    hint_level: int = 0
    attempts: int = 0
    correct_streak: int = 0
    wrong_streak: int = 0
    frustration: int = 0
    explicit_ask: bool = False
    revealed: bool = False
    diagnostics: int = 0
    transfer_done: bool = False
    mastery: float = 0.3
    history: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def may_reveal(s: State) -> bool:
    if s.hint_level >= 5 and s.explicit_ask:
        return True
    if s.hint_level >= 3 and s.attempts >= 2:
        return True
    if s.frustration >= 2 and s.attempts >= 1:
        return True
    return False


def _action(s: State, kind: str, instruction: str):
    return {"kind": kind, "phase": s.phase, "hint": HINTS.get(s.hint_level, ""),
            "instruction": instruction}


def _advance_or_ask(s: State):
    if s.correct_streak >= 2 and not s.transfer_done:
        s.phase = "TRANSFER"
        s.transfer_done = True
        return _action(s, "transfer", "连续两次通过：出迁移题（换情境），只问一个问题。")
    s.phase = "ASK"
    return _action(s, "ask", "换概念/加难度，只问一个问题。")


def step(s: State, event: str, result: str | None = None,
         text: str | None = None, rubric: str | None = None,
         expected: str | None = None) -> dict:
    """Apply one event. Returns {state, action, summary, allowed_events}."""
    if event == "stop":
        s.phase = "SUMMARY"
        return {"state": s.to_dict(), "action": _action(s, "summary", "停止学习：做小结并邀约复盘。"),
                "summary": summary(s), "allowed_events": []}
    if s.phase == "SUMMARY":
        raise InvalidTransition("SUMMARY is terminal; call init for a new session")

    if event == "confirm_goal" and s.phase == "ALIGN":
        s.phase = "DIAGNOSE"
        return _emit(s, "diagnose", "用 2–3 个诊断问题确认起点，不要讲课。")

    if event == "diagnosed" and s.phase == "DIAGNOSE":
        s.diagnostics += 1
        s.phase = "PLAN"
        return _emit(s, "plan", "选一个概念、定提示预算。")

    if event == "plan_ready" and s.phase == "PLAN":
        s.phase = "ASK"
        return _emit(s, "ask", "只问一个问题，等待回答。")

    if event == "asked" and s.phase in ("ASK", "HINT"):
        if text:
            s.question = text
        if rubric:
            s.rubric = rubric
        if expected:
            s.expected = expected
        s.phase = "WAIT"
        return _emit(s, "wait", "等待学生回答；不要自问自答。")

    if event == "answer" and s.phase in ("WAIT", "HINT", "TRANSFER"):
        if result not in ("correct", "partial", "wrong"):
            raise InvalidTransition("result must be correct/partial/wrong")
        return _on_answer(s, result, text)

    if event == "hint_request" and s.phase in ("WAIT", "HINT", "ASK"):
        s.explicit_ask = True
        if may_reveal(s):
            s.hint_level = 5
            s.revealed = True
            s.phase = "HINT"
            return _emit(s, "reveal", "给答案+讲解，并要求学生用自己的话回讲关键一步。")
        s.hint_level = min(5, s.hint_level + 1)
        s.phase = "HINT"
        return _emit(s, "hint", f"升到 {HINTS[s.hint_level]}；不得给最终答案。")

    if event == "next" and s.phase == "ADVANCE":
        a = _advance_or_ask(s)
        return {"state": s.to_dict(), "action": a, "summary": summary(s),
                "allowed_events": allowed(s)}

    if event == "transfer_done" and s.phase == "TRANSFER":
        s.phase = "SUMMARY"
        return _emit(s, "summary", "迁移完成：小结并邀约复盘。")

    raise InvalidTransition(f"event {event!r} not allowed in {s.phase}")


def _on_answer(s: State, result: str, text: str | None = None):
    s.attempts += 1
    prev = s.phase
    s.phase = "EVALUATE"
    entry = {"event": "answer", "result": result, "prev": prev}
    if text:
        # Kept for the P3 review: the student's own words are the evidence a
        # review is allowed to reason about.
        entry["text"] = str(text)[:4000]
    s.history.append(entry)
    if result == "correct":
        s.correct_streak += 1
        s.wrong_streak = 0
        s.hint_level = 0
        s.phase = "ADVANCE"
        return _emit(s, "advance", "判定通过：确认关键点，准备换概念/加难度。")
    s.correct_streak = 0
    s.wrong_streak += 1
    if result == "wrong":
        s.frustration = min(3, s.frustration + 1)
    s.hint_level = min(5, s.hint_level + 1)
    s.phase = "HINT"
    if s.hint_level >= 5 and s.explicit_ask:
        s.revealed = True
        return _emit(s, "reveal", "已到 L5：给答案+讲解，并要求回讲。")
    return _emit(s, "hint", f"判定不足，升到 {HINTS[s.hint_level]}；不得给最终答案。")


def _emit(s: State, kind: str, instruction: str):
    return {"state": s.to_dict(), "action": _action(s, kind, instruction),
            "summary": summary(s), "allowed_events": allowed(s)}


def allowed(s: State):
    table = {
        "ALIGN": ["confirm_goal", "stop"],
        "DIAGNOSE": ["diagnosed", "stop"],
        "PLAN": ["plan_ready", "stop"],
        "ASK": ["asked", "hint_request", "stop"],
        "WAIT": ["answer", "hint_request", "stop"],
        "HINT": ["answer", "asked", "hint_request", "stop"],
        "ADVANCE": ["next", "stop"],
        "TRANSFER": ["answer", "transfer_done", "stop"],
        "SUMMARY": [],
    }
    return table.get(s.phase, [])


def summary(s: State) -> str:
    return (f"【状态摘要】阶段={s.phase}；概念={s.concept or '未设定'}；"
            f"掌握={mastery_label(s.mastery)}；提示={HINTS.get(s.hint_level, '')}；"
            f"尝试={s.attempts}；连对={s.correct_streak}；"
            f"已揭示={'是' if s.revealed else '否'}。")


def mastery_label(p: float) -> str:
    if p < 0.35:
        return "未掌握"
    if p <= 0.75:
        return "在学"
    return "已掌握"


def init(session_id: str, goal: str = "", concept: str = "", lang: str = "zh") -> State:
    return State(session_id=session_id, goal=goal, concept=concept, lang=lang)
