# RAG 数据库契约（schema v2：公开语料）

| 项 | 值 |
|---|---|
| 版本 | **v2** |
| 日期 | 2026-11-05 |
| 适用 | 引用单位**不是页**的语料：Wikisource / Perseus CTS / 数据集 / Lean 等 |
| 实现 | `sidecar/app/schema.py`（DDL/检测）、`catalog.py`（读取）、`ingest.py`（写入） |
| 适配器 | `sidecar/app/adapters/wikisource.py`、`cts.py` |
| v1 | 仍是私有 PDF 库的契约，见 [RAG-DB-SCHEMA.md](RAG-DB-SCHEMA.md) |

---

## 0. 一句话

v1 假设每个 chunk 都有整数 `page`；v2 把 `page` 换成**带 scheme 的 locator**，
并把“来源 / 许可 / 流”提升为一级字段。**两种契约放在两个 SQLite 文件里**，
`SOCRATIC_SCHEMA=auto|v1|v2` 选择；v1 代码路径未改。

```
<DATA_ROOT>/
├── indexes/search.db   ← v1：私有 PDF（chunks + 页图）
├── public.db           ← v2：公开语料（sources/documents/chunks + locator）
├── vectors/*.npy       ← v1 的 BGE 向量（v2 暂不使用）
└── state.db            ← 运行时状态（会话/引用/复盘/toc）
```

默认位置：CLI 用 `SOCRATIC_PUBLIC_DB` 或 `<DATA>/public.db`；sidecar 用
`SOCRATIC_DB` 指向要读的那个文件。**不要把 v2 表写进 v1 库**：
`scripts/ingest_public.py` 检测到 v1 会直接拒绝。

## 1. 何时用 v1 / v2

| 场景 | 契约 | 理由 |
|---|---|---|
| 自扫/公版 PDF，引用回到页图 | **v1** | `page` + `/v1/pages` 已经够 |
| Wikisource / CTS / 数据集 / Lean | **v2** | 引用单位是 revision / URN / 声明，不是页 |
| 想混排 | 先各建一个库；检索合并是下一步工作 | 同一文件里两套 `chunks` 语义会互相污染 |

## 2. DDL

```sql
CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT);  -- rag_schema = v2

CREATE TABLE sources (
  source_id      TEXT PRIMARY KEY,       -- wikisource:zh / perseus / ...
  adapter        TEXT NOT NULL,          -- mediawiki | cts | ...
  base_url       TEXT,
  auth_env       TEXT,
  rate_limit     REAL,
  license        TEXT,
  redistribution TEXT,                   -- allowed | share-alike | forbidden | unknown
  enabled        INTEGER NOT NULL DEFAULT 1,
  config_json    TEXT
);

CREATE TABLE documents (
  document_id   TEXT PRIMARY KEY,        -- wikisource:zh:史記/卷001 / urn:cts:...
  source_id     TEXT NOT NULL REFERENCES sources(source_id),
  title         TEXT NOT NULL,
  author        TEXT,
  edition       TEXT,
  lang          TEXT,                    -- zh-classical | latin | greek | en
  script        TEXT,
  license       TEXT,
  provenance    TEXT,                    -- 站点 + 标题 + revision
  canonical_url TEXT,
  metadata_json TEXT
);

CREATE TABLE chunks (
  id             INTEGER PRIMARY KEY,
  document_id    TEXT NOT NULL REFERENCES documents(document_id),
  ordinal        INTEGER NOT NULL,       -- 文档内连续，从 0 开始
  section        TEXT,                   -- 章节标题（可空）
  text           TEXT NOT NULL,
  lang           TEXT,
  stream         TEXT NOT NULL DEFAULT 'text',   -- text|translation|commentary|apparatus
  visibility     TEXT NOT NULL DEFAULT 'tutor',  -- tutor|answer_key
  locator_json   TEXT NOT NULL,
  citation_label TEXT,                   -- 人读标签；空则按 locator 生成
  quality        TEXT,
  char_start     INTEGER,                -- 相对 section 的字符区间
  char_end       INTEGER,
  source_version TEXT                    -- revision / URN / dataset version
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(text, tokenize='unicode61');

CREATE TABLE assets (asset_id TEXT PRIMARY KEY, document_id TEXT, chunk_id INTEGER,
                     type TEXT, uri TEXT, rights TEXT, metadata_json TEXT);
CREATE TABLE embeddings (chunk_id INTEGER, model TEXT, dim INTEGER, version TEXT,
                         PRIMARY KEY (chunk_id, model));
```

