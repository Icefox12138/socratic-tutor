# P1-2 文本版入库 + `main_text_share`

| 项 | 值 |
|---|---|
| 日期 | 2026-10-30 |
| 输入 | 馆藏 61 本文字版（`cpp ≥ 200`，25,839 页） |
| 输出 | `library.db`（FTS5 trigram）、`library-manifest.json`；Steadman manifest 增加 `main_text_share` |
| 结论 | **PASS（带一条重要限制）**：61 本入库、10/10 查询命中；2 字中文查询需 LIKE 兜底 |

## 1. 入库规模

| 指标 | 值 |
|---|---:|
| 书 | 61（中文 56 / 英文 5） |
| 总页数 | 25,839 |
| 有文本页 | 24,142（93.4%） |
| chunks | **87,566** |
| 索引体积 | 278.1 MB |

累计（含 P1-1）：**165,386 chunks / 33,795 有文本页**。

## 2. 关键限制：trigram 不匹配 2 字中文

FTS5 `trigram` 要求查询 ≥3 字符。实测 8 条查询只命中 2 条：

- `帝国主义`、`剩余价值`（4 字）→ 命中；
- `微分`、`极限`、`矩阵`、`函数`、`资本`、`革命`（2 字）→ **0 命中**。

加 `LIKE '%q%'` 兜底后 **10/10 命中**（`微分/极限/矩阵/函数/资本/革命/帝国主义/剩余价值/导数/商品`）。

处置：

- P1 检索服务对 `<3` 字符查询走 `LIKE`（87k chunks 下可接受）；
- P1-3 建索引时改 **CJK bigram**（2 字 token）或双索引（trigram + bigram），从根上解决。

## 3. Steadman `main_text_share`

按字体 + Unicode 分类，抽样 5 页/卷：

| 指标 | 值 |
|---|---:|
| 卷数 | 100 |
| `main_text_share ≥10%` | **52** |
| `commentary_only`（<10%） | **48** |
| `platos-apology` | 0.475 |
| `collegevergil` | 0.0 |
| `livy` | 0.0 |

结论：**近一半 Steadman 卷没有可教学的主文本**（注释/词表/工作表）。P1-3 排课时只对 52 卷排“原文精读”；其余只做词表/注释/练习。

## 4. 产物

- `library.db`（61 本，87,566 chunks）、`library-manifest.json`（逐书 pages/text_pages/chars/book_id/lang）
- `library-queries.json`（10 条，10 命中）
- `steadman-manifest.json` 已加 `main_text_share` / `main_text_counts` / `commentary_only`
- 脚本：`ingest_library.py`、`query_library.py`、`main_text_share.py`、`stats_library.py`

## 5. 下一步

P1-3：把 `steadman.db` + `library.db` 合并进 `socratic-search`，加 BGE-M3 + bigram，复跑 D4 的 20 条查询。
