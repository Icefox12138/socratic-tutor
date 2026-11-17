# 数据契约差异：数据工程的"目标契约" vs 运行时"已实现契约"

| 项 | 值 |
|---|---|
| 日期 | **2026-11-16** |
| 问题 | `rag-build` 评估出的目标契约（词典/语法/教材块，尚未实现）与 `socratic-tutor` 现有的 v1/v2 契约差在哪、影响多大 |
| 方法 | 把两边都变成**可枚举清单**再对差，不比较散文 |
| 工具 | `scripts/schema_check.py --db <库> --proposed`（只读，可复跑） |

---

## 1. 为什么不能"读文档对文档"

两份文档用的词不同、颗粒度不同（数据侧按"画像"，运行时侧按"表/列/枚举"），直接比会
漏掉最关键的一层：**同一个缺口，在运行时的拦截位置不同，后果完全不同**。

运行时有三个层次的"闸"：

| 闸 | 位置 | 行为 | 缺口在这里意味着 |
|---|---|---|---|
| **硬拒绝** | `locators.validate()` | 未知 scheme / 缺必需键 → 抛 `LocatorError` | 数据**根本进不了库** |
| **读时过滤** | `catalog._meta_ok` / `search._v2_meta_ok` | `stream` 不在 `STUDENT_STREAMS` → 直接不可见 | 数据进得来，但**查不到**（静默） |
| **无此概念** | `documents` 表 | 没有 `kind` 列 | 数据进得来，**语义丢失**，规则选不中 |

`chunks.stream` 在 v2 DDL 里**没有 CHECK 约束**——所以"枚举不够"不是写入被拒，而是
写入成功、读取时被静默过滤。这是本评估最重要的一条：**缺口不都是同一类错误**。

## 2. 已实现契约（以代码为准，不以文档为准）

来源：`sidecar/app/schema.py`（DDL）、`locators.py`（白名单与必需键）、`config.STUDENT_STREAMS`、
`citation_policy.py`（source → tier/role/locator_scheme）。

| 维度 | 已实现 | 执行点 |
|---|---|---|
| 表 | `sources` / `documents` / `chunks` / `assets` / `embeddings` / `schema_meta` / `chunks_fts` | DDL |
| `documents` 列 | `document_id, source_id, title, author, edition, lang, script, license, provenance, canonical_url, metadata_json` | DDL（**无 `kind`**） |
| `chunks.stream` 文档值 | `text \| translation \| commentary \| apparatus` | 仅注释；**无 CHECK** |
| 学生可见流 | `SOCRATIC_STUDENT_STREAMS`，默认 `text` | `search._v2_meta_ok`、`catalog._meta_ok` |
| locator scheme | `pdf_page, mediawiki, cts, lean, dataset, ia` | `locators.SCHEMES` |
| locator 必需键 | 见 `locators.REQUIRED` | `locators.validate()` 硬拒绝 |
| 策略侧 scheme | `citation_policy` 的 source 记录 `locator_scheme` | 规则校验 |

## 3. 目标契约（数据工程评估结论）

来源：`rag-build/docs/CORPUS-PROFILES.md` §6.2（D1 词典、G1 语法、T2/T3/T4 教材块）、
`DICTIONARY-GRAMMAR-PIPELINE.md`、`EXPERIMENT-PLAN.md` E7/E8。

| 维度 | 目标 | 出处 |
|---|---|---|
| `documents.kind` | `dictionary` \| `grammar`（还会扩展到 `textbook`/`edition`…） | §6.2-1 |
| `chunks.stream` | 加 `definition`、`paradigm`、`example`、`formula`、`table`、`code` | §6.2-2、T2/T3/T4、D1、G1 |
| locator `dict` | `headword, homonym, sense, pos, column, page` | D1 |
| locator `grammar` | `section(§N), title, page` | G1 |
| 表 `lexicon_headwords` | `(lang, headword, lemma, pos, entry_id)` 精确索引，**不建向量** | D1 |

## 4. 对差结果（用 `schema_check.py` 实测）

在「有 proposed 词表的 v2 库」上跑，六条差异全部被机械检出：