`chunks_fts.rowid` 必须等于 `chunks.id`；写入的文本**先分词**（见 §9）。

## 3. locator_json（联合类型）

```json
{"scheme":"mediawiki","site":"zh.wikisource.org","title":"史記/卷001",
 "revision":"11133934","section":"黃帝","section_index":1,
 "char_start":0,"char_end":601}

{"scheme":"cts","urn":"urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.1",
 "work":"urn:cts:greekLit:tlg0012.tlg001.perseus-grc1","book":"1",
 "line_start":1,"line_end":1}

{"scheme":"pdf_page","page":12,"bbox":[0.1,0.2,0.8,0.9]}
{"scheme":"dataset","dataset":"theoria","split":"train","id":"..."}
{"scheme":"lean","module":"Mathlib...","decl":"Real.sin","mathlib_rev":"e6bd550"}
{"scheme":"ia","item":"...","file":"...","page":42}
```

| scheme | 必需键 | verify 依据 |
|---|---|---|
| `mediawiki` | `site`, `title`, `revision` | 该文档/章节的已存文本 + revision 匹配 |
| `cts` | `urn` | 该 URN 的已存文本 |
| `pdf_page` | `page` | v1 页内文本（或页图） |
| `dataset` | `dataset`, `id` | 记录 ID 对应文本 |
| `lean` | `module`, `decl` | 声明（工具，不进 chunks 也可） |
| `ia` | `item`, `page` | item/file 页文本 |

`locator_json` 由 `sidecar/app/locators.py` 生成、校验、拼 URL；
**缺必需键的 locator 会在入库时被拒绝**（`LocatorError`），不会静默写坏引用。

## 4. 流与可见性（硬约束）

| 请求 | 返回的 chunk |
|---|---|
| `view=student` | `visibility='tutor'` **且** `stream IN (SOCRATIC_STUDENT_STREAMS)`（默认 `text`） |
| `view=tutor` | `visibility='tutor'`，所有 stream |
| 任何 view | `visibility='answer_key'` **永不**返回；由 SQL 过滤，不靠提示词 |

公开语料的译本/注释/校勘记应写成 `stream='translation'|'commentary'|'apparatus'`，
默认只给导师看。`answer_key` 语义与 v1 相同。

## 5. citation 形状

搜索/读片段返回：

```json
{
  "chunk_id": 12,
  "document_id": "wikisource:zh:史記/卷001",
  "source": "wikisource:zh",
  "book": "史記/卷001",
  "lang": "zh-classical",
  "page": null,
  "section": "黃帝",
  "stream": "text",
  "positions": {"char_start": 0, "char_end": 601},
  "bbox": null,
  "text": "黃帝者，少典之子……",
  "score": 0.83,
  "similarity": 0.83,
  "citation": {
    "scheme": "mediawiki",
    "locator": "《史記/卷001》黃帝（Wikisource rev 11133934）",
    "label": "…同上…",
    "url": "https://zh.wikisource.org/wiki/史記/卷001?oldid=11133934#黃帝",
    "image": null,
    "page_image": null,
    "tier": "A",
    "license": "PD-old",
    "document_id": "wikisource:zh:史記/卷001",
    "revision": "11133934"
  }
}
```

- `page_image` 在 v2 恒为 `null`；用 `url` 打开原文。插件会显示“原文 ↗”。
- `citation.locator` 与 `label` 同值，保留社区别名。
- `tier` 是可信度层（公开校对本 = `A`）；`license` 来自 source/document。

## 6. verify（引用闸门）

```
GET /v1/verify?quote=...&document_id=...&section=...&revision=...
GET /v1/verify?quote=...&book=...&page=...          # v1，保持不变
```

