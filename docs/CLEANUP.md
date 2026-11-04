# 非文档内容的复用与清理建议

| 项 | 值 |
|---|---|
| 日期 | 2026-10-30 |
| 仓库体积 | 约 **2.6 GB**（`eval/` 占 2.6 GB，docs 仅 0.2 MB） |
| 结论 | 约 **2.3 GB 可再生/可清理**；保留约 **300 MB** 即可继续开发 |

> **已执行（2026-10-30）安全子集**：删除 `vectors.npy`、`__pycache__` 与 4 个临时转储；仓库 **2,598.2 → 891.5 MB**（释放 **1,706.7 MB**）。`search.db` 未动，`eval_questions.py` 复跑仍为 page recall 0.60。

---

## 1. 有复用价值（保留）

### 1.1 代码

| 路径 | 价值 |
|---|---|
| `eval/p1/ingest/ingest_steadman.py` | Steadman 入库 + transsheet 隔离 |
| `eval/p1/ingest/ingest_library.py` | 61 本文本版入库 |
| `eval/p1/ingest/build_search.py` | 合并 + bigram 索引 + 20 条评估 |
| `eval/p1/ingest/page_render.py` | 页图按需渲染 + 2 GB LRU |
| `eval/p1/ingest/quality_gate.py` | 100 条引用抽检 |
| `eval/p1/eval/gen_questions.py` / `eval_questions.py` | 100 条问句集生成/复评 |
| `eval/p1/bakeoff/run_bakeoff.py` | OCR/解析器对照 harness |
| `eval/p1/llm/stress_llm.py` / `stress_strict.py` | 50 轮 LLM 压力 |
| `plugin-probe/` | DSH 8 项能力探针 |
| `eval/p0/**/*.py` | preflight、CER、三流、页图基准 |

### 1.2 清单与证据

| 路径 | 价值 |
|---|---|
| `eval/p0/catalog/catalog.jsonl` | 905 条全库清单（sha/book_id） |
| `eval/p0/catalog/sample-manifest.json` | 20 本样本 + 窗口 + 金标页 |
| `eval/p1/ingest/*-manifest.json` | 100 卷 / 61 本逐卷指标 |
| `eval/p1/eval/questions.json` / `results.json` | 100 条问句 + 基线 |
| `eval/p1/ingest/quality-gate.json` | 100 条抽检证据 |
| `eval/p1/bakeoff/scorecard.json` | OCR 60 页基线 |
| `eval/p1/llm/trace-*.json` | 50 轮 LLM 行为证据 |
| `eval/p0/preflight.md`、`capability/api-matrix.md`、`bench/*/*.md` | P0 结论依据 |
| `docs/decisions/ADR-012/013` | 决策记录 |

### 1.3 数据

| 路径 | 处理 |
|---|---|
| `eval/p1/ingest/search.db`（296 MB） | **保留**：开发用合并索引；可重建 |
| `eval/p1/ingest/*.json` 清单 | 保留 |
| `eval/p0/catalog/hash-manifest.jsonl` | 保留（801 行） |
| `D:\Guo-Code\PDF` / `PDF-new\Steadman` / `loeb` / `teubner` | 原始语料，保留（版权卷只 personal） |

---

## 2. 可归档（不删，移出活跃目录）

| 路径 | 大小 | 理由 |
|---|---:|---|
| `eval/p0/retrieval/index.db` | 74 MB | D4 词项检索证据；BGE-M3 后不再使用，压缩归档 |
| `eval/p0/retrieval/chunks.json` | 5 MB | 同上 |
| `docs/architecture-analysis.md` | 48 KB | 历史评审 F1–F11，部分已被 P0/P1 推翻 |
| `docs/DESIGN-full.md` | 131 KB | 完整设计，保留 |
| `eval/p1/llm/sample-*.txt` | <20 KB | 抽检摘录；trace 已足够 |

---

## 3. 可清理（可再生/临时）

