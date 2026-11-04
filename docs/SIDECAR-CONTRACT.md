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
GET /v1/search?q=&view=&limit=&source=&lang=&book=&chapter=&session_id=&turn=&step=&call_id=
```

| 字段 | 说明 |
|---|---|
| `view` | `student` / `tutor`（服务端必须过滤 `answer_key`） |
| `book` + `chapter` | 可选，把范围收窄到一个章回；扫描本返回 `mode: "page_only"` |
| `session_id/turn/step/call_id` | 可选，服务端据此写引用流水 |

响应：

```json
{"query": "...", "view": "student", "mode": "fts|bge+rerank|page_only",
 "results": [{"chunk_id": 1, "source": "library", "book": "...", "lang": "greek|page|zh",
              "page": 12, "text": "", "image_only": true, "score": 0.8,
              "citation": {"locator": "...", "tier": "unknown", "page_image": "/v1/pages?..."}}],
 "chapter": {"title": "卷3 殷本紀第三", "page_start": 109, "page_end": 128},
 "pages": [{"page": 109, "page_image": "/v1/pages?..."}],
 "took_ms": 12.3, "cached": false}
```

插件对 `lang="page"` 与 `image_only=true` 有特殊渲染（页图卡）。

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

## 5. 计算

```
POST /v1/compute {"expression": "...", "operation": "simplify|diff|integrate|solve|limit|value|latex",
                 "variable": "x", "point": "0"}
-> {"result": "...", "latex": "..."}
```

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
-> {"citations": [{"id","locator","lang","snippet","page_image",...}]}
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

9 项检查：openapi、必需端点、health、search、result shape、page image、books、toc、chapter；`--expect-auth` 再加一条"无 token 必须 401"。退出码 0 表示"插件/MCP 可用"。

## 12. MCP 包装

`packages/socratic-mcp` 把同一组能力暴露成 MCP tools（`kb_search` / `kb_read` / `chapter_lookup` / `review_session` / `socratic_state` / `socratic_health`），任何 MCP host 可直接接入，不必实现本契约的 HTTP 细节。

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