- 先做文本归一化（小写、去标点/空白）再整段包含匹配；
- 给 `revision` 时必须与索引里的 revision 一致，否则
  `verified=false, reason="revision mismatch: ..."`；
- `section` 可选，用于把匹配范围收窄到一章；
- 页图不是 v2 的必要条件：v2 的权威是 revision 对应的文本。

## 7. 端点

| 端点 | 说明 |
|---|---|
| `/v1/search?q=&document_id=&section=&source=&lang=&view=` | v2 返回 `schema:"v2"`, `mode:"fts-public"` 或 `"bge+rerank-public"` |
| `/v1/sources` | `sources` 列表（adapter/许可/再分发/限流） |
| `/v1/documents?source=&lang=&limit=&offset=` | 文档列表，不含正文 |
| `/v1/documents/{document_id}` | 元数据 + 章节列表 + chunk 数（id 里可有 `/`） |
| `/v1/chunks/{id}` | 单片段；v2 含完整 citation |
| `/v1/verify` | §6 |
| `/health` | v2 时 `schema:"v2"`, `documents`, `sources`, `bge:"disabled|lazy|loading|ready|missing: …|error: …"` |

`book` 在 v2 里表示文档标题（也接受 `document_id` 精确值）；
`chapter` 是 `section` 的旧别名。

## 8. 适配器

### Wikisource（`adapter=mediawiki`）

- 端点：`https://<lang>.wikisource.org/w/api.php`，只用 `action=parse`
  （渲染后的 HTML），不爬 `action=raw`，不绕限流；
- 引用单位：**页面标题 + revision（oldid）**；`section` 来自 HTML 标题；
- 许可：站点默认 `CC-BY-SA-4.0`；公版古籍可在 CLI 用 `--license PD-old` 覆盖；
- User-Agent：必须带工具名与联系方式（Wikimedia 政策），默认见
  `adapters/http.default_user_agent()`，可用 `SOCRATIC_HTTP_UA` 覆盖；
- 限流：默认 1 请求/秒（`--rate`）；
- 清洗：丢弃 `ws-header`、导航框、`mw-editsection`、脚注 `<sup>`、`ombox`
  提示框；保留正文/表格文本；
- 失败：`missingtitle` 等 API error → `FetchError`，不入库。

### Perseus / CTS（`adapter=cts`）

- 端点：`https://www.perseus.tufts.edu/hopper/CTS`（旧 CTS，稳定可达）；
  `scaife-cts.perseus.org` 在部分网络 TLS SNI 被拒，仅作备选；
- **旧端点不支持 passage range**：一次一个 URN；`fetch_many()` 把多个 URN
  合并成一个 document（同一 edition）；
- 引用单位：CTS URN（work/book/line）；`document_id` 是 edition 级 URN；
- 元数据：`title`/`groupname`/`versionInfo` 从响应读取；
- 许可：Perseus 文本逐 edition 不同，默认 `CC-BY-SA-4.0`，接生产前逐条核对。

## 8b. 向量与混合检索（v2）

v2 向量是**可选增强**：没有向量时退回 FTS，服务不报错。

```
<DATA>/vectors/public-vectors.npy   (N, 1024) float16，L2 归一化
<DATA>/vectors/public-ids.npy       (N,) int64，与 chunks.id 一一对应
```

- `embeddings` 表记录 `(chunk_id, model, dim, version)`；v2 只对
  `visibility='tutor'` 的 chunk 编码，`answer_key` 不进向量。
- 构建/增量更新：

```powershell
python scripts/embed_public.py --db data/public.db --device cuda
# 默认增量：保留已有向量、只编码新 chunk、剪掉已删除 chunk 的孤儿向量
python scripts/embed_public.py --db data/public.db --rebuild   # 全部重算
python scripts/embed_public.py --db data/public.db --dry-run   # 只看缺口
```

- 环境变量：`SOCRATIC_V2_VECTORS` / `SOCRATIC_V2_IDS`（文件路径）、
  `SOCRATIC_V2_BGE_MODEL`（默认同 `SOCRATIC_BGE_MODEL`）、
  `SOCRATIC_V2_MODEL_NAME`（默认 `bge-m3`）、`SOCRATIC_V2_EMBED_VERSION`。