| 路径 | 大小 | 为什么可删 | 如何再生 |
|---|---:|---|---|
| `eval/p0/retrieval/vectors.npy` | **1,707 MB** | 4,096 维 hashed TF-IDF，D4 临时基线；BGE-M3 会替换 | 重跑 `socratic_search.py`（CPU 约 1–2 min） |
| `eval/p1/ingest/library.db` | 278 MB | 已被 `search.db` 合并；清单保留 | `ingest_library.py`（几分钟） |
| `eval/p1/ingest/steadman.db` | 156 MB | 同上 | `ingest_steadman.py`（几分钟） |
| `eval/p1/pages/` | 36 MB | 页图缓存，可重建 | `page_render.py` |
| `eval/p0/bench/*/pages/` | 25 MB | 基准页图；保留 3 张报告用图即可 | 重渲染 |
| `eval/p1/bakeoff/pages/` | ~19 MB | OCR 输入页图；`out/` 文本保留 | 重渲染 |
| `__pycache__/`、`*.pyc` | ~0.2 MB | 编译缓存 | 自动 |
| `eval/p0/catalog/conte_pages.txt` | 19 KB | 调试转储 | 可重跑 |
| `eval/p0/_notes.md` | 0.5 KB | 临时笔记 | — |
| `eval/p0/retrieval/debug_fts.py` | 0.6 KB | 一次性调试 | — |
| `eval/p1/llm/dump_turns.py` / `uncited.py` | 0.7 KB | 一次性分析 | — |
| 空白/重复缓存图 | 几 MB | 如 `A3_gold1_p177.png`（5 KB 空白）、旧 key 的 `steadman__platos...` | 重渲染 |

**预计释放：约 2.3 GB**，仓库回到 **~300 MB**（保留 search.db + 清单 + 脚本 + 证据）。

---

## 4. 仓库外 `D:\Guo-Code\_diag` 的处置

> **已执行（2026-10-30）**：8 个脚本移入 `eval/p0/scripts/`，`aeneid.xml`/`apology.xml` 移入 `eval/p0/gold/`；其余 89 个文件先归档到 `D:\Guo-Code\_diag-archive-20261030`，随后**已删除归档**（104 个文件 / 6.22 MB）；`_diag` 与归档目录均已不存在。复跑 `latin_line_cer.py` / `conte_cer.py` 仍为 **0.64% / 1.9%**。

该目录是 P0 的分析草稿区，**不在项目内**，但含关键脚本：

| 保留并移入 `eval/p0/scripts/` | 理由 |
|---|---|
| `latin_line_cer.py` / `chapter_cer2.py` / `conte_cer.py` | Loeb/Teubner CER 复现 |
| `apology_perseus.py` / `teubner_meta.py` / `pdf_probe2.py` | 基准与元数据 |
| `catalog_steadman.py` | Steadman 编目 |
| `validate_doc.py` | 文档代码块校验 |
| `aeneid.xml` / `apology.xml` | Perseus 金标（移入 `eval/p0/gold/`） |

| 可删/归档 | 理由 |
|---|---|
| `updater-ctx*.txt`、`stead_full.txt`、`latin_ctx.txt` | 临时上下文转储 |
| `C盘垃圾检查报告.md`、`清理C盘垃圾.ps1`、`cleanup-log.txt` | 与本项目无关 |
| `*.part`（`loeb/greek__L495...pdf.part`） | 未完成下载，2 MB |

---

## 5. 建议的清理顺序（不自动执行）

```powershell
# 0) 先确认 search.db 可打开、questions.json 可复评
python -u eval/p1/eval/eval_questions.py

# 1) 删最大且确定可再生
Remove-Item eval/p0/retrieval/vectors.npy

# 2) 删源库（确认 search.db 正常后）
Remove-Item eval/p1/ingest/library.db, eval/p1/ingest/steadman.db

# 3) 清缓存（保留 3 张报告用图）
Remove-Item eval/p1/pages -Recurse -Force
Remove-Item eval/p1/bakeoff/pages -Recurse -Force

# 4) 清临时文件
Remove-Item eval/p0/_notes.md, eval/p0/retrieval/debug_fts.py,
  eval/p1/llm/dump_turns.py, eval/p1/llm/uncited.py, eval/p0/catalog/conte_pages.txt
```

> 执行前先跑一次 `eval_questions.py`；若即将做 BGE-M3，保留 `search.db`，不要保留 `vectors.npy`。

---

## 9. 2026-11-03 存储回填

- 仓库文档/代码仍在 D；**大 venv 不要用“仓库体积”判断**：
  - `.venv-bge`：sidecar/BGE；
  - `.venv-ocr`：PaddleOCR CPU；
  - `.venv-paddle-gpu`：Paddle 3.0 CUDA（约 2 GB+）；
  - `.venv-mineru`：MinerU；
  - `tools/jdk17`：ODL Java 17。
- 缓存/模型已迁 D：uv/pip/PaddleX/MinerU/uv-tools；C 盘只剩 `.dsh` 和少量 Temp。
- C 盘可用约 **24 GB**；旧 Temp 已清 1.62 GB。
- **不要删**：`eval/p1/ingest/search.db`、`eval/p0/catalog/*`、`gold/`、`eval/p1/bge/*.npy`。
- 可删：`eval/p1/bakeoff/out/*` 可重跑；`.venv-*` 可重建，但重建成本高。

