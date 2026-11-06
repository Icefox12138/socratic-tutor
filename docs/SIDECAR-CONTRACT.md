# SIDECAR-CONTRACT（插件与 sidecar 的边界）

这份文件是 `plugin-socratic` 与 `sidecar` 之间的**唯一契约**。任何实现只要满足下面 9 组端点，插件就能工作；插件本身不假设 sidecar 是 Python、FastAPI，还是别的什么。

- 基础地址：`SOCRATIC_SIDECAR_URL`（默认 `http://127.0.0.1:8765`）或插件配置 `baseUrl`
- 鉴权：若 `SOCRATIC_TOKEN` 非空，接受两种头——
  `Authorization: Bearer <token>`（社区标准）或 `X-Sidecar-Token: <token>`（DSH 插件默认）。
  服务端未配置 token 时忽略鉴权；配置了 `SOCRATIC_REQUIRE_AUTH=1` 却无 token 时返回 503
- 自描述：`GET /openapi.json`（FastAPI 自动生成）与 `/docs` 无需鉴权，可直接当契约校验用
- 所有响应：`application/json`，错误体 `{"detail": "..."}` + 非 2xx
- 插件在每次工具调用前探测一次 `/health`（缓存 5 秒）；**探测失败时工具返回结构化错误，不抛异常**

## 1. 健康

```
GET /health -> 200 {"ok": true, "chunks": 167192, "bge": "ready", ...}
```

任何 2xx 视为可用；插件只关心可达性。

## 2. 检索

```
GET /v1/search?q=&view=&limit=&source=&lang=&book=&chapter=&document_id=&section=&scope=&session_id=&turn=&step=&call_id=
```

| 字段 | 说明 |
|---|---|
| `view` | `student` / `tutor`（服务端必须过滤 `answer_key`；v2 还会隐藏非 `text` 流） |
| `book` + `chapter` | 可选，把范围收窄到一个章回；扫描本返回 `mode: "page_only"` |
| `document_id` + `section` | v2 公开语料的范围收窄；`chapter` 是 `section` 的别名 |
| `source` | v1 是语料桶（`library`…），v2 是 `source_id`（`wikisource:zh`…） |
| `scope` | `auto`（默认，只查当前库）/ `all`（v1+v2 联邦）/ `routed`（按语言/覆盖路由到一个库，需两库路径） |
| `session_id/turn/step/call_id` | 可选，服务端据此写引用流水 |

响应：

```json
{"query": "...", "view": "student", "schema": "v2", "mode": "fts-public",
 "results": [{"chunk_id": 1, "document_id": "wikisource:zh:史記/卷001",
              "source": "wikisource:zh", "book": "史記/卷001", "lang": "zh-classical",
              "page": null, "section": "黃帝", "stream": "text",
              "positions": {"char_start": 0, "char_end": 601}, "bbox": null,
              "text": "黃帝者……", "score": 0.8, "similarity": 0.8,
              "citation": {"scheme": "mediawiki", "locator": "《史記/卷001》黃帝（Wikisource rev 11133934）",
                           "url": "https://zh.wikisource.org/wiki/…?oldid=11133934#黃帝",
                           "image": null, "page_image": null,
                           "tier": "A", "tier_estimated": false, "role": "cite",
                           "policy_version": "bb263d1e4d64",
                           "license": "PD-old", "revision": "11133934"}}],
 "chapter": null, "took_ms": 12.3, "cached": false}
```

`citation.tier` 是可信度层级（`A` 校对文本 / `B` 原页渲染 / `C` OCR 文本 /
`D` 机器生成），由服务端引用策略决定：v2 按语料源查表，v1 的页级引用为 `B`
并带 `tier_estimated: true`（库内没有逐 chunk 的校对层元数据）。
`citation.role` 目前恒为 `cite`；`tier_estimated` 为真表示该层级是粗判而非实测。
`citation.policy_version` 是生效策略的内容哈希，见
[CITATION-POLICY-PLAN.md](CITATION-POLICY-PLAN.md)。