- sidecar：`SOCRATIC_BGE=1`（默认）时懒加载 BGE-M3 + reranker。
  检索顺序：FTS top50 + BGE top50 → RRF（k=60）→ rerank top50 → top N；
  `view=student` 的 stream 过滤在 rerank 之前完成。
- 失败降级：向量文件缺失/损坏、模型加载失败 → `mode:"fts-public"`，
  `/health` 的 `bge` 写明 `missing:`/`error:`；首次成功检索后变 `ready`。
- 向量在首次查询/启动预热时载入内存；重新编码后需重启 sidecar，没有热重载。
- 实测（30 chunks，4060 8 GB）：首查 **7.3 s**（含模型加载），
  热查 **0.33–0.39 s**；`黄帝`/`轩辕`/`尧舜禅让` 在 FTS 上 0 命中，
  混合检索能回到 `黃帝`/`帝舜` 节；英文 `Achilles` 能回到 `Iliad 1.1`。
- 局限：BGE 单通道对中文→希腊/拉丁的纯语义仍弱；跨语言主要靠
  8c 的查询翻译通道，不要指望 BGE 单独解决。

## 8c. 查询翻译（可选）

中文问题与希腊/拉丁原文几乎没有共享词元。翻译层只在**检索前**把问题扩成
检索变体，不进入答案、不作为引用证据。

- 提供方：`SOCRATIC_TRANSLATE=auto|glossary|llm|off`
  - `auto`（默认）：离线词表 + **仅对 OOV 调 LLM**；命中中国史人物/制度词
    （约 50 个标记）的问题不调 LLM。无 LLM key 时等价于 `glossary`。
  - `glossary`：只用离线词表 `sidecar/app/glossary.json`（64 条，含希腊/
    拉丁词形变化、简繁别名）；确定性、无网络。
  - `llm`：始终调 LLM（OpenAI 兼容端点，默认 DeepSeek）；失败时无变体。
  - `off`：不翻译。
- OOV 判定：词表命中片段挖掉、去虚词后，剩余 CJK ≥2 字或 ≥3 字母的词；
  例：`克鲁塞斯`/`银弓之神` 是 OOV，`阿喀琉斯的愤怒` 不是。
- LLM 配置：`SOCRATIC_LLM_BASE` / `SOCRATIC_LLM_MODEL` / `SOCRATIC_LLM_KEY`
  （或 `DEEPSEEK_API_KEY`）；超时 `SOCRATIC_TRANSLATE_TIMEOUT`（默认 6 s）。
- 检索融合：原始查询权重 1.0；中文别名变体 0.8；词表变体
  `SOCRATIC_TRANSLATE_WEIGHT`（默认 1.5）；LLM 变体
  `SOCRATIC_TRANSLATE_LLM_WEIGHT`（默认 1.0，只补召回不抢 top-1）。
  默认原查询走 BGE+rerank，翻译变体走 FTS
  （`SOCRATIC_TRANSLATE_BGE=1` 可让变体也走 BGE）。
- 响应新增：`translated: bool`、`translations: [{lang,text,source}]`。
- 评估（130 人工题 / 7 书 / 331 chunks）：fts R@5 **0.577**、fts+词表 **0.762**、
  bge **0.892**、bge+词表 **0.938**、**bge+auto 0.977**（R@1 0.838）。
  未知词表 8 问 bge+词表 0.625 → bge+auto **1.000**。
  历史 43 问/130 自动集数字见 `eval/public/RESULTS*.md`。

## 8d. 词法通道（grep / lemma）

精确串与词形归并是 v2 的**补充通道**，不替代 FTS/BGE：

```http
GET /v1/grep?q=...    # 原样子串；v1/v2 都可
GET /v1/lemma?q=...   # 希腊/拉丁变格归并；仅 v2
```

- `grep` 返回 `match={start,end,snippet,count}`；用于引文、人名、公式、标识符。
- `lemma` 优先用 `simplemma`（可选依赖 `.[lemma]`），缺失时用后缀词干；
  返回 `match={coverage,lemmas,exact}`。
