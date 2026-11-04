# P2-2 判定器 + Critic 报告

| 项 | 值 |
|---|---|
| 日期 | 2026-11-02 |
| 范围 | 受约束判定（correct/partial/wrong）+ 误区标签 + `evaluations` + 反模式 critic |
| 位置 | `sidecar/app/evaluator.py`、`critic.py`、`evaluations.py`、`main.py`、插件 |
| 测试 | **28/28 通过**（P2-1 15 + P2-2 13；当前总计 51） |
| 结论 | 判定器可用；critic 规则 + 单问/引用/leak 硬拦截已接 |
| 后续状态 | 100 段自动评估已完成；人工评分跳过 |

## 1. 判定器

流程：**规则优先 → LLM JSON 兜底**。

| 输入 | 规则 | 输出 |
|---|---|---|
| `expected` 精确/包含 | 命中 | correct, 0.95 |
| `expected` 数值 | 容差内 | correct, 0.95 |
| `rubric` 关键点 | ≥80% | correct, 0.7–0.9 |
| `rubric` 关键点 | 40–79% | partial, 0.4–0.7 |
| `rubric` 关键点 | <40% | wrong, 0.7 |
| 空回答 | — | wrong, 0.95 |
| 无规则 | LLM | JSON 校验后返回 |

LLM 输出契约：

```json
{"result":"correct|partial|wrong","confidence":0.0,"misconceptions":["..."],"reason":"..."}
```

校验失败/超时/无 key → `partial, 0.3, ["judge_unavailable"], source=fallback`，不抛给状态机。

**实测**：`"导数可以表示瞬时速度"` 被判 `partial, 0.8`，误区 `循环论证/未解释极限过程`。

## 2. 状态机接线

- `State` 新增 `question/rubric/expected`；
- `asked` 事件把问题、rubric 写入状态；
- `answer` 不传 `result` 时，sidecar 用 `question + text` 自动判定；
- 判定写入 `evaluations`，返回 `evaluation` 与 `evaluation_id`；
- 判定结果直接驱动 `ADVANCE/HINT`。

**实测**：`差商` 对 `差商的极限` + rubric `差商,极限` → `partial 0.55` → 状态 `HINT`。

## 3. Critic（规则骨架）

检测：

| flag | 条件 |
|---|---|
| `leak` | hint<4 且含“答案是/最终答案” |
| `self_answered` | 同段有“答：”且有问句 |
| `multi_question` | >1 个问号 |
| `empty_hint` | L1–L3 且 <15 字或“再想想” |
| `uncited_claim` | 含“根据/研究表明”且无 citation |

返回 `{ok, flags, critical, action}`；多问时附 `rewrite`（只保留第一个问句）；`uncited_claim` 时附 `citation_rewrite`（soften/mark）。已接 DSH `llm/stream` 硬拦截（引用→leak→单问；L4+ 放行 leak）。

## 4. 数据库

`sidecar/state.db`：

```sql
evaluations(id, session_id, question, answer, result, confidence,
            misconceptions, reason, source, created_at)
```

`GET /v1/evaluations/{session_id}` 可回读。

## 5. 测试

- 精确/数值/rubric 全命中/部分/未命中；
- 短前缀不得判 correct（回归）；
- 空回答；
- LLM 关闭兜底；
- 非法 JSON；
- DB save/list；
- critic 五类 flag；
- `asked` 存题 + `answer` 推进。

## 6. 未完成

- LLM 判定**未标定**：没有 60–100 条双人金标，不能宣称 ≥80%；
- `expected` 是答案键，**插件不传**，只在服务端/管理接口用；
- critic 只标记，不重写；
- 无 100 段对话、SR、置信区间；
- 判定结果未更新 BKT（P2-3）。

## 7. 下一步

P2-3：BKT + FSRS，把 `evaluations` 变成掌握度变化；或先做 UI 引用卡。
