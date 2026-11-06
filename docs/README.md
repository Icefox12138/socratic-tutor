# docs 索引

> **先读 [STATUS.md](STATUS.md)**：2026-11-05 当前状态快照；与旧报告冲突时以它和 [HANDOFF.md](HANDOFF.md) 为准。

## 1. 入口（按顺序）

| 顺序 | 文件 | 用途 |
| ---: | --- | --- |
| 1 | [STATUS.md](STATUS.md) | **当前状态**：阶段、数字、阻塞、环境 |
| 2 | [HANDOFF.md](HANDOFF.md) | **新对话交接**：不变量、坑、下一步 |
| 3 | [HANDOFF-2026-11-06-v1-federated.md](HANDOFF-2026-11-06-v1-federated.md) | **v1 检索提升 + 统一/路由（最新代码变更）** |
| 4 | [HANDOFF-2026-11-06-lexical.md](HANDOFF-2026-11-06-lexical.md) | grep/lemma 最小闭环 + 融合 |
| 5 | [HANDOFF-2026-11-06-human-oov.md](HANDOFF-2026-11-06-human-oov.md) | 人工题 + OOV/领域闸门 |
| 6 | [HANDOFF-2026-11-06-eval-130.md](HANDOFF-2026-11-06-eval-130.md) | 130 问 / 7 书评估 + 未知词表 LLM 边际价值 |
| 7 | [HANDOFF-2026-11-05-translation-eval.md](HANDOFF-2026-11-05-translation-eval.md) | v2 查询翻译 + 43 问评估交接 |
| 8 | [HANDOFF-2026-11-05-v2-vectors.md](HANDOFF-2026-11-05-v2-vectors.md) | v2 BGE-M3 向量/混合检索交接 |
| 9 | [HANDOFF-2026-11-05-public-corpora.md](HANDOFF-2026-11-05-public-corpora.md) | 公开语料 v2 入库/adapter 交接 |
| 10 | [HANDOFF-2026-11-05-rag-strategy.md](HANDOFF-2026-11-05-rag-strategy.md) | 本轮 RAG 路线/公开语料/schema/计算后端结论 |
| 11 | [HANDOFF-2026-11-06-compute.md](HANDOFF-2026-11-06-compute.md) | 计算后端：SymPy/SciPy/pint/control/Wolfram/Lean |
| 13 | [RELEASE-2026-11-06.md](RELEASE-2026-11-06.md) | **本次发版清单：版本、产物、SHA256、tag、待上传项** |
| 14 | [DESIGN.md](DESIGN.md) | lite 主设计（先读 §0/§1.3/§6/§16/§17） |
| 15 | [DESIGN-full.md](DESIGN-full.md) | 完整版：DDL/代码/论证，按需查 |

## 2. 评审与计划

| 文件 | 用途 |
|---|---|
| [FEASIBILITY-REVIEW.md](FEASIBILITY-REVIEW.md) | P0/P1 后的可行性复核；末尾有 P2 后补记 |
| [architecture-analysis.md](architecture-analysis.md) | 历史评审 F1–F11，仅参考 |

## 3. P1 报告

| 文件 | 内容 |
|---|---|

## 4. P2 报告

