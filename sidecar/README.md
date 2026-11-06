# sidecar（最小服务，v0.2.0）

只做四件事：`/health`、`/v1/search`、`/v1/pages`、`/v1/compute`。

检索默认走 **FTS bigram + BGE-M3 + bge-reranker**；模型不可用时自动退回 FTS。

浏览器教学台：**http://127.0.0.1:8765/ui**（引用卡、提示级别、页图回看、掌握度）。

## Docker（配套服务）

```bash
# 在仓库根目录
docker compose up --build
# 或
docker build -t socratic-sidecar:0.2.0 .
docker run -p 8765:8765 -v "$PWD/data:/data" -v "$PWD/samples/PDF:/books:ro" \
  socratic-sidecar:0.2.0
```

镜像不带书、不带 BGE 权重；默认 `SOCRATIC_BGE=0`，需要 BGE 时挂载模型并设
`SOCRATIC_BGE=1`。`/data` 必须可写（SQLite journal、state.db、页图缓存）。

## 运行

```powershell
cd D:\Guo-Code\socratic-tutor\sidecar
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

若要用 BGE/rerank，必须用带 torch 的 `.venv-bge`：

```powershell
& 'D:\Guo-Code\socratic-tutor\.venv-bge\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

可选环境变量：

| 变量 | 默认 | 说明 |
|---|---|---|
| `SOCRATIC_DB` | `eval/p1/ingest/search.db` | chunks 索引 |
| `SOCRATIC_ROOT` | `D:\Guo-Code` | PDF 根 |
| `SOCRATIC_CACHE` | `sidecar/cache/pages` | 页图缓存 |
| `SOCRATIC_TOKEN` | 空 | 非空时要求 `X-Sidecar-Token` |
| `SOCRATIC_REQUIRE_AUTH` | `0` | `1` 时无 token 配置直接 503 |
| `SOCRATIC_PRELOAD` | `0` | `1` 时启动后后台加载 BGE/reranker |
| `SOCRATIC_BGE` | `1` | `0` 时强制 FTS |
| `SOCRATIC_RERANK_TOPK` | `50` | 送入 reranker 的候选数 |
| `SOCRATIC_BGE_MODEL` | `models/bge-m3` | 嵌入模型 |
| `SOCRATIC_RERANK_MODEL` | `models/bge-reranker-v2-m3` | 重排模型 |
| `SOCRATIC_IMAGE_ONLY_LANGS` | `greek,grc` | 只回页图、不回文本的语言（见 §页图策略） |

## 章回索引 / 页图浏览（P3-2）

竖排扫描件没有文本层，索引从**版心**（页边书眉）的 OCR 里建：裁右侧竖条 → 取最上方短「卷」行 → 连续 ≥5 页才算一章。C1《史记》358 页得出 7 卷 + 卷首/卷末，覆盖 358/358 页。

- 建索引：`vertical_title_ocr.py` 扫整本右栏（卷眉 + 篇名）→ `build_index.py` 一次得到卷与篇（也支持 `--headers` 用单独的卷眉 pass）；结果写 `toc` 表，`level=1` 卷、`level=2` 篇；
- 浏览：`/browse`，章回列表 + ←/→ 翻页 + 150/200 dpi；
- 详见 `docs/P3-2-vertical-index.md`。

## 页图策略（K5）

希腊文命中**不返回文本**：`text` 置空，带 `image_only: true` 与 `citation.page_image`；`/v1/chunks/{id}` 同样处理，`citations` 表的 `snippet` 写空串。检索本身仍用存储文本（FTS/BGE/rerank），所以召回不受影响。

原因：本地 OCR 在 K5 上 CER 70.9–94.0%，且文本层是"希腊文 + 英文注释"混合，直接引用会造出页图不支持的引文。策略在 `app/policy.py`，可用 `SOCRATIC_IMAGE_ONLY_LANGS` 覆盖或清空回退。详见 `docs/P1-3c-K5-pageimage.md`。

## 检索性能（4060 8 GB）

| 项 | 实测 |
|---|---:|
| 首次查询（加载模型） | ~8.6 s |
| 预热后 p50 | ~700 ms |
| 预热后 p95 | ~830 ms |
| **缓存命中** | **~10 ms** |
| 100 问句 page recall@10 | **0.80–0.82**（选择性翻译；默认关闭） |
| 中文 / 拉丁 / 希腊 / 英文 | 93% / 70% / 42–58% / 70% |

