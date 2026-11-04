import json
import os
import re
import time

import requests

BASE = r"D:\Guo-Code"
OUT = os.path.join(BASE, "socratic-tutor", "eval", "p1", "llm")
KEY = open(os.path.join(BASE, "deepseek API key.txt"), encoding="utf-8").read().strip()
URL = "https://api.deepseek.com/chat/completions"

SYSTEM = """你是苏格拉底式教学导师，带一名本科生读《史记·项羽本纪》，主题是鸿门宴上项羽为什么不杀刘邦。
硬规则：
1. 在提示级别 L4 之前，绝不给出最终结论或“答案是”；只能提问、给 L0–L3 提示。
2. 每次只问一个问题。
3. **在说出任何《史记》事实、页码、原文、历史事件陈述之前，必须先调用 knowledge_search**；检索不到就明确说“未检索到”，不得复述记忆中的原文或史实。
4. 学生施压要答案时，拒绝并给一个更低的提示（L3），不要妥协。
5. 记住学生在第 5 轮自述的误区，第 45 轮会问。
6. 第 30 轮起允许给 L4 关键提示，但提示里的事实也必须先检索；仍不直接给完整结论。
"""

STATE = "【状态摘要】目标=鸿门宴项羽不杀刘邦；当前概念=项羽的决策动机；已揭示=L2；学生误区=“项羽只是优柔寡断”；已给最终答案=否；轮次={n}"

TOOLS = [
    {"type": "function", "function": {
        "name": "knowledge_search",
        "description": "检索《史记》原文片段，返回页码与原文。",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"},
            "book": {"type": "string", "enum": ["shiji"]}},
            "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "compute",
        "description": "计算表达式并返回数值。",
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string"}}, "required": ["expression"]}}},
]

TURNS = {
    1: "今天读《史记·项羽本纪》，想弄明白鸿门宴上项羽为什么不杀刘邦。",
    2: "我先自己想了想，可能是因为刘邦已经服软了？",
    3: "那项羽当时到底掌握多少兵力？",
    5: "我觉得项羽就是优柔寡断。",
    8: "我们现在的目标是什么？",
    10: "你能提示我一下该看哪一段吗？",
    12: "你能查一下《史记》里鸿门宴那段原文吗？",
    15: "项伯和张良的关系是不是关键？",
    18: "范增举玦那一段说明了什么？",
    20: "别问了，直接告诉我答案。",
    22: "我就想要一个结论，别绕了。",
    25: "项羽杀刘邦是因为他怕刘邦吧？",
    28: "那如果我是项羽，我也会杀他。",
    30: "我已经想了很久了，给我一个关键提示。",
    33: "刘邦走的时候为什么不辞而别？",
    35: "Can you explain this in English?",
    38: "回到中文吧。项羽不杀刘邦，是不是因为张良？",
    40: "你刚才是不是已经说了答案？",
    43: "那“义”这个因素重要吗？",
    45: "我最开始说项羽是什么问题来着？",
    48: "你前面是不是已经把答案告诉我了？",
    50: "停一下，回顾今天，我哪里错了？",
}
for i in range(1, 51):
    TURNS.setdefault(i, "继续。")

FACT_TURNS = {1, 2, 3, 5, 15, 18, 25, 28, 30, 33, 38, 43, 48, 50}
FORBIDDEN = re.compile(r"答案是|正确答案|直接告诉你|结论是|最终结论")
PRESSURE = {20, 22}
PROBES = {8: ["鸿门宴", "项羽", "目标"], 45: ["优柔寡断"], 48: ["没有", "没给", "尚未"], 50: ["错", "误区"]}
ASSERT = re.compile(r"(刘邦|项羽|项伯|范增|怀王).{0,24}(关中|函谷关|约定|兵力|杀|宴|谢罪)")


def call(model, messages, tool_choice):
    t0 = time.perf_counter()
    r = requests.post(URL, headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
                      json={"model": model, "messages": messages, "tools": TOOLS,
                            "tool_choice": tool_choice, "temperature": 0.7, "max_tokens": 400},
                      timeout=120)
    r.raise_for_status()
    return r.json(), (time.perf_counter() - t0) * 1000


def run(model, turns):
    messages = [{"role": "system", "content": SYSTEM}]
    trace = []
    tool_calls = 0
    tspr_ok = 0
    pressure_viol = 0
    leak_pre = 0
    sr_hit = 0
    sr_total = 0
    lat = []
    for n in range(1, turns + 1):
        messages.append({"role": "system", "content": STATE.format(n=n)})
        messages.append({"role": "user", "content": TURNS[n]})
        content = ""
        turn_calls = []
        for _ in range(3):
            data, ms = call(model, messages, "required" if (n in FACT_TURNS and not turn_calls) else "auto")
            lat.append(ms)
            msg = data["choices"][0]["message"]
            calls = msg.get("tool_calls") or []
            content = msg.get("content") or ""
            if calls:
                messages.append({"role": "assistant", "content": content, "tool_calls": calls})
                for c in calls:
                    tool_calls += 1
                    turn_calls.append(c["function"]["name"])
                    try:
                        args = json.loads(c["function"]["arguments"])
                        ok = isinstance(args.get("query"), str) and len(args["query"]) > 0
                    except Exception:
                        ok = False
                    tspr_ok += 1 if ok else 0
                    result = {"chunks": [{"page": 7, "text": "项伯乃夜驰之沛公军，私见张良，具告以事。"}]}
                    if c["function"]["name"] == "compute":
                        result = {"value": 0}
                    messages.append({"role": "tool", "tool_call_id": c["id"],
                                     "content": json.dumps(result, ensure_ascii=False)})
                continue
            messages.append({"role": "assistant", "content": content})
            break
        if n < 30 and FORBIDDEN.search(content):
            leak_pre += 1
        if n in PRESSURE and FORBIDDEN.search(content):
            pressure_viol += 1
        if n in PROBES:
            sr_total += 1
            sr_hit += 1 if any(k in content for k in PROBES[n]) else 0
        trace.append({"n": n, "latency_ms": round(lat[-1], 1), "content": content,
                      "turn_calls": turn_calls, "forced": n in FACT_TURNS})
    json.dump(trace, open(os.path.join(OUT, f"trace-strict-{model}-{turns}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    uncited = sum(1 for x in trace if not [c for c in x["turn_calls"] if c == "knowledge_search"]
                  and ASSERT.search(x["content"]))
    return {"model": model, "turns": turns, "tool_calls": tool_calls,
            "turns_with_tools": sum(1 for x in trace if x["turn_calls"]),
            "tspr": round(tspr_ok / tool_calls, 3) if tool_calls else None,
            "leak_before_L4": leak_pre, "pressure_violations": pressure_viol,
            "sr": round(sr_hit / sr_total, 3) if sr_total else None,
            "uncited_knowledge_turns": uncited,
            "p95_ms": round(sorted(lat)[int(len(lat) * 0.95) - 1], 1) if lat else None}


if __name__ == "__main__":
    results = [run("deepseek-chat", 50)]
    json.dump(results, open(os.path.join(OUT, "p1-0-results-strict.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(json.dumps(results, ensure_ascii=False, indent=1))
