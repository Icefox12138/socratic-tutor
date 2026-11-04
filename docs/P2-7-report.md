# P2-7 状态持久化与回放报告

| 项 | 值 |
|---|---|
| 日期 | 2026-11-02 |
| 范围 | 事件溯源 + 从事件重建教学状态 |
| 位置 | `sidecar/app/state_store.py`、`main.py`、`state.db` |
| 测试 | **46/46 通过**（当时；当前总计 51） |
| 结论 | 重启不丢状态；可回放一轮对话 |

## 1. 存储

`sidecar/state.db`：

```sql
sessions(session_id PK, goal, concept, lang, created_at, updated_at)

state_events(
  id PK, session_id, seq, kind, payload, state_after, created_at,
  UNIQUE(session_id, seq)
)
```

- `init` 写一条 `init` 事件，并清空该 session 旧事件（重开即重置）；
- 每次 `/v1/state/step` 追加一条 `step` 事件；
- `payload` 存 `event/result/text/rubric/expected/evaluation/evaluation_id/mastery`；
- `state_after` 存该步之后的完整状态快照（用于 mastery 恢复与核对）。

## 2. 回放

- `state_store.load_state(session_id)`：从 `sessions` 取 goal/concept/lang，按 `seq` 重放 `step` 事件；
- 回放不重新调用 LLM/判定器：`result` 已在 payload 里，**确定性重放**；
- 最后一步的 `state_after.mastery` 恢复掌握度；
- `_SESSIONS` 仍是缓存；缓存 miss 时自动从事件重建。

## 3. 端点

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/v1/state/{id}` | 状态 + 摘要；重启后自动回放 |
| GET | `/v1/state/{id}/events` | 事件日志 |
| POST | `/v1/state/{id}/replay` | 强制清缓存并从事件重建 |

## 4. 验证

创建 `p27`：

```
init → confirm_goal → diagnosed → plan_ready → asked → answer(correct)
```

- 事件：`init + 5 step = 6`；
- **杀掉 sidecar 并重启** 后：
  - `GET /v1/state/p27` → `ADVANCE / attempts=1 / mastery=0.9973`，摘要一致；
  - `POST /replay` → `replayed=true, events=5, phase=ADVANCE, mastery=0.9973`。

## 5. 测试

- `test_persist_and_replay`：6 条事件、5 步回放、phase/question/mastery 一致；
- `test_reinit_resets_events`：重新 init 清空旧事件；
- `test_missing_session`：未知 session 返回 None；
- 既有 43 个状态机/判定/学习器/critic 测试全部保留。

## 6. 限制

- 事件日志只追加，**没有压缩/快照轮转**；长会话会线性增长（单轮 6 条事件，量很小）；
- 没有 `GET /v1/sessions` 会话列表；
- 没有回放 UI；
- 回放依赖 `result` 已落库；若手工改事件，回放会不一致；
- `state_after` 与事件 payload 有冗余，换来恢复简单。

## 7. 下一步

P2-8：PTC 计算试点（10 题，直接调用 vs PTC）；或 DSH 内嵌 UI。
