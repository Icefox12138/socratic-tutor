# DSH 插件骨架冒烟（2026-11-02）

## 安装

```powershell
dsh plugin --profile tutor add "link:D:/Guo-Code/socratic-tutor/plugin-socratic"
```

`--dump-config` 可见：

```
# == dsh-socratic
- id: socratic-teacher
  name: dsh-socratic
```

## Headless 试跑

命令：

```powershell
$env:DEEPSEEK_API_KEY=(Get-Content '/path/to/deepseek API key.txt' -Raw).Trim()
dsh --profile tutor headless "Use kb_search with query 微分, view student, limit 3. Then use cite_verify on the first result's source, book, page. Report the first locator and the byte count. Do not answer from memory."
```

结果：

| 项 | 值 |
|---|---|
| 插件加载 | `[dsh-socratic] registered kb_search/kb_read/cite_verify/compute_math/socratic_health` |
| `kb_search` | 3 条；首条 chunk_id **77840**，`library`，page **10**，score 9.4017 |
| 首条 locator | `数学\其他\随机过程\随机过程 方兆本.pdf p.10` |
| `cite_verify` | **ok=200，bytes=149,798** |
| 模型行为 | 先调用工具，再报告 locator/字节数，明确“不凭记忆” |

## 追加：硬拦截（2026-11-02）

- `llm/stream` 监听器缓冲纯文本流，先做引用处理，再做单问重写；tool-call 流放行。
- headless 要求“问两个问题” → 日志 `hard_rewrite before=210 after=209`，最终回复只有一个问句。
- 引用：`根据定理，A 成立。`（无 p.）→ `这一点我尚未核验，先不下结论。`；带 `（p.12）` 不变。
- 代价：纯文本回复不再逐字流式；`SOCRATIC_HARD_REWRITE=0` 可关；`SOCRATIC_CITATION_MODE=soften|mark|off`。

## 追加：DSH 内嵌教学台（2026-11-02）

- 包 0.2.0 增加 `dsh.client` 与 `client.js`，注册 `conversation.composer.dock`；
- 临时 web profile（64839）boot graph 含 `dsh-socratic/client.js`；
- CDP dump：`教学台=True`、`引用卡=True`、`最近引用=True`；
- 让 GUI agent 调 `kb_search` 后，面板出现 `数学\...\随机过程 方兆本.pdf p.122`；
- 截图：`dsh-embedded.png`；用户 GUI 需刷新/重启才会加载新 client entry。

## 追加：按回合引用卡（2026-11-02）

- `conversation.chat.turnTail` 注册 `TurnCitations`；props.turn 是 TurnRecord，取 `props.turn.turn`；
- `kb_search` 带 `session_id/turn/step/call_id`；sidecar `citations` 表按轮存；
- 实测：GUI 调 `kb_search` 后，该 assistant 回合尾部出现“本轮引用”3 条（p.36 / p.92 / p.122），每张卡有“页图”；
- 截图：`dsh-per-turn.png`。

## 追加：leak 硬拦截（2026-11-02）

- `softenLeak` 在 hint<4 时把“答案是/最终答案”句子替换为“先不揭示最终答案；你先说说卡在哪一步？”；
- 实测：headless 强制回复“答案是 2” → 输出替换句；日志 `leak:true, hint:0`；
- L5（hint≥4）放行；`SOCRATIC_LEAK_MODE=soften|mark|off`。

## 追加：K5 希腊页图引用（2026-11-02）

- 引用 `lang=greek` 时，turnTail 卡片不显示 OCR snippet；
- 显示“希腊原文：OCR 不可用，仅页图”+ 内嵌页图缩略图，点击全屏；
- 适合 K5 Loeb 希腊页；K6 拉丁仍显示文本+页图。

## 追加：PTC `ptc_calc`（2026-11-02）

- 工具名不能用 `run_code`（DSH PTC transport 保留）；使用 `ptc_calc`；
- headless 实测：模型调用 `ptc_calc`，日志 `ptc_run ok=true calls=1`；
- 10 题正确 10/10，6 类逃逸 0；详见 `docs/P2-8-PTC.md`。

## 已知缺口

- 没有状态机 / 提示级别 / 复盘；
- 状态仅插件进程内 Map，重启丢失；
- 没有 UI（引用卡、页图面板）；
- `tier` 仍为 `unknown`；
- 只接 sidecar 的 FTS，未接 BGE/reranker；
- 无 token 时只适合本地。

## 追加：`agent/pre-step` 摘要（2026-11-02）

- 实测签名：`(info, next)`；`info` 键 `messages/turn/step/signal/agent`；`next()` 返回 `{kind:'enter', messages}`。
- 每步插入 `runtime-context` 摘要；`socratic_state` 工具可 `set` 概念/提示级别/尝试次数/是否揭示/误区。
- 实测：先 `set concept=导数 hint=L2 attempts=1`，下一步摘要变为
  `【状态摘要】概念=导数；提示级别=L2；尝试次数=1；已给最终答案=否；学生误区=未记录。`
  模型能复述该摘要并按 L2 继续提问。
- 状态存在插件进程内 Map，**重启丢失**；P2 要落 sidecar/session event。
