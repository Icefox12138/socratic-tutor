# ADR-012：检索层选型（自建 `socratic-search`）

| 项 | 值 |
|---|---|
| 状态 | **Accepted（D16 收窄 GO；自建检索进入 P1）** |
| 日期 | 2026-10-29 |
| 决策者 | 项目所有者 |
| 相关 | DESIGN.md §9–§10、§23.6；P0-PLAN D4 |

## 背景

MVP 需要一个检索层，满足：

1. `answer_key` 在 chunk 级不可见（`view` 强制），不是“调用方自律”；
2. 不引入 AGPL 传染；
3. 单机、零构建、可替换（`knowledge_search` 契约）；
4. 延迟 <1 s；能接 BGE-M3。

候选：自建 `socratic-search`（FTS5 + 向量 + RRF）与 `dsh-knowledge@0.5.2`（现成）。

## 决策

**MVP 自建 `socratic-search`；`dsh-knowledge` 降为 P4 可选**（仅在需要批量横排导入/管理 UI 时，以独立进程 + 外层 `view` 评估）。

## 证据（D4）

- 语料 5 本 / 109,229 chunks；FTS5 trigram + hashed TF-IDF + RRF。
- recall@10 = **0.95**（19/20）；p95 = **38.7 ms**；canary 在 `student`/`tutor` 下均 **0 命中**。
- `dsh-knowledge` 未安装：`allowBuilds`、22 MB 限制、模型下载、AGPL、无 chunk 级可见性；其能力不能改变隔离结论。

## 后果

**正面**：`view` 在 SQL/向量层强制；许可干净（MIT）；无 `autoRetrieve`；可直接换嵌入模型；部署零构建。

**负面**：需要自己维护约 30 h；无管理 UI；索引体积偏大（P1 换 1024d/float16 压缩）。

## 备选与回退

- 若 P4 需要批量横排：独立进程跑 `dsh-knowledge`，外层只暴露带 `view` 的 `knowledge_search`，不进程内 import。
- 若自建在 P1 达不到 recall 0.85：加 rerank / 换 BGE-M3；仍不达标则回到 §23.6 C 分支（停/修，不得用 L1 兜底）。
