# D1–D2 capability-probe 结果（8 项 API）

| 项 | 值 |
|---|---|
| 日期 | 2026-10-29 |
| 环境 | DSH 0.2.1-rc.3；profile `tutor`（`dsh-base` + `dsh-headless` + `dsh-capability-probe`）；headless 模式 |
| 探针 | `plugin-probe/index.js`（Host Cordis 插件，link 安装） |
| 证据 | `eval/p0/capability/probe-log.jsonl`；headless 会话输出 |

## 结论矩阵

| # | 核对项 | 结论 | 证据 | Fallback |
|---|---|---|---|---|
| 1 | `defineTool` 导入与 schema | **部分**：`@deepseek-ai/dsh-tools` 在 profile 内不可解析；但 `ctx.tools.register()` 接受**原始 JSON Schema** 并成功注册、被模型调用 | `tool_register:"ok"`；模型成功调用 `probe_ping` | 用原始 JSON Schema 注册；参数在 sidecar 再校验 |
| 2 | `tools/post-execute` 改写 | **可用（签名已纠正）**：`(exec, result)`；返回 `{ content }` 可替换内容；返回 `{ content, value }` 报 `cannot replace both value and content` | `post_execute` → `post_rewrite`；headless 返回 DONE 无错 | 按 `{content}` 改写；保留 `value` 由 sidecar 处理 |
| 3 | `systemPrompt.context` 回放 | **部分**：方法存在；`context({name,order,text})` 返回 function（签名与假设不同），未验证刷新后回放 | `systemPrompt_context:"function"`；`context_call:"function"` | 状态写 session event + 自定义节点重放；不依赖 context 持久化 |
| 4 | `ConversationNodeDefinition` | **未验证**（需 Client 包；本探针只测 Host） | — | 通用卡片 + 右侧栏；不阻塞教学 |
| 5 | `ctx.jobs.start` 进度 | **部分**：方法存在；未跑生命周期（需 owner/agent） | `jobs_start:"function"`；`tools` 原型含 `createExecution/execute` | 轮询 sidecar `/v1/jobs/{id}` |
| 6 | `ctx.storage` 持久化 | **部分**：hub 存在（`ctx/name/backend/forms`），`forms` 为空；未验证写入 | `storage:["ctx","name","backend","forms"]` | 学习者模型存 sidecar SQLite，Host 只读 |
| 7 | 本地配置 / token | **未验证**：`DSH_SIDECAR_TOKEN` 不存在；文件读取未测 | `env_token:false` | 启动脚本写 `DSH_SIDECAR_TOKEN`；Host 读 env |
| 8 | 出站消息钩子 | **未发现**：无公开钩子证据 | 仅 `tools/*` 钩子可用 | **数据层隔离 + critic 兜底**；不承诺零泄漏 |

## 关键发现（必须写进插件契约）

1. **`inject` 是硬约束**：不声明 `inject` 时访问 `ctx.tools` / `ctx.systemPrompt` / `ctx.jobs` / `ctx.storage` 会抛 `cannot get property "X" without inject`。插件必须 `export const inject = ['tools','systemPrompt','jobs','storage']`。
2. **post-execute 签名是 `(exec, result)`**，不是 `(result, next)`；返回 `{content}` 只能替换内容，**不能同时**返回 `value`。
3. **`file:` 安装是复制**，改源码不会生效；开发期用 `link:`（本探针已改 `link:`）。
4. **profile `package.json` 必须 UTF-8 无 BOM**；PowerShell 5.1 的 `Set-Content -Encoding UTF8` 会加 BOM，DSH 读取时报 `Unexpected token`。
5. **headless 需要 `@deepseek-ai/dsh-headless` bundle + `DEEPSEEK_API_KEY`**；desktop 的凭据不会自动带到新 profile。
6. `ctx.tools` 原型暴露 `register / restrict / guard / execute / createExecution / prepareExecution`，后续可做更细的行为探针。

## 对 DESIGN.md 的影响

- §16.4 钩子表：`tools/post-execute` 的签名与“不能同时替换 value/content”要写死；`systemPrompt.context` 标为“签名待定，状态另存 session event”。
- §16.9：第 1 项改为“原始 JSON Schema 可用；`defineTool` 导入待核”；第 3 项标“部分”；第 4/7/8 项沿用 fallback。
- §16.7：sidecar token 用 `DSH_SIDECAR_TOKEN` 环境变量注入，不依赖文件读取。

## 判定

**D1–D2 通过（部分验证）**：4 项可用/部分可用、4 项未验证，均有 fallback，**不阻塞 D3**。风险等级：低（无“必须依赖未验证能力”的设计点）。
