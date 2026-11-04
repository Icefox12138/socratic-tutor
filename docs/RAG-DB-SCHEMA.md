# RAG 数据库契约（schema v1）

| 项 | 值 |
|---|---|
| 版本 | **v1** |
| 日期 | 2026-11-04 |
| 适用 | `sidecar` 读取的检索数据。**由使用者自建**，不属于 socratic-tutor 仓库 |
| 实现 | `sidecar/app/search.py`（唯一读取方）、`sidecar/app/toc.py`（章回） |

---

## 0. 一句话

sidecar 只认**三样东西**：一个 SQLite 库、两个 `.npy` 向量文件、以及它们之间的行序约定。
满足本契约的数据，不论用什么 OCR、什么切块策略生成，sidecar 都能检索、引用与回页。

```
<DATA_ROOT>/
├── indexes/search.db          ← chunks 表 + chunks_fts（必需）
├── vectors/bge-vectors.npy    ← N × 1024，fp16 或 fp32（启用 BGE 时必需）
├── vectors/bge-ids.npy        ← N，int64，与 chunks.id 一一对应
└── state.db                   ← 运行时自建（会话/引用/复盘/章回），**不由使用者提供**
```

路径通过环境变量指定：`SOCRATIC_DATA`（默认 `<repo>/data`）、`SOCRATIC_DB`、`SOCRATIC_BGE_VECTORS`、`SOCRATIC_BGE_IDS`、`SOCRATIC_STATE_DB`。

## 1. `chunks` 表（必需）

```sql
CREATE TABLE chunks (
  id         INTEGER PRIMARY KEY,
  source     TEXT NOT NULL,   -- 语料来源桶：library | steadman | teubner_conte | 任意自定义
  book       TEXT NOT NULL,   -- 书标识，**相对于该书库根的路径**，如 物理\朗道…pdf
  lang       TEXT NOT NULL,   -- zh | latin | greek | en | …
  page       INTEGER NOT NULL,-- 1 起算的页码，必须能通过 /v1/pages 取到页图
  text       TEXT NOT NULL,   -- 该块的原文
  visibility TEXT NOT NULL    -- tutor | answer_key
);
```

### 列语义（每条都是硬约束）

| 列 | 约束 | 违反后果 |
|---|---|---|
| `source` | 必须匹配 sidecar 的 `pages.ROOTS` 键之一，否则页图 404 | 引用无法回页 → 违反"引用可回页 100%" |
| `book` | 相对书库根的路径，用系统分隔符 | 同上 |
| `page` | **1 起算**，且 ≤ 该书实际页数 | 页图 404 |
| `lang` | 用于检索分流与页图专用分支（`greek` 等） | 希腊文页可能被当作可 OCR 文本返回 |
| `visibility` | `answer_key` 的行**永不**进入学生视图；由 SQL 层过滤，不靠上层自觉 | 答案泄漏 |
| `id` | 稳定、唯一、从 1 连续最佳（非强制，但影响向量行序） | 向量错位 |

## 2. `chunks_fts` 全文索引（必需）

```sql
CREATE VIRTUAL TABLE chunks_fts USING fts5(text, tokenize='unicode61');
```

**关键约定：写入 `chunks_fts` 的文本必须先分词**，不能直接塞原文。

| 语言 | 分词规则 |
|---|---|
| 中文 | 连续汉字段切成**二元组**（`史记` → `史记`；`秦始皇本纪` → `秦始`、`始皇`、`皇本`、`本纪`） |
| 拉丁/希腊 | 小写单词，`[a-z]{2,}` |
| 其它 | 按原样保留 |

理由：SQLite 的 `unicode61` 不切中文，整句会被当成一个 token，查询必然 0 命中。
参考实现：`eval/p1/ingest/build_search.py` 的 `tokens()`（该脚本随数据工程迁出，但规则不变）。

`rowid` 必须等于 `chunks.id`：

```sql
INSERT INTO chunks_fts (rowid, text) VALUES (?, ?);   -- ? = chunks.id
```

## 3. 向量（启用 BGE 时必需）

