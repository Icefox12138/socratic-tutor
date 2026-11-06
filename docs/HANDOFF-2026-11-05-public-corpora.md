# 公开语料接入交接（schema v2）

| 项 | 值 |
|---|---|
| 日期 | **2026-11-05** |
| 项目 | `D:\Guo-Code\socratic-tutor` |
| 范围 | v2 契约、Wikisource/CTS adapter、ingest CLI、sidecar 读取、测试、文档 |
| 状态 | **首版完成并实测**；未提交 git |
| 测试 | sidecar **192/192**（原 147 + 新 45） |
| 实测 | 史記/卷001 rev 11133934 → 6 节 28 chunks；Iliad 1.1–1.2 → 2 chunks；契约探针 CONTRACT OK |

> **后续**：v2 BGE-M3 向量/混合检索见
> [HANDOFF-2026-11-05-v2-vectors.md](HANDOFF-2026-11-05-v2-vectors.md)；
> 本文中“FTS-only”的描述已被其取代。

---

## 0. 一句话

公开语料现在有独立的 **schema v2**（documents + locator + stream + license），
第一个 adapter 是 **Wikisource**（revision 级引用），第二个是 **Perseus CTS**
（URN 级引用）；sidecar 用 `SOCRATIC_SCHEMA=auto` 自动识别库，v1 私有 PDF 路径
一行未改。

---

## 1. 交付物

### 新代码

| 文件 | 作用 |
|---|---|
| `sidecar/app/schema.py` | v2 DDL、版本检测、计数；`ensure_v2()` 幂等 |
| `sidecar/app/locators.py` | locator 联合类型：校验、URL、人读 label |
| `sidecar/app/textutil.py` | v1/v2 分词、清洗、段落切块、希腊/拉丁去重音 |
| `sidecar/app/catalog.py` | v2 只读视图：sources/documents/chunk/search 结果形状 |
| `sidecar/app/ingest.py` | 单事务写入：source/document/chunks/FTS；重灌替换 |
| `sidecar/app/adapters/base.py` | `Document`/`Section`/`SourceSpec`/`FetchError` |
| `sidecar/app/adapters/http.py` | 带 UA 的 GET、限流、JSON |
| `sidecar/app/adapters/wikisource.py` | MediaWiki `action=parse` + rendered HTML 清洗 |
| `sidecar/app/adapters/cts.py` | Perseus CTS `GetPassage` + TEI 解析 |
| `scripts/ingest_public.py` | CLI：Wikisource 标题 / CTS URN / 搜索发现 / dry-run |

### 修改

| 文件 | 变更 |
|---|---|
| `sidecar/app/config.py` | `SOCRATIC_SCHEMA`、`STUDENT_STREAMS`、`schema_version()` |
| `sidecar/app/search.py` | v2 检索分支、v2 verify、health 的 schema/documents/sources |
| `sidecar/app/main.py` | `/v1/verify` 支持 document_id/section/revision；`/v1/sources`、`/v1/documents`、`/v1/documents/{id}`；chunk/books 的 v2 分支 |
| `sidecar/app/citations.py` | 引用流水新增 `document_id`/`scheme`/`url`（自动 ALTER） |
| `plugin-socratic/client.js` | 引用卡显示“原文 ↗”（有 `citation.url` 时） |
| `plugin-socratic/index.js` | `kb_search` 接受 `document_id`/`section`；`cite_verify` 支持 v2 的 document_id/section/revision |
| `packages/socratic-mcp/socratic_mcp/tools.py` | `kb_search` schema 同步 `document_id`/`section` |
| `scripts/contract_check.py` | 接受 `fts-public`；v2 检查 scheme/url/sources |
| `scripts/ragdb_check.py` | v2 计数与 schema 输出；v2 不再要求向量/toc |

### 文档

- `docs/RAG-DB-SCHEMA-V2.md`：v2 契约（DDL、locator、stream、verify、adapter、限制）
- `docs/RAG-DB-SCHEMA.md`：顶部加 v1/v2 分流说明
- `docs/SIDECAR-CONTRACT.md`：v2 端点与 citation 形状
- `docs/STATUS.md`：测试 192、公开语料首版
- 本文件

---

## 2. 实测证据

### 2.1 真实入库

```powershell
python scripts/ingest_public.py --source wikisource --lang zh `
  --titles-file data/public-titles.txt --db data/public.db --license PD-old --rate 1
# {"document_id": "wikisource:zh:史記/卷001", "revision": "11133934",
#  "sections": 6, "chars": 4604, "chunks": 28}

python scripts/ingest_public.py --source perseus --lang greek `
  --urn urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.1 `
  --urn urn:cts:greekLit:tlg0012.tlg001.perseus-grc1:1.2 --db data/public.db
