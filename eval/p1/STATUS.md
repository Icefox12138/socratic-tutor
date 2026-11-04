# P1 执行状态

> 2026-11-03 回填：P1-6 当前 0.82；P2 已完成，当前状态见 `docs/STATUS.md`。

| 项 | 状态 | 产物 |
|---|---|---|
| P1-0 LLM 准入 | **DONE（主模型准入；critic 待补）** | `llm/p1-0-report.md`、`llm/p1-0-results*.json`、`llm/trace-*.json`、`ADR-013` |
| P1-1 Steadman 入库 | **DONE（PASS）** | `ingest/P1-1-report.md`、`ingest/steadman.db`、`ingest/steadman-manifest.json` |
| P1-2 文字版入库 | **DONE（PASS，带限制）** | `ingest/P1-2-report.md`、`ingest/library.db`、`ingest/library-manifest.json` |
| P1-3 socratic-search 合并 | **DONE（PASS；BGE-M3 挂起）** | `ingest/P1-3-report.md`、`ingest/search.db`、`ingest/search-eval.json` |
| P1-3b BGE-M3 回归 | **DONE（部分：0.72 < 0.85）** | `bge/P1-3b-report.md`、`bge/bge-results.json`、`bge/hybrid-results.json` |
| P1-3b2 Reranker/翻译 | **DONE（0.82 ≥0.80；跨语言 68.8%）** | `bge/P1-3b2-report.md`、`bge/rerank-results.json`、`bge/combined-results.json` |
| P1-4 页图/引用回看 | **DONE（PASS）** | `ingest/P1-4-report.md`、`ingest/page_render.py`、`pages/*.png` |
| P1-5 质量闸门 | **DONE（PASS）** | `ingest/P1-5-report.md`、`ingest/quality-gate.json`、`pages/*.png` |
| P1-3c OCR bake-off | **DONE（K6 Perseus Paddle 12.8%；K5 页图；公式 GPU 15×，p118 仍页图）** | `docs/P1-3c-local-report.md`、`docs/P1-3c-formula-ocr.md`、`body-scorecard.md` |
| P1-3d 解析器对照 | **DONE（PyMuPDF + ODL 2.5.17）** | `docs/P1-3d-ODL.md`、`scorecard-odl.json`、`scorecard-pymupdf.json` |
| P1-6 评估集 v1 | **DONE（基线 0.60）** | `eval/P1-6-report.md`、`eval/questions.json`、`eval/results.json` |
| Sidecar 最小服务 | **DONE（0.1.0）** | `sidecar/`、`sidecar/tests/smoke.json` |
| DSH 插件骨架 | **DONE（0.1.0）** | `plugin-socratic/`、`plugin-socratic/SMOKE.md` |

**P1-0 结论**：基线 `deepseek-chat` 未引用断言 4% 未过；加 strict 策略（事实类回合首调 `tool_choice=required`）后 50 轮 **27 次调用/25 轮、未引用 0/50、SR 100%、p95 1.98 s** → **准入主模型**。`deepseek-reasoner` 仅 20 轮；第三模型无凭据；critic 暂用规则。

**下一步**：P1-1/P1-2 入库；P1-3 换 BGE-M3；补非 DeepSeek critic 后 P2 灰度。

**P1-1 结论**：PASS。Steadman 100 卷 / 9,653 有文本页 / **77,820 chunks** 入库（希腊 52、拉丁 48）；**33 卷 transsheets 共 18,930 chunks 已隔离为 `answer_key`**；希腊/拉丁查询 8/8 命中；索引 156 MB。发现 `text_share` 只能判断“有无文字层”，不能判断“有无原文”，P1-2 补 `main_text_share`。

**P1-2 结论**：PASS（带限制）。61 本 / 24,142 有文本页 / **87,566 chunks**（中文 56、英文 5）；累计 165,386 chunks。**trigram 不匹配 2 字中文**，加 LIKE 兜底后 10/10 命中；P1-3 改 bigram。Steadman `main_text_share`：**52 卷 ≥10%，48 卷 commentary_only**；`collegevergil`/`livy` 为 0。

