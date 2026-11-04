# P1-1 Steadman 入库报告

| 项 | 值 |
|---|---|
| 日期 | 2026-10-30 |
| 输入 | `D:\Guo-Code\PDF-new\Steadman`：100 PDF / 9,890 页 |
| 输出 | `steadman.db`（SQLite FTS5 trigram）、`steadman-manifest.json` |
| 结论 | **PASS**：100 卷入库；8/8 查询命中；transsheets 已隔离为 `answer_key` |

## 1. 入库规模

| 指标 | 值 |
|---|---:|
| 卷数 | 100（希腊 52 / 拉丁 48） |
| 总页数 | 9,890 |
| 有文本页 | 9,653（97.6%） |
| chunks | **77,820** |
| `tutor` chunks | 58,890 |
| `answer_key` chunks | 18,930 |
| 索引体积 | 156.3 MB |

## 2. 关键发现：transsheets 是答案

Steadman 目录中有 **33 卷 `*transsheet*`**（翻译工作表/答案页）。它们含对照译文，若按普通文本入库，等于把答案放进学生可检索区。

处置：按文件名 `transsheet` 判定，整卷 `visibility=answer_key`，检索默认 `WHERE visibility='tutor'`。**18,930 chunks 被隔离**。

这是 P1-1 最重要的产出：不是“灌了多少”，而是“灌的时候有没有把答案挡住”。

## 3. 检索抽测

| 语言 | 查询 | 命中 |
|---|---|---:|
| 希腊 | Ἀπολογία / μῆνιν / ἄνδρα / πόλεμος | **4/4** |
| 拉丁 | arma / Dido / Aeneas / bellum | **4/4** |

FTS5 trigram 对 polytonic 希腊语与拉丁语均可检索；引用带 `volume/page`。

## 4. `text_share` 的口径问题

100 卷 `text_share` 全部 ≥10%，因为 Steadman 的注释/词表/导言本身就有文字层。但 **K2 College Vergil、K4 Livy 的“原文流”为 0**（P0 D14 实测）。

因此：

- `text_share` 只能判断“有没有文字层”，不能判断“有没有原文”；
- P1-2 需补 `main_text_share`（按字体/三流分类），`main_text_share < 10%` 的卷标 `commentary_only`，教学时不排原文，只做词表/注释。

## 5. 产物

`steadman.db`、`steadman-manifest.json`（100 卷，含 pages/text_pages/chars/text_share/sha256/status）、`steadman-queries.json`、`ingest_steadman.py`、`stats_steadman.py`。

## 6. 下一步

- P1-2：61 本文本版入库 + 补 `main_text_share`；
- P1-3：把 `steadman.db` 换成 BGE-M3 向量 + RRF，复跑 D4 的 20 条查询。
