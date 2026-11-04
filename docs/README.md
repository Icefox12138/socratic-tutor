# docs 索引

> **先读 [STATUS.md](STATUS.md)**：2026-11-03 当前状态快照；与旧报告冲突时以它和 [HANDOFF.md](HANDOFF.md) 为准。

## 1. 入口（按顺序）

| 顺序 | 文件 | 用途 |
|---:|---|---|
| 1 | [STATUS.md](STATUS.md) | **当前状态**：阶段、数字、阻塞、环境 |
| 2 | [HANDOFF.md](HANDOFF.md) | **新对话交接**：不变量、坑、下一步 |
| 3 | [DESIGN.md](DESIGN.md) | lite 主设计（先读 §0/§1.3/§6/§16/§17） |
| 4 | [DESIGN-full.md](DESIGN-full.md) | 完整版：DDL/代码/论证，按需查 |

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
| [RAG-DB-SCHEMA.md](RAG-DB-SCHEMA.md) | **数据库契约**：自建 RAG 库的形状 |
| [SPLIT-PLAN.md](SPLIT-PLAN.md) | 拆分计划：运行时 / 数据工程、docs 归属 |
| [SIDECAR-CONTRACT.md](SIDECAR-CONTRACT.md) | 插件 ↔ sidecar 的 9 组端点契约与降级规则 |
| [RELEASE-PLAN.md](RELEASE-PLAN.md) | **发布计划（双重开源）**：源码轨 + 产物轨、三个批次、资产门 |
| [ASSETS-POLICY.md](ASSETS-POLICY.md) | 截图/示例数据政策：为什么书页不能进仓库 |
| [assets/SOURCES.md](assets/SOURCES.md) | 资产来源登记（✅ 可发布 / ⛔ 阻塞） |
| [RELEASE.md](RELEASE.md) | 发布流程：PyPI 包 / DSH 插件 / MCP server / sidecar 镜像 |

合成演示语料：[samples/README.md](../samples/README.md)（5 页自制书 + 索引，零版权）。

工具：`scripts/ragdb_check.py`（不起服务，直接检查配置指向的库）、`scripts/contract_check.py`（对任意 URL 跑 9 项契约检查）、`scripts/publish_lint.py`（发布前查 license/绝对路径/密钥/数据文件）。
| [P2-5-embedded-ui.md](P2-5-embedded-ui.md) | DSH 内嵌教学台 + K5 页图引用 |
| [REVISION.md](REVISION.md) | 2026-11-03 全面修订记录 |
| [NEW-PTC-SESSION.md](NEW-PTC-SESSION.md) | 新 PTC 会话开场模板 |

## 5. 阅读原则

- 先 STATUS，再 HANDOFF；不要从旧报告开头读结论。
- 旧报告保留当时结论；被后续实验推翻的，在报告头部加“后续状态”注记。
- 新实验写 `eval/p1` / `eval/p2`，不要改历史数字。
- 报告日期统一用绝对日期；不要写“今天/昨天”。