**P1-3 结论**：PASS（FTS bigram）。合并 167,192 chunks / 295.9 MB；D4 20 条 recall **1.00**、p95 **8.2 ms**、canary 0；2 字中文已修复。**BGE-M3 已补跑**（见 P1-3b）。

**P1-3b 结论**：部分通过。BGE-M3 fp16 在 4060 上编码 148,261 个 tutor chunks（256 tokens 844 s；512 tokens 1,209 s）。问句集：FTS 0.60 → BGE 0.64/0.65 → **混合 RRF 0.72**；中文 **93%** 达标，拉丁 55%、希腊 42%、英文 20% 未达跨语言 0.70。方向正确但不宣称达标；下一步 reranker / 查询翻译 / 按 stream 建索引。

**P1-3b2 结论**：通过（本级 ≥0.80）。Reranker 全量 0.77（108 s）；对希/拉 32 条做查询翻译后合并 **0.82**；中文 94.8%、拉丁 75%、希腊 58%、英文 50%。跨语言 68.8%，距 0.70 差 1.2 点；总体 0.82 <0.85，P1 出口门仍未完全满足。

**P1-4 结论**：PASS。`render(source, book, page, dpi, bbox)` 支持 Steadman/馆藏/Conte 三源；冷 16–134 ms、热 0.0 ms、裁剪 50 ms；2 GB LRU 缓存；引用对象 `{source,book,page,bbox,image}` 可直接回页图。

**P1-5 结论**：PASS。100 条分层抽检：**100/100 可回溯、100/100 chunk 回页**；S 级 200dpi **20/20**；p95 101 ms；热缓存 10/10；canary student 0（answer_key 18,931 条）。缓存 125 张/35.9 MB。

**P1-6 结论**：v1 建立。100 条问句级：page recall **0.600**、chunk 0.550、MRR 0.467、p95 100 ms；中文 86%、拉丁 35%、希腊 17%、英文 10%。**跨语言与语义是硬缺口**，BGE-M3（P1-3b）不是可选项。

**P1-3c 结论**：K6 拉丁用 Perseus 金标，PaddleOCR **12.8%**、Rapid 14.1%、MinerU 16.2%；K5 希腊 OCR 不可用，引用 UI 改为**页图优先**（已实测点击打开 p147）。公式 OCR 4 页 127 条 LaTeX；batch32+合并 2.7×，但 p118 内容丢失；batch32 不合并不加速，生产默认整页。OCRFlux 推迟。详见 `docs/P1-3c-local-report.md`。

**Sidecar 结论**：`/health`、`/v1/search`、`/v1/chunks`、`/v1/pages`、`/v1/compute` 已跑通；检索默认 **FTS + BGE-M3 + reranker**（`bge+rerank`），预热 p50 ~700 ms / p95 ~830 ms，100 问句 **0.76**；FTS 兜底。页图 301 KB PNG；SymPy `diff x^2=2*x`；`__import__` 400；canary 不返回 answer_key。**尚无查询翻译（0.82 只在评测脚本里）、无 Qdrant。**

**DSH 插件结论**：`dsh-socratic` 0.1.0 已装入 `tutor` profile；注册 6 个工具；headless 实测 `kb_search` 3 条、`cite_verify` 200/149,798 bytes；**`agent/pre-step` 摘要已生效**：`socratic_state` 设 `导数/L2/1` 后，下一步摘要更新为 `概念=导数；提示级别=L2；尝试次数=1`，模型能复述。**无状态机/UI；状态仅进程内 Map，重启丢失。**

**P1-3d 结论**：PyMuPDF vs ODL 2.5.17（JDK17）A1/B4 各 12 页完成。ODL 整本 A1 20.9 s（31 ms/页）、B4 11.1 s（11 ms/页）；PyMuPDF ~20 ms/页。ODL A1 文本 +46%，B4 持平；bbox 覆盖 A1 37.6% vs 33.7%、B4 32.1% vs 21.7%。**表格 TEDS 未测**（抽样页无表格金标），默认仍用 PyMuPDF。详见 `docs/P1-3d-ODL.md`。

**下一步**：P1-3b BGE-M3 重跑（单语 ≥0.85、跨语言 ≥0.70）；P1-3c 补三引擎；然后 P2。