`mode` 取值：`fts` / `bge+rerank` / `page_only`（v1）、`fts-public` /
`bge+rerank-public`（v2；有 BGE 向量时是后者，否则自动退回 `fts-public`）、
`federated`（`scope=all`）、`routed`（`scope=routed`）。
`federated` 响应额外带 `schemas: ["v1","v2"]`，每条结果带 `schema`，
两库各取 `limit` 后按 RRF 合并；某库失败写 `errors`，另一库仍返回。
合并由引用策略决定，响应带 `merge: {mode, anchor, weights}`
（`mode` 默认 `rrf`，与历史行为逐位相同），每条结果的
`citation.role_in_answer` 为 `anchor` 或 `corroborating`——只标注，不改变顺序。
`routed` 只查一个库，响应带 `routed_to` / `route_reason` / `route_probe`。
详见 [FEDERATED-SEARCH.md](FEDERATED-SEARCH.md)。
v2 还可能带 `translated: true` 与
`translations: [{"lang":"greek","text":"…","source":"glossary|llm"}]`；
翻译只用于扩展检索，不是引用证据。v2 搜索默认还融合 grep/lemma，
响应带 `"lexical": {"grep": n, "lemma": n}`（`SOCRATIC_LEXICAL=off` 可关）。
插件对 `lang="page"` 与 `image_only=true` 有特殊渲染（页图卡）；v2 用 `citation.url`。

## 3. 片段 / 章回

```
GET /v1/chunks/{id}?view=student|tutor
GET /v1/chapter?source=&book=&q=卷3|第7回|标题片段   （或 ?page=50 反查）
```

`/v1/chapter` 返回 `{chapter, prev, next, pages}`，`page_image` 必须可直接 GET。

## 4. 页图

```
GET /v1/pages?source=&book=&page=&dpi=72..300[&bbox=x0,y0,x1,y1]
-> 200 image/png
```

v2（公开语料）没有页图：`citation.page_image` 为 `null`，用 `citation.url` 打开原文。

## 4b. 公开语料（schema v2）

```
GET /v1/sources
-> {"schema": "v2", "sources": [{"source_id","adapter","base_url","license",
                                 "redistribution","rate_limit", ...}]}

GET /v1/documents?source=&lang=&limit=&offset=
-> {"schema": "v2", "documents": [{"document_id","title","lang","license","chunks"}]}

GET /v1/documents/{document_id}
-> {"document_id","title","author","lang","license","canonical_url","scheme",
    "chunks": 28, "sections": [{"section","ord","chunks"}]}

GET /v1/verify?document_id=&quote=&section=&revision=
-> {"verified": true, "method": "text", "scheme": "mediawiki",
    "document_id": "...", "revision": "11133934", "chunks": 5, "reason": ""}
```

`document_id` 里可以含 `/`（如 `wikisource:zh:史記/卷001`），路径按 `:path` 转发。
给定 `revision` 时，索引里的 revision 不一致会直接 `verified=false`（reason 写明 mismatch）。

## 4c. 词法通道（grep / lemma）

```
GET /v1/grep?q=&view=&limit=&source=&lang=&book=&document_id=&section=
GET /v1/lemma?q=&view=&limit=&source=&lang=&book=&document_id=&section=
```

- `grep`：精确子串（Unicode casefold），v1/v2 都可用；用于引文、人名、公式、标识符。
- `lemma`：词形归并，**只支持 v2 干净文本**；v1 返回 400。
- 响应：

```json
{"query": "μῆνις", "view": "student", "schema": "v2", "mode": "lemma",
 "results": [{"chunk_id": 1, "document_id": "...", "section": "1.1",
              "citation": {"locator": "...", "url": "..."},
              "match": {"coverage": 1.0, "lemmas": ["μῆνις"], "exact": false}}],
 "took_ms": 3.2}
```

`grep` 的 `match` 是 `{start,end,snippet,count}`；`lemma` 的 `match` 是
`{coverage,lemmas,exact}`。两者都只返回 `visibility='tutor'` 的行。

## 5. 计算

```
GET  /v1/compute/backends
POST /v1/compute {"expression": "...", "operation": "...", "variable": "x",
                  "point": "0", "backend": "auto|sympy|scipy|pint|control|wolfram|lean",
                  "target": "上界/目标单位", "data": {"num": [], "den": []}}
-> {"ok": true, "backend": "scipy", "engine_version": "...", "result": ...,
    "latex": "...", "numeric": ..., "details": ...,
    "verification": {"method": "quad_error", "ok": true, "error": ...},
    "cross_check": {"backend": "sympy", "value": ..., "difference": ...},
    "disputed": false,
    "sandbox": "audit",
    "credentials": {"backend": "...", "input_sha256": "...",
                    "assumptions": {...}, "verification": {...},
                    "sandbox": "audit", "generated_at": "..."}}
```