| 文件 | dtype | 形状 | 含义 |
|---|---|---|---|
| `bge-vectors.npy` | float16 或 float32 | `(N, 1024)` | 第 i 行对应 `bge-ids[i]` |
| `bge-ids.npy` | int64 | `(N,)` | 必须都是 `chunks.id` 中存在的值 |

约束：

- 维度必须是 **1024**（BGE-M3）；
- **通常只覆盖 `visibility='tutor'` 的 chunk**（答案键不进向量索引，避免被相似度"检索出来"）。
  实测本机库：`chunks=167,192`，其中 `tutor=148,261`、`answer_key=18,931`，
  向量行数正好是 **148,261**；
- 归一化与否都可（sidecar 内部会归一化）；
- 行序任意，但 `ids` 必须与之对应；
- **可以只覆盖部分 chunk**（见 §5）；缺失的行在 BGE 通道里查不到，但 FTS 仍可命中。

## 4. 章回索引 `toc`（可选，但建议提供）

```sql
CREATE TABLE toc (
  source TEXT, book TEXT, ord INTEGER, level INTEGER, title TEXT,
  page_start INTEGER, page_end INTEGER, volume INTEGER,
  pages INTEGER, meta TEXT,
  PRIMARY KEY (source, book, ord)
);
```

**存放位置有坑**：`toc` 目前位于 **`state.db`**（`toc.py` 用 `config.STATE_DB`），
而 `state.db` 是运行时自建的库。若使用者要在安装时就带上章回索引，需把 `toc` 行写进
`state.db`，或按 §6 的迁移项把 `toc` 改为读 `search.db`。

`level`：1 = 卷/篇，2 = 篇/回（与 `classics-index` 的输出一致）。
`ord`：同书内递增，从 0 开始。

## 5. 最小可用与降级

| 提供情况 | sidecar 行为 |
|---|---|
| 只有 `search.db`（无向量） | `SOCRATIC_BGE=0` 或自动退回纯 FTS，检索仍可用，recall 下降 |
| 有 chunks 但无 `toc` | `/v1/toc`、`/v1/chapter` 返回 404；检索与页图正常 |
| 库存在但为空 | `/health` 显示 `chunks: 0`；检索返回空结果，**不是错误** |
| 库文件不存在 | `/health` 应报告 `no_index`（见 §6 迁移项），服务不崩 |

## 6. 拆分前必须完成的两处代码改动（**已完成**，2026-11-04）

| 改动 | 状态 | 实现 |
|---|---|---|
| `/health` 在 DB 不可用时返回 **200 + `{"ok": false, "reason": "no_index"}`** | ✅ | `main.health()` 捕获后返回 200；`/v1/search` 返回 503 + `{"code": "no_index"}` |
| `toc` 的读取来源可配置 | ✅ | `SOCRATIC_TOC_IN=state\|search` 或 `SOCRATIC_TOC_DB=<path>`，见 `config.toc_db()` |

副作用：`scripts/contract_check.py` 现在把"无索引"视为**可接受状态**（打印 SKIP 并继续检查服务面），
需要强制要求数据时加 `--require-data`。

## 7. 自检清单

建好库后，按顺序验证：

```bash
# 1) 结构
sqlite3 search.db "SELECT count(*) FROM chunks; SELECT count(*) FROM chunks_fts;"
# 期望：两行数字相等

# 2) 中文可检索（二元组分词生效）
sqlite3 search.db "SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH '秦始';"
# 期望：> 0

# 3) 向量对得上
python -c "import numpy as np; v=np.load('vectors/bge-vectors.npy'); i=np.load('vectors/bge-ids.npy'); print(v.shape, i.shape, v.shape[0]==i.shape[0])"

# 4) 端到端（起 sidecar）
python scripts/contract_check.py --base http://127.0.0.1:8765 --query <库里必有的词>
# 期望：CONTRACT OK
```

## 8. 版本

本文件描述 **schema v1**。破坏性变更（增删列、改语义）必须升版本，并在 sidecar 侧同步。
建议在库中记录版本：

```sql
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
INSERT OR REPLACE INTO meta VALUES ('rag_schema', 'v1');
```