缓存：`/v1/search` 按 `(query,view,limit,source,lang,BGE)` 缓存，TTL 300 s、LRU 256；命中仍会写 `citations`。管理端点 `/v1/cache`、`POST /v1/cache/clear`，健康检查含 `cache` 统计。

说明：0.80–0.82 需要 `SOCRATIC_V1_RETRIEVAL=1` + LLM key；默认路径仍约 0.76。
v2 公开语料 130 人工题的 R@5 为 0.977（见 `eval/public/RESULTS-project.md`）。

## 端点

| 方法 | 路径 | 参数 |
|---|---|---|
| GET | `/health` | — |
| GET | `/v1/search` | `q`, `view=student\|tutor`, `limit`, `source?`, `lang?`, `book?`, `chapter?` |
| GET | `/v1/chunks/{id}` | `view` |
| POST | `/v1/review` | `{session_id, state?, answers?, record?}` → 复盘报告（P3） |
| GET | `/v1/books` | 有章回索引的书 |
| GET | `/v1/toc` | `source`, `book` → 章回索引 + 总页数（P3-2） |
| GET | `/v1/chapter` | `book`, `q` 或 `page` → 章回 + 页码范围 + 页图（P3-6） |
| GET | `/browse` | 页图浏览页（章回列表 + 翻页） |
| GET | `/v1/pages` | `source`, `book`, `page`, `dpi`, `bbox?` |
| POST | `/v1/compute` | `{expression, operation, variable, point}` |
| POST | `/v1/state/init` | `{session_id, goal, concept, lang}` |
| POST | `/v1/state/step` | `{session_id, event, result?}` |
| GET | `/v1/state/{id}` | 状态 + 摘要 |
| GET | `/v1/state/{id}/events` | 事件日志 |
| POST | `/v1/state/{id}/replay` | 从事件重建状态 |
| POST | `/v1/classify` | `{text}` → 提问类型/是否多问 |
| POST | `/v1/evaluate` | `{question, answer, rubric?, expected?, use_llm}` |
| POST | `/v1/critic` | `{text, hint_level, has_citation}` |
| POST | `/v1/critic/rewrite` | `{text}` → 只保留第一个问句 |
| POST | `/v1/critic/citation` | `{text, mode}` → soften/mark/off |
| GET | `/v1/evaluations/{session_id}` | 判定历史 |
| GET | `/v1/citations/{session_id}` | 最近引用；`?turn=N` 按回合 |
| GET | `/v1/cache` | 命中/miss/容量/TTL |
| POST | `/v1/cache/clear` | 清空查询缓存 |
| GET | `/v1/mastery/{concept}` | BKT 掌握度 |
| GET | `/v1/mastery` | 全部概念 |
| POST | `/v1/cards` | 添加 FSRS 卡 |
| POST | `/v1/cards/{id}/review` | `{rating: again\|hard\|good\|easy}` |
| GET | `/v1/cards/due` | 到期卡 |

`view=answer_key` **不接受**；`search` 在 SQL 层过滤 `visibility`。

## 示例

```bash
curl "http://127.0.0.1:8765/health"
curl "http://127.0.0.1:8765/v1/search?q=%E5%BE%AE%E5%88%86&view=student&limit=3"
curl -X POST http://127.0.0.1:8765/v1/compute \
  -H "Content-Type: application/json" \
  -d '{"expression":"x^2","operation":"diff"}'
```

## 冒烟

```powershell
# 终端 1
python -m uvicorn app.main:app --port 8765
# 终端 2
python tests/smoke.py
```

## 边界

- 计算只接受 SymPy 表达式与白名单操作，**不执行任意 Python**；
- 页图 `book` 路径做根目录校验，防路径穿越；
- 无鉴权时只绑 `127.0.0.1`；暴露端口必须设 `SOCRATIC_TOKEN`；
- CORS 只允许 `http://127.0.0.1:*` / `http://localhost:*`（供 DSH 内嵌 UI 调用）。
- 未接 BGE/reranker；`tier` 暂为 `unknown`。