| backend | operations | 说明 |
|---|---|---|
| `sympy` | simplify/diff/integrate/solve/limit/value/latex/factor/expand | 符号；默认 |
| `scipy` | quad/minimize/root | 数值；`quad` 用 `point`/`target` 作上下界 |
| `pint` | convert | `expression="3 m"`, `target="ft"`；可选 |
| `control` | step | `data={"num":[1],"den":[1,2,1]}`；可选 |
| `wolfram` | eval | 需 `wolframscript` + `SOCRATIC_COMPUTE_EXTERNAL=1` |
| `lean` | check | 需 `lean`/`lake` + `SOCRATIC_COMPUTE_EXTERNAL=1` |

- 不可用后端返回 **503** `{"code":"backend_unavailable","detail":...,"backends":...}`，
  不返回假结果。
- `auto` 按 operation 推断后端；未知 operation/backend 返回 400。
- SymPy/SciPy/pint 仍做表达式黑名单校验；Wolfram/Lean 是外部代码，默认关闭。
- 本地后端在**可 kill 的子进程 worker** 中执行；worker 使用 audit 策略沙箱
  （禁 socket/子进程、只写 per-run temp），不是 OS 隔离。
  `credentials` 带 `input_sha256/assumptions/verification/sandbox`；SciPy quad
  会用 SymPy 积分 cross-check，超差标 `disputed: true`。
- `GET /v1/compute/backends` 返回每个后端的 `available/version/operations/install`
  以及 `sandbox` 状态。

## 6. 教学状态机

```
POST /v1/state/init {"session_id","goal","concept","lang"}
POST /v1/state/step {"session_id","event","result?","text?","rubric?","expected?"}
GET  /v1/state/{session_id}
GET  /v1/state/{session_id}/events
POST /v1/state/{session_id}/replay
```

`step` 返回 `{state, action: {kind, phase, hint, instruction}, summary, allowed_events}`；`summary` 会被插件注入到下一轮上下文。

## 7. 判定 / 自检

```
POST /v1/critic {"text","hint_level","has_citation"}
POST /v1/critic/rewrite {"text"}
POST /v1/critic/citation {"text","mode"}
POST /v1/critic/leak {"text","hint_level","mode"}
```

## 8. 引用流水

```
GET /v1/citations/{session_id}?turn=&limit=
-> {"citations": [{"id","locator","lang","snippet","page_image",
                   "document_id","scheme","url", ...}]}
```

turnTail 卡片只读这个端点。

## 9. 复盘

```
POST /v1/review {"session_id","state?","answers?","record?"}
-> {"claims": [...], "summary": {...}, "practice": [...], "digest"}
```

---

## 10. 兼容字段（社区对齐）

每条 result 同时给原生字段与社区通用别名，方便把 RAGFlow/Onyx 的客户端接过来：

| 字段 | 值 |
|---|---|
| `document_id` | `<source>:<book>` |
| `page` | 页码（原生） |
| `similarity` | 与 `score` 同值 |
| `positions` / `bbox` | `null`（本实现是页级 chunk，没有块级坐标） |

`citation.document_id` 也同步给出。

## 11. 契约探针

```bash
python scripts/contract_check.py --base http://127.0.0.1:8765 [--token X] [--expect-auth]
```

9 项检查：openapi、必需端点、health、search、result shape、page image、books、toc、chapter；`--expect-auth` 再加一条"无 token 必须 401"。
v2 库会把 page image 换成 `citation scheme` / `citation url` / `sources` 三项检查。
若服务暴露 `/v1/grep` / `/v1/lemma`，会额外探测（旧服务自动跳过）。
退出码 0 表示"插件/MCP 可用"。

## 12. MCP 包装

`packages/socratic-mcp` 把同一组能力暴露成 MCP tools（`kb_search` / `kb_read` / `chapter_lookup` / `review_session` / `socratic_state` / `socratic_health`），任何 MCP host 可直接接入，不必实现本契约的 HTTP 细节。
`kb_search` 透传 `source` / `lang` / `book` / `chapter`，v2 另接受 `document_id` / `section`。

---

## 降级契约

| 情况 | 插件行为 |
|---|---|
| `/health` 不可达 | 所有需要 sidecar 的工具返回 `{"ok":false,"error":"sidecar_unreachable","tool":...,"hint":...}` |
| 工具返回非 2xx | 原样透传状态与响应体（`{"ok":false,"status":500,"body":{...}}`） |
| `socratic_health` | 永远执行，返回 `{"reachable": false, "base": ...}` |
| 流式拦截 | 只在有教学工具参与的请求上启用（`kb_*`/`socratic_*`/`cite_verify`） |

## 参考实现

`sidecar/` 是本契约的参考实现（FastAPI + SQLite + PyMuPDF）。实现自己的 sidecar 只需满足上表；不需要 Python。