- v2 `search()` 默认把它们作为额外 RRF 列表：grep 权重 2.0、lemma 1.3
  （`SOCRATIC_LEXICAL=auto|off`，响应带 `"lexical":{"grep":n,"lemma":n}`）。
- 评估（12 条变格查询，形式不是原文子串）：FTS R@5 0.083、grep 0、
  lemma 0.917（降级）/ **1.000**（simplemma）。
- 详见 [LEXICAL-SEARCH.md](LEXICAL-SEARCH.md)。

## 9. 分词与切块

| 语言 | 写入 `chunks_fts` 的词元 |
|---|---|
| 中文 | 连续汉字的**二元组**（`史記`→`史記`；`黃帝者`→`黃帝`,`帝者`） |
| 拉丁/希腊 | 小写词，长度 ≥2；**先去重音**（`θεὰ`/`θεά` → `θεα`，`confectō`→`confecto`） |

- v2 用 `textutil.tokens_v2()`；v1 的 `tokens()` 原样保留，避免影响 167k 旧索引。
- 希腊/拉丁去重音是检索层的折叠；**存进 `chunks.text` 的引文保留原重音**。
- 切块：按段落，目标 ≤1200 字符；超长段落按句末切，再按硬长度切。
- 中文单字查询（<2 字）在二元组索引上不命中；需要时用两字以上查询。

## 10. 入库

```powershell
# Wikisource：一页/多页
python scripts/ingest_public.py --source wikisource --lang zh `
  --title "史記/卷001" --db data/public.db --license PD-old

# 从文件读标题（UTF-8，一行一个）
python scripts/ingest_public.py --source wikisource --lang zh `
  --titles-file data/public-titles.txt --db data/public.db

# 先搜索再入库
python scripts/ingest_public.py --source wikisource --lang zh `
  --query "史記 五帝" --db data/public.db

# Perseus：多段合并成一个文档
python scripts/ingest_public.py --source perseus --lang greek `
  --urn urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.1 `
  --urn urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.2 `
  --db data/public.db

# 只抓取、不写库
python scripts/ingest_public.py ... --dry-run
```

- 重复入库同一 `document_id` 会**替换**旧 chunks（先删 FTS 行，再删 chunks），
  不会留下旧 revision 的文本；
- 检测到目标文件是 v1 库时拒绝写入，要求换 `--db`；
- 入库是单事务：抓取失败不会留下半个文档。

## 11. 与 v1 的兼容

- `SOCRATIC_SCHEMA=auto`（默认）按文件检测；`v1`/`v2` 可强制；
- v1 的 `chunks`/`chunks_fts`/`toc`/页图/向量代码路径未改；
- v2 不读 `toc`；章节来自 `chunks.section`；
- 不做自动迁移：v1 → v2 需要重新入库（引用单位不同，不能无损转换）。

## 12. 已知限制 / 未做

1. **v2 向量是可选层**：默认 FTS；建了向量才走 `bge+rerank-public`。
   中文→希腊/拉丁的跨语言语义仍偏弱，需要翻译通道，不能只靠 BGE。
2. CTS 旧端点不支持 range；长篇入库需要逐段 URN 循环，注意限流。
3. Wikisource 清洗是基于 rendered HTML 的启发式；新模板可能出现漏网文本，
   入库后应抽查 `citation_label` 与首段。
4. 许可需要逐文本核实：`--license` 默认值只是站点级默认，不是逐书结论。
5. 没有 `stream=translation/commentary` 的采集 CLI；需要时先手工入库或扩展 adapter。
6. 中文单字查询不命中（二元组索引的固有限制）。

## 13. 自检

```powershell
# 结构/计数/许可/向量对齐
$env:SOCRATIC_DB="D:\Guo-Code\socratic-tutor\data\public.db"
python scripts/ragdb_check.py

# 建/补向量
python scripts/embed_public.py --db data/public.db --device cuda

# 起 sidecar 后探契约（v2 会检查 citation.scheme/url 与 /v1/sources）
python scripts/contract_check.py --query 黃帝

# 直接查库
sqlite3 data/public.db "SELECT document_id, count(*) FROM chunks GROUP BY 1;"
sqlite3 data/public.db "SELECT citation_label FROM chunks LIMIT 3;"
```
