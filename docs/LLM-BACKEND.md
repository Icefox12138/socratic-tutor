# LLM 底座：谁在用模型、怎么换、换了要重测什么

| 项 | 值 |
|---|---|
| 日期 | **2026-11-16** |
| 范围 | 运行时（sidecar + DSH 插件）；数据工程的同名文档在 `rag-build/docs/LLM-BACKEND.md` |
| 结论 | 运行时的模型调用只有 **两处**，都走 `sidecar/app/llm.py`；换底座是改环境变量，不是改代码 |

---

## 0. 一句话

运行时里只有 **OOV 翻译**和**答案判定**会调模型；其余（检索、引用、页图、状态机、critic、硬拦截、插件）全部与模型无关。所以"换底座"影响的是翻译与判定的**质量**，不是引用链路的**正确性**。

## 1. 唯一的客户端

`sidecar/app/llm.py` 是运行时唯一的模型出口。配置全部来自环境：

| 变量 | 默认 | 说明 |
|---|---|---|
| `SOCRATIC_LLM_BASE` | `https://api.deepseek.com` | OpenAI 兼容端点（vLLM / Ollama / SiliconFlow / OpenRouter 都行） |
| `SOCRATIC_LLM_MODEL` | `deepseek-chat` | 模型 id；**建议写死具体版本**而不是别名（见 §5） |
| `SOCRATIC_LLM_KEY_FILE` | `<repo>/deepseek API key.txt` | 不设 `DEEPSEEK_API_KEY` 时读它 |
| `DEEPSEEK_API_KEY` | — | 优先级最高 |
| `SOCRATIC_LLM_TIMEOUT` | `25` 秒 | 判定走同一个值 |

`llm.chat()` 只依赖 **`POST {base}/chat/completions`** 与 `choices[0].message.content` 这一个形状；不发送 `response_format`，不依赖 DeepSeek 私有字段。**没有重试**：两个调用方都设计成"失败即降级"，教学回合不能被慢端点拖住。

## 2. 两处调用点

| 调用点 | 何时用 | 失败时 | 影响 |
|---|---|---|---|
| `translate.py`（OOV 翻译） | `SOCRATIC_TRANSLATE=llm` 或 `auto` 且词表未命中 | 返回 `[]`，退回纯词表 | 只影响跨语言召回，不影响引用 |
| `evaluator.py`（答案判定） | 规则判定不出结论时 | 返回 `partial/0.3` + `judge_unavailable`，**不抛给调用方** | 判定质量下降，状态机照常推进 |

判定结果会带 `judge = {model, base, latency_ms}`，并写入 `evaluations.judge` 列（`state.db`；旧库首次打开时就地 `ALTER`，不改写已有行）。`/health` 另报 `llm: {base, model, configured}`，**不含密钥**。

## 3. 与模型无关的部分（换底座不受影响）

- 引用链路：`citation` 的 locator / tier / role / policy_version 全部由策略与数据决定；
- `answer_key` 物理隔离、页图渲染、章回索引；
- DSH 插件与人格包：`dsh-socratic` 的 13 个工具、`dsh-socratic-persona` 的章程与 `llm/stream` 改写都是**内容规则**，不认 provider；
- 评测口径中的 recall / R@5 / 泄漏计数：与模型无关（除非你改翻译）。

## 4. 换底座的步骤

1. 设 `SOCRATIC_LLM_BASE` / `SOCRATIC_LLM_MODEL` / 密钥，重启 sidecar；
2. `GET /health` 确认 `llm.model` 与 `llm.base` 是你想要的，`configured: true`；
3. 跑 smoke：`scripts/contract_check.py --query 极限`（确认不依赖模型的功能没坏）；
4. 重测**两件事**（其余不用重测）：
   - **OOV 翻译**：`eval/llm/`（rag-build 侧的金标；见该工程 `docs/LLM-BACKEND.md`）——看跨语言 R@10 是否退化；
   - **判定一致性**：同一批"开放题 + 学生答案"，比较新旧模型的 `result` 分布与人工标注的一致率（当前 86.7% 的错误分类基线是在 `deepseek-chat` 上测的）。

## 5. 已知的坑

1. **别名会漂移**：`deepseek-chat` 是别名，背后模型换过版本；结果文件里要记 `model` + 日期（`llm.provenance()` 已提供），否则"数字可比"是假的。
2. **JSON 合规率**：判定提示词只要求"返回 JSON"，没有 `response_format`。小模型可能返回围栏或散文——`llm.parse_json()` 能容忍围栏与前后文，但仍可能失败；失败会**静默降级**为 `partial`，没人会收到告警。
3. **中文标签**：判定的 misconception 标签是中文，供中文教学界面使用；英文底座可能改变标签分布。
4. **延迟**：reasoner 类模型会显著变慢，25 秒超时可能不够；`judge_unavailable` 会变多。
5. **不要把内置工具放进检索路径**：DeepSeek 的 `deepseek_web_search` / `deepseek_read_url` 由服务端自己发起检索并拼上下文，**绕过引用策略**（没有 tier、没有 role、没有 locator、进不了 `citations` 表）。检索只能用本仓的 sidecar 通道。
6. **公开数据的归属看"要不要先加工"，不看"是不是调 API"**：下载下来必须先解析/切块/建索引才能用的（Perseus 版本 XML、archive.org 元数据、Wikisource 页面入库），是**构建输入**，归数据工程；只有"拿来即用"的才算运行时的服务时调用（例如按 CTS URN 现场取一段、按 revision 复核一条引文）。**运行时目前没有任何服务时公开 API 调用**：唯一的联网路径是 `scripts/ingest_public.py` + `app/adapters/`，它把公开语料写进 `public.db`，是构建步骤，不参与答题。

## 6. 相关代码与测试

| 文件 | 作用 |
|---|---|
| `sidecar/app/llm.py` | 唯一客户端（route / chat / parse_json / provenance） |
| `sidecar/app/evaluator.py` | 判定，走 `llm.chat_json()`，结果带 `judge` |
| `sidecar/app/translate.py` | OOV 翻译，走 `llm.chat()`，失败返回 `[]` |
| `sidecar/tests/test_llm.py` | 11 条：路由来自配置、密钥优先级、loader 注入、HTTP/形状错误包装、JSON 容错、判定落到配置端点、verdict 带 judge 入库 |
| `scripts/ingest_public.py` + `app/adapters/` | 公开语料的**构建期**导入（写 `public.db`）；不是服务时调用 |
