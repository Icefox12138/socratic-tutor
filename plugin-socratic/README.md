# dsh-socratic（教学插件骨架）

把 sidecar 的检索/页图/计算能力接进 DSH 的 Host 插件骨架。
**工具 + 章程 + `agent/pre-step` 摘要；状态机/判定/BKT/FSRS/critic 已接 sidecar；缺 DSH 内嵌 UI、对话 canary。**

## 前置

1. **一个符合契约的 RAG 数据库**：库由使用者自建，格式见
   [`docs/RAG-DB-SCHEMA.md`](https://github.com/Icefox12138/socratic-tutor/blob/main/docs/RAG-DB-SCHEMA.md)；
   OCR/切块/向量化不在本仓库。没有库时工具会返回 `no_index`，不会崩。
2. sidecar 已启动：`http://127.0.0.1:8765`
2. DSH profile `tutor`（base + headless）

## 安装

```powershell
cd D:\Guo-Code\socratic-tutor
dsh plugin --profile tutor add "link:D:/Guo-Code/socratic-tutor/plugin-socratic"
dsh --profile tutor --dump-config | Select-String socratic
```

开发期必须用 `link:`；`file:` 是复制，改源码不生效。

## 配置

环境变量：

| 变量 | 默认 |
|---|---|
| `SOCRATIC_SIDECAR_URL` | `http://127.0.0.1:8765` |
| `SOCRATIC_TOKEN` | 空（与 sidecar 一致） |

## 工具

| 工具 | 用途 |
|---|---|
| `kb_search` | 检索 chunks，返回 citation + page_image；希腊命中 `text` 为空、`image_only:true`；可带 `book`+`chapter` 限定章回（扫描本回页图） |
| `chapter_lookup` | 按 `卷3`/`第7回`/标题片段查章回页码范围与页图；给 `page` 反查所在章回 |
| `kb_read` | 按 chunk_id 读取；希腊命中同样只回 citation + 页图 |
| `cite_verify` | 取页图，返回状态/字节数 |
| `compute_math` | SymPy 白名单操作 |
| `ptc_calc` | PTC 试点：Node `vm` 沙箱，代码调 `compute_symbolic/compute_numeric`；`run_code` 名字被 DSH 保留 |
| `socratic_critic` | 多问/泄漏/无引用自检；多问时返回 rewrite |
| `socratic_init` | 初始化侧 sidecar 状态机（ALIGN） |
| `socratic_step` | 推进状态机（confirm_goal/diagnosed/.../answer） |
| `socratic_state` | 读取阶段、提示级别、尝试次数 |
| `socratic_health` | sidecar 健康检查 |
| `review_session` | 复盘当前会话：逐条判定、8 类错误、归因、复练卡（P3） |

引用卡：希腊命中显示页图；扫描本章回命中（`lang="page"`）显示章回缩略图 + 「打开章回」深链。

`view` 只允许 `student|tutor`；`answer_key` 由 sidecar 拒绝。

## 解耦与降级

- 传输层在 `lib/transport.js`（baseUrl / token / sessionId / 探测 / 降级），领域代码只 import 它；
- 每个工具执行前探测 `/health`（缓存 5 s）：不可达时返回 `{"ok":false,"error":"sidecar_unreachable",...}`，不抛异常；
  `socratic_health` 例外，永远执行并报 `reachable:false`；
- 与 sidecar 的完整边界见 `docs/SIDECAR-CONTRACT.md`（9 组端点，任何人可据此实现自己的 sidecar）；
- 契约测试：`node --test test/plugin.test.mjs`（5 条，不需要真 sidecar）。

## 流式开关

```
SOCRATIC_STREAM=buffer   (默认) 缓冲后改写，再一次性发出——单问/引用/泄漏拦截有效
SOCRATIC_STREAM=stream   逐字透传，只记审计日志（stream_passthrough），不拦截
```

硬拦截需要全文才能判断，所以默认是 buffer；stream 是给演示/关闭章程时用的，**代价是放弃拦截**。注意这不是 HTTP SSE：sidecar 不产生文本，流在 DSH 的 `llm/stream` 钩子里。

## 状态摘要（`agent/pre-step`）

- 签名实测：`(info, next)`；`info` 含 `messages/turn/step/signal/agent`；`next()` 返回 `{kind:'enter', messages}`。
- 每步向 sidecar 查询 `GET /v1/state/{session}`，把返回的 `summary` 插入一条 `runtime-context`：
  `【状态摘要】阶段=…；概念=…；提示=…；尝试=…；已揭示=…。`
- 状态由 sidecar 的确定性状态机维护，**已持久化到 `sidecar/state.db`**；重启不丢。
- 实测：`socratic_init` + `socratic_step(confirm_goal)` 后，下一步摘要为 `阶段=DIAGNOSE`，模型据此诊断。

## 试跑

```powershell
$env:DEEPSEEK_API_KEY=(Get-Content 'D:\Guo-Code\deepseek API key.txt' -Raw).Trim()
dsh --profile tutor headless "先用 kb_search 搜『微分』，报告第一条 citation；再用 cite_verify 核验它。"
```

## 硬拦截（`llm/stream`）

- 插件监听 DSH `llm/stream`，缓冲纯文本流，依次做**引用处理 → leak 处理 → 单问重写**；
- 有 `tool-call` 的流原样放行，避免破坏工具调用；
- 代价：**纯文本回复失去逐字流式**（等流结束再发）；
- 关闭单问：`SOCRATIC_HARD_REWRITE=0`；
- 引用模式：`SOCRATIC_CITATION_MODE=soften|mark|off`（默认 soften）；
- leak 模式：`SOCRATIC_LEAK_MODE=soften|mark|off`（默认 soften；L4+ 放行）。
- 实测：模型被要求问两个问题，210 字 → 209 字，最终只剩一个问句；无引用事实句被替换为“未核验”。

## 内嵌教学台（DSH Web）

- 包声明 `dsh.client`（`platform: web`）与 `exports["./client"]`；
- `client.js` 在 `conversation.composer.dock` 注册折叠面板：阶段/提示/掌握度/最近引用/页图；
- 在 `conversation.chat.turnTail` 注册**按回合引用卡**：`turn` 过滤 `/v1/citations`；
- 安装到 **web** profile 后，刷新 GUI 生效：

```powershell
dsh plugin --profile web add "link:D:/Guo-Code/socratic-tutor/plugin-socratic"
```

- 侧边栏“新会话”进入对话后，composer 下方出现“教学台”。

## 已知缺口

- 已有状态机/判定/BKT/FSRS/critic；仍缺 DSH 内嵌 UI、对话 canary、100 段人工评分；
- 没有 UI（引用卡、页图面板）；
- `tier` 仍为 `unknown`；
- 只接 FTS，未接 BGE/reranker。
