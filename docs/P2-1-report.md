# P2-1 状态机报告

| 项 | 值 |
|---|---|
| 日期 | 2026-11-02 |
| 范围 | 确定性状态机 + L0–L5 + 提问分类 + 显式状态摘要 |
| 位置 | `sidecar/app/state_machine.py`、`classifier.py`、插件 `socratic_init/step/state` |
| 测试 | **15/15 通过**（8 状态机 + 7 分类器） |
| 结论 | **完成**；当时未做的 LLM 判定/BKT/critic/持久化已由 P2-2/3/7 补齐 |
| 后续状态 | 当前 sidecar **51/51**；状态已持久化（`state_events`） |

## 1. 状态机

```
ALIGN → DIAGNOSE → PLAN → ASK → WAIT
                                  ├─ answer(correct) → ADVANCE → ASK / TRANSFER
                                  ├─ answer(partial/wrong) → HINT(L+1) → WAIT
                                  └─ hint_request → HINT / L5 reveal → WAIT
TRANSFER → transfer_done → SUMMARY
任意状态 → stop → SUMMARY
```

| 状态 | 允许事件 |
|---|---|
| ALIGN | `confirm_goal`, `stop` |
| DIAGNOSE | `diagnosed`, `stop` |
| PLAN | `plan_ready`, `stop` |
| ASK | `asked`, `hint_request`, `stop` |
| WAIT | `answer`, `hint_request`, `stop` |
| HINT | `answer`, `asked`, `hint_request`, `stop` |
| ADVANCE | `next`, `stop` |
| TRANSFER | `answer`, `transfer_done`, `stop` |
| SUMMARY | 终止 |

规则：

- 判定 `correct` → `ADVANCE`；连续 2 次 → `TRANSFER`；
- `partial/wrong` → `HINT`，`hint_level+1`（上限 L5）；
- `hint_request` 置 `explicit_ask`；`may_reveal` 满足才给 L5；
- 所有转移由代码计算，LLM 只写措辞。

## 2. 提问分类

`/v1/classify` 规则分类：`clarify/hypothesis/evidence/perspective/inference/meta`，并返回问句数与 `multi`（>1 个问号）。

## 3. 显式摘要

每步 sidecar 返回：

```
【状态摘要】阶段=WAIT；概念=导数；提示=L2 类比/例子；尝试=2；连对=0；已揭示=否。
```

插件 `agent/pre-step` 通过 `GET /v1/state/{session}` 取该摘要，作为 `runtime-context` 插入，不依赖 `systemPrompt.context` 回放。

## 4. 验证

- 单测 15/15：ALIGN→WAIT、correct→ADVANCE、两连对→TRANSFER、partial/wrong→HINT、reveal 政策、stop 终止、非法转移、摘要字段、六类提问。
- 端到端：`init(导数)` → `confirm_goal` → `DIAGNOSE` → `diagnosed` → `PLAN` → `plan_ready` → `ASK` → `asked` → `WAIT` → `answer(correct)` → `ADVANCE`。
- 插件 headless：模型调用 `socratic_init` + `socratic_step(confirm_goal)` 后，下一轮摘要显示 `阶段=DIAGNOSE`，模型据此只问一个诊断问题。

## 5. 未完成（P2-1 的剩余）

- LLM 判定器（`correct/partial/wrong` + 误区标签 + confidence）；
- BKT 掌握度、FSRS；
- critic（自问自答/提问轰炸/空提示/循环）；
- 状态持久化（当前 sidecar 进程内 dict，重启丢失）；
- 100 段对话、SR ≥90%；
- UI。

## 6. 下一步

P2-2：把“学生回答 → 判定”接成受约束 JSON（规则优先、LLM 兜底），并写 `evaluations`；这是状态机真正闭环的前提。