| 文件 | 内容 |
|---|---|
| [P2-1-report.md](P2-1-report.md) | 状态机/L0–L5/分类器 |
| [P2-2-report.md](P2-2-report.md) | 判定器 + critic + 硬拦截 |
| [P2-3-report.md](P2-3-report.md) | BKT/FSRS |
| [P2-4-report.md](P2-4-report.md) | UI（本会话曾标 P2-4，实际 P2-5） |
| [P2-5-report.md](P2-5-report.md) | 100 段对话评估（本会话曾标 P2-5，实际 P2-6） |
| [P2-6-human-rating.md](P2-6-human-rating.md) | 20 段盲评包 + AI 预评分（人工跳过） |
| [P2-7-report.md](P2-7-report.md) | 事件溯源/回放 |
| [P2-8-PTC.md](P2-8-PTC.md) | PTC 试点（`ptc_calc`；原生注入结论已过期） |
| [P2-9-PTC-token.md](P2-9-PTC-token.md) | 原生 PTC token 对比（收口：不省 token，不默认） |
| [P3-1-review.md](P3-1-review.md) | 复盘 v1：逐条判定、8 类错误、归因、复练（86.7%） |
| [P3-6-chapter-retrieval.md](P3-6-chapter-retrieval.md) | 检索接入章回：`book`+`chapter`、扫描本回页图 |
| [OPEN-SOURCE.md](OPEN-SOURCE.md) | 开源价值评估：哪些代码可发布、哪些不能 |
| [USER-GUIDE.md](USER-GUIDE.md) | **安装与使用说明**：装包、起服务、接 Agent、排查 |
| [RAG-DB-SCHEMA.md](RAG-DB-SCHEMA.md) | **数据库契约 v1**：私有 PDF 库的形状 |
| [RAG-DB-SCHEMA-V2.md](RAG-DB-SCHEMA-V2.md) | **数据库契约 v2**：公开语料（Wikisource/CTS）、locator/stream/license、向量 |
| [LEXICAL-SEARCH.md](LEXICAL-SEARCH.md) | grep/lemma 词法通道：端点、语义、simplemma、评估 |
| [FEDERATED-SEARCH.md](FEDERATED-SEARCH.md) | `scope=all`/`routed`：合并、路由、边界 |
| [../eval/v1/RESULTS.md](../eval/v1/RESULTS.md) | v1 P1 100 问：0.760→0.820 |
| [../eval/public/RESULTS-project.md](../eval/public/RESULTS-project.md) | **项目综合评估**：v1 + v2 + 统一检索 |
| [SPLIT-PLAN.md](SPLIT-PLAN.md) | 拆分计划：运行时 / 数据工程、docs 归属 |
| [SIDECAR-CONTRACT.md](SIDECAR-CONTRACT.md) | 插件 ↔ sidecar 的 9 组端点契约与降级规则 |
| [RELEASE-PLAN.md](RELEASE-PLAN.md) | **发布计划（双重开源）**：源码轨 + 产物轨、三个批次、资产门 |
| [ASSETS-POLICY.md](ASSETS-POLICY.md) | 截图/示例数据政策：为什么书页不能进仓库 |
| [assets/SOURCES.md](assets/SOURCES.md) | 资产来源登记（✅ 可发布 / ⛔ 阻塞） |
| [RELEASE.md](RELEASE.md) | 发布流程：PyPI 包 / DSH 插件 / MCP server / sidecar 镜像 |

合成演示语料：[samples/README.md](../samples/README.md)（5 页自制书 + 索引，零版权）。

工具：`scripts/ragdb_check.py`（不起服务，直接检查配置指向的库/向量）、`scripts/contract_check.py`（对任意 URL 跑契约检查）、`scripts/ingest_public.py`（Wikisource/CTS 公开语料入库）、`scripts/embed_public.py`（v2 BGE-M3 向量增量编码）、`scripts/eval_public.py`（公开语料检索评估）、`scripts/eval_lexical.py`（grep/lemma 变格评估）、`scripts/publish_lint.py`（发布前查 license/绝对路径/密钥/数据文件）。
| [P2-5-embedded-ui.md](P2-5-embedded-ui.md) | DSH 内嵌教学台 + K5 页图引用 |
| [REVISION.md](REVISION.md) | 2026-11-03 全面修订记录 |
| [NEW-PTC-SESSION.md](NEW-PTC-SESSION.md) | 新 PTC 会话开场模板 |

## 5. 阅读原则

- 先 STATUS，再 HANDOFF；不要从旧报告开头读结论。
- 旧报告保留当时结论；被后续实验推翻的，在报告头部加“后续状态”注记。
- 新实验写 `eval/p1` / `eval/p2`，不要改历史数字。
- 报告日期统一用绝对日期；不要写“今天/昨天”。