# {"document_id": "urn:cts:...perseus-grc1", "sections": 2, "chunks": 2}
```

### 2.2 检索/核验

- `q=黃帝` → 8 hits，citation：
  `《史記/卷001》黃帝（Wikisource rev 11133934）`，
  URL 带 `oldid` 与 section 锚点；
- `verify(document_id, section="黃帝", quote="黃帝者，少典之子，姓公孫，名曰軒轅",
  revision="11133934")` → `verified=true, chunks=5`；
- revision 改 `999` → `verified=false, reason="revision mismatch: indexed 11133934, asked 999"`；
- `q=θεά`（acute）命中文本里的 `θεὰ`（grave）：v2 词元做重音折叠；
- `/v1/documents/wikisource:zh:史記/卷001` → 6 节 28 chunks。

### 2.3 契约

起 sidecar（`SOCRATIC_DB=data/public.db`）后：

```
ok   health            HTTP 200 schema=v2 chunks=30
ok   search            HTTP 200 mode=fts-public
ok   citation scheme   scheme=mediawiki
ok   citation url      https://zh.wikisource.org/wiki/…
ok   sources           HTTP 200 2 sources
CONTRACT OK
```

### 2.4 测试

`python -m unittest discover -s tests -p "test_*.py"` → **192 OK**。
新增 45：schema/locator、Wikisource HTML、CTS TEI、v2 检索/端点、ingest/CLI。
`socratic-mcp` 测试 6/6 OK。plugin 测试在本机被 DSH 沙箱的 `spawn EPERM`
挡住（Node test runner 启动子进程），只做了 `node --check`；CI 会跑。

---

## 3. 关键决策

| # | 决策 | 理由 |
|---|---|---|
| 1 | **v1/v2 分库**，不自动迁移 | 引用单位不同；同一 `chunks` 表塞两套语义会互相污染 |
| 2 | v2 **首版 FTS-only** | 公开语料是干净文本；先验证词法够不够，向量后补 |
| 3 | Wikisource 解析 **rendered HTML** | 引用要能对上读者看到的文本；wikitext 模板会漏进引文 |
| 4 | 中文二元组 + 拉丁/希腊**去重音** | 希腊重音变体必须互相命中；引文原文保留 |
| 5 | CTS 用 **Tufts 旧端点** | `scaife-cts.perseus.org` 在本机 TLS SNI 被拒；旧端点仍返回 TEI |
| 6 | CTS **一次一个 URN**，`fetch_many` 合并 | 旧端点不支持 passage range |
| 7 | v2 无页图，用 `citation.url` | revision/URN 才是权威；插件显示“原文 ↗” |
| 8 | `visibility` 语义不变，新增 `stream` | 译本/注释按流隔离；`answer_key` 仍由 SQL 过滤 |

---

## 4. 边界与未做

1. 首版 v2 无 BGE/rerank（**后续已实现**，见
   [HANDOFF-2026-11-05-v2-vectors.md](HANDOFF-2026-11-05-v2-vectors.md)）；
   当时 `/health` 写 `bge: not used: v2 is FTS-only`。
2. Wikisource 清洗是启发式：已剔除 `ws-header`、导航、`mw-editsection`、
   `<sup>` 脚注、`ombox` 提示框；新模板可能漏。
3. CTS 旧端点限流/覆盖率不稳；生产前逐 edition 核对许可。
4. 没有 translation/commentary 的采集 CLI，但 schema/读取层已支持 stream。
5. 中文单字查询不命中（二元组索引固有）。
6. 人工评分仍未做；不能声称人类验证。
7. `data/public.db` 是本地样本，已 gitignore；不入库、不发布。

---

## 5. 复现命令

```powershell
cd D:\Guo-Code\socratic-tutor

# 测试（本机沙箱需要 .tmp-testenv 绕过 tempfile 的 0o700 ACL；CI 不需要）
$env:PYTHONPATH="D:\Guo-Code\socratic-tutor\sidecar;D:\Guo-Code\socratic-tutor\.tmp-testenv"
cd sidecar; ..\.venv-bge\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"

# 入库
cd ..
python scripts/ingest_public.py --source wikisource --lang zh `
  --title "史記/卷001" --db data/public.db --license PD-old

# 库自检
$env:SOCRATIC_DB="D:\Guo-Code\socratic-tutor\data\public.db"
python scripts/ragdb_check.py

# 起 sidecar（v2）
cd sidecar
$env:SOCRATIC_DB="D:\Guo-Code\socratic-tutor\data\public.db"
..\.venv-bge\Scripts\python.exe -m uvicorn app.main:app --port 8765
```

---

## 6. 下一步（按优先级）

1. **v2 向量**：把 BGE-M3 接到 v2（`embeddings` 表 + npy），先评估 FTS vs hybrid
   在公开语料上的 recall；当前没有数字，不要宣称 v2 达到 0.82。
2. **更多 Wikisource 文本**：先做目标书目的覆盖率/校对质量清单，再批量入库。
3. **OpenStax/Wikibooks**（CC BY）做 secondary/讲解层；Lean/Mathlib 只做工具。
4. **CTS 批量**：GetValidReff + 限流循环；或换可达的新 CTS 端点。
5. **混合检索**：v1 私有 PDF + v2 公开语料合并排序（当前只能二选一）。
6. **人工评分**：仍缺 2 名评分者。

---

## 7. 坑（新增）

1. `tempfile.mkdtemp()` 在 Windows + 受限令牌下会建出不可写入的目录
   （`mode=0o700` 被解释成受限 DACL）；本机用 `.tmp-testenv/sitecustomize.py`
   绕过，**不要提交这个文件**。
2. `scaife-cts.perseus.org` 在本机 `TLSV1_UNRECOGNIZED_NAME`；不要把它写死成
   唯一端点。
3. Wikisource API 必须带工具名 + 联系方式的 User-Agent，否则 403。
4. 希腊文 FTS：索引与查询都要去重音，否则 `θεά` 查不到 `θεὰ`。
5. 中文 `q` 少于 2 字在二元组索引上不命中；不要误判为“没入库”。
6. 重复入库同一 document 会替换 chunks（id 会变）；引用流水里存的是旧 chunk_id。
7. `schema.version()` 对不存在的文件返回 `none`；`/health` 走 `no_index`，不是崩溃。