| # | 差异 | 闸类型 | 后果 | 影响面 |
|---:|---|---|---|---|
| 1 | `documents.kind` 缺列 | 无此概念 | 词典/语法**无法按类选规则**；`book_meta` 那套只覆盖 v1 书路径，不覆盖 v2 文档 | `citation_policy.resolve`、`/v1/policy` |
| 2 | `stream=definition/paradigm/example/formula/table/code` 未进白名单 | **读时静默过滤** | 数据入库成功但 `/v1/search` 对学生**永远查不到**；最坏情况是"建了库，检索为空"，无报错 | `search._v2_meta_ok`、`catalog._meta_ok` |
| 3 | `locator={"scheme":"dict"}` 被 `validate` 拒 | **硬拒绝** | 词典**根本进不了库**（入库脚本直接抛 `LocatorError`） | 所有 adapter / ingest |
| 4 | `locator={"scheme":"grammar"}` 同上 | 硬拒绝 | 语法书进不了库 | 同上 |
| 5 | `lexicon_headwords` 表不存在 | 无此概念 | 词目精确查表无处落；退化成"把词条塞进 chunks + 向量"，与 D1 的质量门冲突 | 检索路径，需新端点 |
| 6 | 策略侧没有 dict/grammar 的 `locator_scheme` 与 tier/role 约定 | 策略缺口 | 即便入库，引用**无法渲染**（无 URL、无 label），`/v1/verify` 也无从校验 | `citation_policy`、`locators.url/label` |

**规模判断**：6 条里 **0 条**需要改核心表结构或迁移已有数据；1 条加列（可空）、2 条扩白名单
（纯加法）、1 条加表、2 条改策略常量。属于**加法式 v2.1**，不是 v3。

## 5. 迁移方案（按依赖顺序）

| 步 | 改动 | 兼容性 |
|---:|---|---|
| 1 | `schema.py`：`documents` 加 `kind TEXT`，`ensure_v2` 里就地 `ALTER`（同 `citations` 的做法） | 旧库自动补列，旧代码不读它 |
| 2 | `locators.py`：`SCHEMES += ("dict","grammar")`，`REQUIRED` 补键（`dict`: headword；`grammar`: section） | 只是放宽；未知 scheme 仍拒绝 |
| 3 | `locators.url/default_label`：为两种 scheme 加渲染（dict → 词典源 URL + `p.345 col.2 s.v. λύω`；grammar → `§212 · p.88`） | 纯新增分支 |
| 4 | `config.STUDENT_STREAMS` 默认值 + 文档：是否让学生看到 `definition` 等，**由学科决定**，默认仍只 `text` | 默认不变即无行为变化 |
| 5 | `citation_policy` 内置源加 `dict`/`grammar` 的 tier/role/scheme；规则按 `doc_kind` 选源 | 无规则引用则不生效 |
| 6 | `lexicon_headwords` + `/v1/lexicon` 端点（词形→词元→词条） | 新表新端点，不影响既有 |

**验收**（都可机械检查）：

1. `schema_check.py --db <旧 v1/v2 库>` 仍报 `gaps` 数量不变（旧库不需要任何迁移即通过）；
2. 建一个含 `dict`/`grammar` locator 的 v2 库，`schema_check.py` 的 `invalid` 为空、`gaps` 只剩"未实现的 proposed"；
3. 关掉新流白名单时，20 条固定查询快照与今天逐条一致；
4. 开 `stream=definition` 后，`/v1/search` 能命中且 `citation.locator` 可渲染出可点 URL。

### 5.1 已落地（2026-11-17）

| 步 | 状态 | 落点 |
|---:|---|---|
| 1 | ✅ `documents.kind` | `schema.py` DDL + `_ensure_column` 就地 ALTER（旧 v2 库自动补列） |
| 2 | ✅ `dict` / `grammar` scheme | `locators.SCHEMES` / `REQUIRED` |
| 3 | ✅ url / label 渲染 | `locators.url` / `default_label`（grammar 支持 `smythp` → Perseus URL） |
| 4 | ✅ 按文档类型定可见流 | `citation_policy.STREAMS` + `education.streams`；`streams_for(kind)`；`search`/`catalog`/`lexical` 三处读取都改为按 `documents.kind` 取流；`SOCRATIC_STUDENT_STREAMS` 仍是显式覆盖 |
| 5 | ✅ 策略侧词典/语法源与规则 | 内置源 `dict-lsj` / `grammar-smyth` / `grammar-ag`（tier A、`catalogue: lexicon`）；规则 `{doc_kind: dictionary|grammar}` 先于兜底规则；通道类型 `lexicon-sqlite`（能力 `lexicon`+`search`） |
| 6 | ✅ `lexicon_headwords` + `/v1/lexicon` | DDL 加表与两个索引；`app/lexicon.py`（词形→词元→词条 / `§N` 小节）；端点 `GET /v1/lexicon?q=&lang=&area=&view=&limit=`；缺库或未命中均显式降级 |

