# P2-3 学习者模型报告（BKT + FSRS）

| 项 | 值 |
|---|---|
| 日期 | 2026-11-02 |
| 范围 | BKT 概念掌握 + FSRS 词汇卡片 + 状态摘要/判定接线 |
| 位置 | `sidecar/app/learner.py`、`main.py`、`state_machine.py` |
| 测试 | **38/38 通过**（当时；当前总计 51） |
| 结论 | 完成；参数未标定，UI 已接 |
| 后续状态 | BKT 阈值仍偏乐观（一次正确≈0.71），需要标定 |

## 1. BKT

参数（DESIGN §12.5，启发式）：

```
p_init=0.3, p_learn=0.15, p_guess=0.2, p_slip=0.1
```

更新：

- `correct`：后验 `p(1-slip) / (p(1-slip)+(1-p)guess)`；
- `wrong`：`p·slip / (p·slip+(1-p)(1-guess))`；
- `partial`：正确/错误后验各半；
- 再学习：`p += (1-p)·p_learn`；
- 被揭示（L5）：`p *= 0.5`（DESIGN“打 0.5 折”）。

三档（启发式阈值，不是 DESIGN 硬指标）：

| p | 显示 |
|---|---|
| <0.35 | 未掌握 |
| 0.35–0.75 | 在学 |
| >0.75 | 已掌握 |

实测：

| 操作 | before | after | 级别 |
|---|---:|---:|---|
| 初始 | 0.3 | 0.3 | 未掌握 |
| 一次 correct | 0.3 | 0.7098 | 在学 |
| 再一次 correct | 0.7098 | ~0.84 | 已掌握 |
| 一次 wrong | 0.7098 | 0.349 | 未掌握 |
| 一次 partial | 0.349 | 0.477 | 在学 |

## 2. FSRS

- 使用 `fsrs==6.3.2`（`Scheduler` + `Card` + `Rating`）。
- 表 `cards`：`term/definition/lang/state/step/stability/difficulty/due/last_review/reps/lapses`。
- 接口：添加卡片、按 `again/hard/good/easy` 复习、列到期卡。
- 实测：`lim/极限` 添加后 `good`，`due` 从 05:24 推到 05:34，`reps=1`。

## 3. 接线

- `/v1/state/init` 读取 `learner.get(concept)` 初始化 `s.mastery`；
- `/v1/state/step` 在 `answer` 后调用 `learner.record(...)`，把 `before/after/level` 放进响应；
- 状态摘要新增 `掌握=未掌握/在学/已掌握`；
- `evaluations` 与 `mastery` 共用 `sidecar/state.db`。

实测：`answer("差商的极限")` → `correct` → 掌握从 0.3 升到 0.7098，摘要显示“掌握=在学”。

## 4. 测试

- BKT：correct 升、wrong 降、partial 居中、连续 correct 过 0.85、reveal 减半、三档；
- 存储：record/get/list、非法 result；
- FSRS：add/review/due、非法 rating；
- 既有 P2-1/P2-2 测试全部保留。

## 5. 未完成

- **参数未标定**：没有 30 个模拟学生或 60–100 条金标；`p_init/p_learn` 只是 DESIGN 默认；
- 一次 correct 就接近 0.71，说明 guess/slip 需要按学科重估；
- FSRS 只覆盖词汇卡，未接语言包/UI；
- 没有 UI（三档、复习队列不可见）；
- 没有 100 段对话验证“掌握度随练习变化”的统计显著性；
- 没有把 `mastery` 反馈给状态机选支架（§12.9 的 `scaffold_level`）。

## 6. 下一步

P2-4：UI 引用卡 + 提示级别 + 页图回看；或 P2-5 100 段对话评估。建议先做 UI，让 BKT/FSRS 可见。