另：v1 库新增 `chunks.stream TEXT NOT NULL DEFAULT 'text'`（T1 扫描件全填 `text`，读取方不依赖）；
迁移脚本 `scripts/migrate_schema.py --db <库>`（自动备份、幂等、支持 v1/v2）。

## 5.2 效果评估（2026-11-17，实测）

| 项 | 结果 | 证据 |
|---|---|---|
| 测试 | sidecar **371**（+16） | `unittest discover` 全绿 |
| 契约缺口 | v2.1 测试库 **gaps 0**；词典库 **0**；真实 v1 库 **0** | `scripts/schema_check.py`（契约从代码读取，不再硬编码） |
| 可见流 | `None→text`；`dictionary→text+definition+example`；`grammar→text+paradigm+example`；`textbook→+formula+table+code`；`edition→+commentary+apparatus` | `streams_for()` |
| 学生/导师分流 | 同一词典文档：student **3**（text/definition/example）、tutor **4**（多 translation） | 真实 v2 检索 |
| 环境覆盖 | 设 `SOCRATIC_STUDENT_STREAMS=text` 后 student 回到 **1** | 同上 |
| 规则选择 | `doc_kind=dictionary → cite=[dict-lsj]`（anchor `lexicon`）；`grammar → [grammar-smyth, grammar-ag]`；无 `doc_kind` 时与改前**逐字相同** | `resolve()` / `merge_plan()` |
| 词条查询 | `λύω` → 1 条，含释义、`tier A`、`label=λύω · s.1 · p.345`、文档 canonical URL | `/v1/lexicon` 函数级调用 |
| 降级 | 无 `lexicon.db` → `reason=no_lexicon`；无该词 → `not_found`；`smythp=NNNN` 不会被猜成 `§N` | 同上 |
| 时延 | 词条 0.44 ms；v2 学生检索 1.69 ms；单 chunk 读取 0.33 ms（50 次均值，本地 FTS） | 同一脚本 |
| 真实库 | v1 `search.db` 已有 `stream` 列，167,192 行全 `text`；`gaps 0` | `schema_check.py` |

> 未做**端到端 GUI 冒烟**（插件侧没有词典卡片），也**没有真实词典数据**：上面的词典库是 2 条手工样本，
> 只证明契约与端点可用，不证明 E7 的建库质量。

## 6. 怎么复跑这套评估

```powershell
# 现有真库（v1）：应报 gaps 0
python scripts/schema_check.py --db D:/Guo-Code/rag-build/data/indexes/search.db

# 目标词表的 v2 库（例如词典 M0 的试建库）：--explain 会打印当前契约
python scripts/schema_check.py --db <lexicon.db> --explain --json
```

`--proposed` 是 `--explain` 的旧名，语义已改：不再与一份硬编码的"计划清单"比对，
而是**把实现侧的契约打印出来**（streams / schemes / 必需键 / 表 / education 档），
因为契约现在直接从代码读（`citation_policy.STREAMS`、`locators.SCHEMES`、
`schema.DDL`），不会随文档漂移。

判读规则：

| 输出 | 含义 |
|---|---|
| `invalid` 非空 | **硬拒绝**：`locators.validate` 会抛，数据进不了库 |
| `chunks.stream` 有值但不在 `--explain` 的 streams 里 | **静默不可见**：写入成功、学生视图查不到 |
| `documents.kind: ABSENT` | 语义缺口：按类型定流与按类型选规则都失效 |
| `missing`（仅 v2 显示） | `schema.DDL` 期望但库里没有的表 |
| `gaps: 0` | 该库与当前契约一致 |

## 7. 与其它契约文档的关系

| 文档 | 角色 |
|---|---|
| `docs/RAG-DB-SCHEMA.md` / `RAG-DB-SCHEMA-V2.md` | 契约的**人类可读**版本（要跟着本文的迁移同步改） |
| `sidecar/app/schema.py` + `locators.py` | 契约的**可执行**版本（唯一权威） |
| `rag-build/docs/CORPUS-PROFILES.md` §6.2 | 目标契约的提出处 |
| `docs/SCHEMA-GAP.md`（本文） | 两者的**差异账本** + 迁移方案 |
| `scripts/schema_check.py` | 差异的**测量工具** |
