# RAG 路线、公开语料与计算后端交接（2026-11-05）

| 项 | 值 |
|---|---|
| 日期 | **2026-11-05** |
| 项目 | `D:\Guo-Code\socratic-tutor` |
| 范围 | 检索路线、公开语料 API、`RAG-DB-SCHEMA`、计算后端 |
| 状态 | **讨论与实验完成；本轮未改仓库代码** |
| 结论 | 私有 PDF 保留 hybrid；公开语料需 v2 locator/adapter；ctext 放弃；MATLAB 放弃；SymPy 默认，Wolfram 可选；Lean 只做工具 |
| 相关 | [HANDOFF.md](HANDOFF.md)、[RAG-DB-SCHEMA.md](RAG-DB-SCHEMA.md)、[architecture-analysis.md](architecture-analysis.md)、[SIDECAR-CONTRACT.md](SIDECAR-CONTRACT.md) |

---

## 0. 一句话

本轮没有推翻现有实现，而是把边界划清了：**私有 PDF 书库继续用现有的 FTS5 + BGE-M3 + rerank；grep/lemma 是补充通道，不是替代；clean text 的最大收益是引用和公式，不是召回；只有接公开语料时才需要把 schema 升级为 locator/adapter 结构。**

---

## 1. 本轮最终决策（先看）

| ID | 决策 | 状态 | 理由 |
|---|---|---|---|
| D1 | 不把 grep-only 作为主路线 | **确定** | 100 问上 grep 0.59 vs hybrid 0.82；grep 解决精确性，不解决语义/跨语言 |
| D2 | 增加 grep/lemma 作为补充通道 | **建议** | 精确串、公式、人名、引文核验；lemma 在 32 条古典查询上到 0.56–0.66 |
| D3 | clean text/LaTeX 优先用于引用和公式，不期待它提升召回 | **确定** | 12% CER 召回只掉 6 点，引文存活只剩 11% |
| D4 | 只做私有 PDF 时，v1 schema 够用 | **确定** | `page/book/source` 与本地书库自洽；无需为“未来”重写 |
| D5 | 接公开语料时，升级为 v2 “稳定核心 + 可配置 adapter” | **确定** | CTS/ctext/MediaWiki/Lean 的引用单位不是页；自由 schema 不可取 |
| D6 | 放弃 ctext | **确定** | `/tools/api/zhs` 实际是订阅/机构增值服务入口，禁止抓取；无订阅不可依赖 |
| D7 | 汉语文言文：Wikisource 为主，HF 数据集为辅 | **建议** | Wikisource 有 revision 级引用；HF 数据集许可/来源需逐卡核实，默认非 citation-grade |
| D8 | 放弃 MATLAB | **确定** | 目标不是控制/信号/Simulink；Python SciPy/control + Wolfram 足够 |
| D9 | SymPy 默认；Wolfram Engine 可选 fallback | **建议** | 概念级计算 SymPy 够；难闭式/特殊函数用 Wolfram；许可/安全需隔离 |
| D10 | Mathlib/Lean 只做工具，不直接读数据源 | **确定** | 形式声明不是 prose；引用单位是 declaration + mathlib revision；Loogle JSON 不稳定 |
| D11 | 无政府主义图书馆只作为私有获取渠道，不做 API 集成 | **确定** | 用户私有库；无合法/稳定 API；不对外分发 |

---

## 2. 实验与数字

> 本轮实验都在**临时目录/私有数据目录**，没有进 git。复现路径见 §8。
> 口径：100 问为项目 P1-6 评估集；32 条为其中的希腊/拉丁（含 Conte）子集。

### 2.1 当前 `search.db` 是什么

先纠正一个容易误读的点：**当前索引已经是“有文字层”的干净文本子集，不是 90% 扫描 OCR。**

- `ingest_library.py` 只取 PyMuPDF `get_text()` 且每页 ≥200 字的页，不做 PaddleOCR；`cpp >= 200` 选书。
- 61 本馆藏文字层：25,839 页，其中 24,142 页有 ≥200 字文本（93.4%）。
- Steadman：100 卷 / 约 9,890 页 digital。
- 当前 `search.db` 覆盖约 **10%** 的 361,862 页；其余 90% 影印页**不在索引里**。
- 因此 `0.60 / 0.82` 是 **clean text 上的数字**；12.1% CER 的扫描 OCR 不是这套评估的输入。

### 2.2 100 问：grep vs FTS vs hybrid

| 子集 | grep（jieba + BM25-lite） | FTS5 | hybrid + 翻译 |
|---|---:|---:|---:|
| 中文（58） | 79.3% | **86.2%** | **94.8%** |
| 英文（10） | 40.0% | 10.0% | 50.0% |
| 拉丁（20） | 35.0% | 35.0% | **75.0%** |
| 希腊（12） | 16.7% | 16.7% | **58.3%** |
| **总体（100）** | **59.0%** | **60.0%** | **82.0%** |

补充：

- 整句直接 grep（不拆词）：**0/100**；grep 路线必须先做查询拆解。
- Oracle：83/100 的金标页至少包含一个查询词；17/100 词表完全不重叠（语义/跨语言）。
- 平均候选页 4,631；p95 297 ms（89 MB 文本，16 个词/查询）。
- 结论：**换引擎不换天花板**；词法天花板约 0.60，0.82 的增益来自语义 + 翻译 + 重排。

### 2.3 32 条希腊/拉丁：lemma 索引 + 强排序

方法：`simplemma` 对 `grc/la/en` 做词典 lemma；索引 raw / 去重音 / lemma 变体；按原 token 分组，组内取最佳变体；IDF 选 16 组；BM25 `k1=1.0, b=0.75` + proximity；原问与翻译合并，翻译权重 0.8。

| 方法 | 希腊(12) | 拉丁(20) | 32 条 |
|---|---:|---:|---:|
| 精确 grep（之前最好） | 3 | 8 | **11/32 = 0.344** |
| lemma 默认 | 7 | 11 | **18/32 = 0.562** |
| lemma 最佳网格 | 7 | 14 | **21/32 = 0.656** |
| hybrid + 翻译（项目现有） | 7 | 15 | **22/32 = 0.688** |

要点：

- Oracle = **32/32**：词都在，瓶颈是**排序**，不是 lemma 覆盖。
- 最佳配置：`max_groups=16, k1=1.0, b=0.75, cov_factor=0, translated_weight=0.8, proximity=on`；多个邻近配置 0.625。
- 诚实区间 **0.56–0.66**；48 组网格在同一批 32 条上选最佳，存在过拟合；不要宣称“lemma 超过 hybrid”。
- 但结论成立：**clean text + lemma + 翻译 + 强排序，在古典子集上可以到 0.6 附近**，不是 raw grep。

### 2.4 文本干净度：召回 vs 引用

受控退化：在 100 问 clean text 上注入 OCR 类字符编辑，重建项目 FTS5，跑同一套 query。

| CER | 0% | 3% | 6% | 12% | 20% |
|---|---:|---:|---:|---:|---:|
| page recall@10（0/6/12/20 为 3 seed 均值；3% 为单 seed） | **0.600** | ~0.58 | **0.573** | **0.537** | **0.493** |
| 20 字引文精确存活率 | **100%** | **52.3%** | **31.0%** | **10.7%** | **4.3%** |

- 0% 精确复现项目 0.60；分语言：中文 0.862、拉丁 0.35、希腊 0.167、英文 0.10。
- 召回对 CER 不敏感：约 **0.5 点 / 1% CER**。
- 引用对 CER 极敏感：约 **7–8 点 / 1% CER**（3% 就掉一半）。
- **结论：clean text 的第一收益是引用/公式，不是召回。**

### 2.5 真实 OCR 抽样：20 本扫描书

从 90% 无文字层扫描书中抽 20 本（中国文史哲 5、数学 4、物理 3、西方文史哲 4、计算机 2、马列 2），每本 1 页；20 页全部 0 字嵌入文本，是真扫描。

| 指标 | 结果 |
|---|---|
| RapidOCR 平均置信度 | 0.927 |
| ├ 中国文史哲（含竖排/密集） | 0.857 |
| ├ 数学 | 0.898 |
| └ 西方文史哲 / 计算机 / 马列 | 0.98+ |
| PaddleOCR 6 页水平文本平均置信度 | 0.991 |
| Paddle vs Rapid 跨引擎 CER（6 页水平） | 0.0% / 0.7% / 0.4% / 1.9% / 5.1% / 6.5% |
| Paddle vs Rapid 跨引擎 CER（竖排《周书》1 页） | **58.3%** |

- 水平现代文本 OCR 已接近 clean；竖排古籍/密集版式/公式是断崖。
- 跨引擎 CER 是代理，不是 ground truth；PaddleOCR 自身 CER 未测。
- 这与项目“竖排只做页图 + 卷次”“中文 OCR 只检索、引用回页图”的策略一致。

### 2.6 实验局限

- 32 条 / 100 条样本小；希腊 12、英文 10，分语言只作方向。
- lemma 最佳配置在同一批查询上选，可能过拟合。
- 退化模型是随机字符编辑，不是真实版面/列序错误；可能低估真实 OCR 影响。
- 翻译是项目已有的一次 LLM 结果，非确定性；但 hybrid 对照用的是同一批翻译。
- 真实 OCR 没有 clean 参考，只有跨引擎一致性/置信度。

---

## 3. 路线判断

1. **不替换 hybrid。** 100 问 0.82 vs grep 0.59；希腊/拉丁 0.688 vs 0.34；去掉语义层是负收益。
2. **grep/lemma 作为一等补充通道。** 精确串、公式、人名、引文、代码标识符；引用前做精确匹配闸门。
3. **clean text 优先做“引用级”升级。** 逐字引文、公式计算、页图核验；不要指望它把召回从 0.60 拉到 0.82。
4. **lemma 路线成立但有限。** 对 clean classical text 可到 0.56–0.66，接近 hybrid；需要 Unicode 分词、去重音、lemma、翻译、IDF 选词、proximity，不是“pure grep”。
5. **语言分层**：中文 FTS 已 86%，接近门槛；英文 FTS 10% 低得不正常，先查 tokenizer/停用词/页级排序；希腊/拉丁必须语义 + 翻译。
6. **引用闸门**：LLM 给出引文 → 页内精确匹配（`verify`）→ 不过则“未核验/拒答”；页图仍是最终权威。

---

## 4. 公开语料 API 结论

> 核查日期 2026-11-05。ctext 页面实际返回的是订阅/反抓取入口，不是开放 API 文档；未绕过。

### 4.1 汉语文言文

| 源 | 访问 | 引用单位 | 许可/条款 | 结论 |
|---|---|---|---|---|
| **Wikisource** | MediaWiki Action/REST API | 页面标题 + revision + section | 公版/CC BY-SA | **主源**；citation-grade；注意 User-Agent/限流 |
| **dzxr/chinese-classical-corpus** | HF 数据集 | dataset/split/row | 需查 card | 辅助；非 citation-grade；用于覆盖/候选 |
| **kenpusney/greathangpt-classical-chinese** | HF 数据集 | dataset/split/row | 需查 card | 辅助；来源/许可需核实 |
| **ctext** | 订阅制 JSON API/Python 模块；禁止抓取 | 章节 | 机构订阅条款 | **放弃**；无订阅不接 |

- HF 数据集是 dataset，不是 API；用 HF datasets-server / Parquet / `datasets` 读取，无 SLA。
- 两者具体 license/provenance 本次网络抓取失败，未核实；接入前必须查 card。
- Wikisource 是 citation-grade；HF 数据若要引用，必须能映射回原源（否则只做 retrieval/辅助）。

### 4.2 古典、数学、通用

| 源 | 访问 | 引用单位 | 许可/条款 | 结论 |
|---|---|---|---|---|
| **Perseus** | CTS API（GetCapabilities/GetPassage）+ Scaife JSON search；Catalog 只有 ATOM/HTML | CTS URN | 逐 edition | 希腊/拉丁可用；429 限流；无页图 |
| **Open Greek and Latin / First1KGreek** | GitHub XML；无统一 API | CTS URN | 逐仓库/edition | 批量 clone；静态；无 SLA |
| **CBDB** | 批量关系库/在线查询；未确认公开 REST | 人物/官职/地点 ID | 学术条款 | **实体工具**，不是 chunks |
| **Lean / Mathlib** | Loogle JSON `/json?q=`（格式不保证稳定）+ Mathlib Git/docs | module + declaration + revision | Apache-2.0 | **工具**，不是数据源 |
| **NaturalProofs** | GitHub/Zenodo 数据集 | theorem/reference ID | 研究数据集 | 实验用；非生产语料 |
| **TheorIA** | GitHub JSON/Pages；无 API | entry ID | **CC BY 4.0** | 物理公式/推导；需署名 |
| **OpenStax** | CC BY PDF/HTML/GitHub；旧 CNX Content API 文档（历史归档）；未确认当前公开 API | 章节/页 | CC BY 4.0 | 教材/讲解层；优先用 PDF/HTML/GitHub |
| **Wikibooks** | MediaWiki API/REST | 页面 + revision | CC BY-SA | 通用教学补充 |
| **Wikimedia** | Action/REST/dumps | 页面 + revision | CC BY-SA/PD | 通用知识；非经典原文主源 |
| **Internet Archive** | Metadata/Search/全文 API | item + file + page | PD 与借阅混合 | PD 扫描件可用；借阅内容不可当开放语料 |

关键链接：

- Perseus Catalog URI/ATOM：[Catalog Data URIs](https://sites.tufts.edu/perseuscatalog/?page_id=93)、[搜索 API FAQ](https://sites.tufts.edu/perseuscatalog/?page_id=366)
- Perseus CTS/Scaife/429：[Perseus-mcp README](https://github.com/tonyjurg/Perseus-mcp)、[Scaife Viewer](https://scaife-viewer.org/)
- First1KGreek：[GitHub](https://github.com/OpenGreekAndLatin/First1KGreek)
- ctext 订阅/反抓取：[tools/subscribe](https://ctext.org/tools/subscribe)
- CBDB：[Dataverse](https://dataverse.harvard.edu/dataverse/cbdb)、[GitHub](https://github.com/cbdb-project)
- GreatHanGPT：[HF dataset](https://huggingface.co/datasets/kenpusney/greathangpt-classical-chinese)
- Chinese classical HF：[dzxr/chinese-classical-corpus](https://huggingface.co/datasets/dzxr/chinese-classical-corpus)
- Loogle：[README](https://github.com/nomeata/loogle)、[Loogle](https://loogle.lean-lang.org/)；Mathlib：[mathlib4](https://github.com/leanprover-community/mathlib4)
- NaturalProofs：[GitHub](https://github.com/wellecks/naturalproofs)；TheorIA：[GitHub](https://github.com/theoria-dataset/theoria-dataset)
- OpenStax：[旧 CNX API](https://github.com/openstax/cnx-archive/blob/master/docs/content_api_doc.md)、[GitHub](https://github.com/openstax)
- MediaWiki API：[API:Main_page](https://www.mediawiki.org/wiki/API:Main_page)；Wikimedia REST：[Wikimedia_REST_API](https://www.mediawiki.org/wiki/Wikimedia_REST_API)
- Internet Archive：[Metadata API](https://archive.org/developers/metadata.html)

### 4.3 明确放弃/后置

- **ctext**：无订阅不接；禁止抓取；不要写爬虫。
- **Anna's Archive / Z-Library**：私有获取渠道，不是 API；不做集成；不对外分发。
- **MATLAB**：放弃。
- **CBDB/NaturalProofs/TheorIA**：后置；先明确 tutor 的 use case（人物查询/定理检索/物理公式），再决定工具还是 dataset。
- **Lean/Mathlib 全库**：不进 chunks；只做工具/精选 `lean` 子集。

---

## 5. `RAG-DB-SCHEMA` 建议

### 5.1 当前 v1 的假设与失配

v1（[RAG-DB-SCHEMA.md](RAG-DB-SCHEMA.md#L29-L39)）：

```sql
chunks(id, source, book, lang, page, text, visibility)
```

隐含假设：

1. 每个 chunk 有整数 `page`；
2. `book` 是相对路径；
3. `source` 对应 `pages.ROOTS` 硬编码根（[pages.py](../sidecar/app/pages.py#L24-L28)）；
4. 引用是 `book p.N`；
5. 单一 BGE-M3 1024d 向量；
6. `toc` 是页范围。

公开语料的现实：

| v1 | 公开语料 |
|---|---|
| `page` 必填 | CTS 是 book/line；ctext 是章节；Lean 是声明；MediaWiki 是 revision；CBDB 是人物 ID |
| `book` 路径 | URN / ID / title / module |
| `source` 硬编码 | API base、auth、rate limit、adapter |
| `citation = book p.N` | 需要 scheme：`cts`/`ctext`/`mediawiki`/`lean`/`dataset`/`ia` |
| `verify(page, quote)` | 需要 scheme-aware 校验 |
| 单向量 | 多模型/多语言/多维度；需要 model/version |
| `visibility` 只有 tutor/answer_key | 译本/注释需要 **stream 级**隔离 |
| 无 `license`/`provenance`/`edition`/`quality` | 无法禁止导出、无法署名、无法区分版本 |

### 5.2 何时必须改

| 场景 | v1 是否够 | 结论 |
|---|---|---|
| 只做私有 PDF 库 | **够** | 不重写；最多后补 `provenance`/`license` |
| 加 Perseus/OGL | 不够 | 需要 `locator=cts`、`document_id`、adapter |
| 加 Wikisource | 不够 | 需要 `locator=mediawiki`、revision、license |
| 加 HF 数据集 | 不够 | 需要 `locator=dataset`、provenance、非 citation-grade 标记 |
| 加 Lean/Mathlib | 不够 | `locator=lean` + revision；工具/精选子集 |
| 加 CBDB | 不够 | 实体工具，不是 chunks |
| 加 IA 公版扫描件 | 部分够 | 仍是 `pdf_page`，但加 item/file、PD/借阅标记 |

**触发条件不是“书从哪来”，而是“引用单位是否还是页”。**

### 5.3 v2 最小设计（稳定核心 + 可配置 adapter）

```sql
sources(source_id, adapter, base_url, auth_env, rate_limit,
        license, redistribution, enabled, config_json)

documents(document_id, source_id, title, author, edition, lang, script,
          license, provenance, canonical_url, metadata_json)

chunks(id, document_id, ordinal, text, lang,
       stream,            -- text | translation | commentary | apparatus
       visibility,        -- student | tutor | answer_key
       locator_json,
       citation_label,
       quality,
       char_start, char_end,
       source_version)

assets(asset_id, document_id, chunk_id, type, uri, rights, metadata_json)

embeddings(chunk_id, model, dim, version)

toc(document_id, scheme, ord, level, title,
    locator_start_json, locator_end_json, meta)
```

`locator_json` union：

```json
{"scheme":"pdf_page","page":12,"bbox":[0.1,0.2,0.8,0.9]}
{"scheme":"cts","urn":"urn:cts:greekLit:tlg0012.tlg001.perseus-grc2:1.1","book":1,"line":1}
{"scheme":"mediawiki","title":"史記/卷一","revision":123456,"section":"..."}
{"scheme":"lean","module":"Mathlib...","decl":"Real.sin","mathlib_rev":"e6bd550"}
{"scheme":"dataset","dataset":"theoria","split":"train","id":"..."}
{"scheme":"ia","item":"...","file":"...","page":42}
```

配套：

- `verify` 改为 **scheme-aware**：`pdf_page` 页图+文本；`cts` passage/line；`mediawiki` revision；`lean` declaration；`dataset` record ID。
- citation 响应统一为 `{scheme, label, locator, url, image, tier, license}`；插件不再假设 `page_image`。
- `source_type`：`text | scan | entity | formal | dataset`；CBDB/Lean 走工具，不进 chunks。
- v1 保留兼容视图；`SOCRATIC_SCHEMA=v1|v2`；现有 PDF 路径不动。

### 5.4 不做什么

- **不要把 schema 做成任意字段可配置。** 每个源一套 schema，检索/引用/测试组合爆炸。
- 可配置的是 **source adapter / manifest**；核心字段语义必须稳定。
- 不要为了“统一”把 CBDB/Lean 塞进 `chunks`。
- 不要在没有 v2 的情况下先灌公开语料；`page` 会撒谎，引用会错。

---

## 6. 计算后端

### 6.1 默认与升级

| 任务 | 默认 | 升级 |
|---|---|---|
| 微积分/线代/ODE/概率概念 | SymPy + NumPy/SciPy | 闭式解失败 → 数值/可选 Wolfram |
| 物理概念/量纲/数值 | SymPy + pint + SciPy | 复杂张量/GR → 专用工具/可选 Wolfram |
| CS 算法/复杂度 | Python | 形式语义/证明 → Lean（工具） |
| 逻辑/类型论/形式证明 | Lean/Mathlib（工具） | 仅当课程目标要求 |
| 控制/信号 | SciPy/control | 不引入 MATLAB；Wolfram 不是 Simulink |

**SymPy 够用于“概念级计算与检查”；不够用于研究级闭式解、复杂张量/GR、形式证明。**

### 6.2 Wolfram Engine + MCP

- Wolfram Engine 免费版面向开发/预生产；生产部署/分发按 [Wolfram 条款](https://www.wolfram.com/legal/terms/wolfram-engine.html) 处理；不能打包进 MIT 仓库。
- 社区 [`mathematica-mcp-full`](https://pypi.org/project/mathematica-mcp-full/)：MIT、beta、~79 tools、可控制 notebook/kernel；官方明确 **不支持生产/不可信多租户**；PyPI 无 provenance；前置条件写的是 Mathematica 14+，**是否兼容免费 Engine 需实测**。
- 优先评估 [Wolfram 官方 Local MCP](https://www.wolfram.com/ai/mcp/local/)；社区包只做实验：`math` profile、pin 版本、低权限/禁网/超时/审计。
- 架构：`compute_python` 默认；`compute_wolfram` 可选 adapter；MCP 只是 transport，sidecar 的 `/v1/compute` 契约才是稳定层。
- 返回凭证：`backend`/`engine_version`/`code`/`assumptions`/`result`/`verification`；SymPy 与 Wolfram 结果分别标注，不一致标 `disputed`。

### 6.3 Lean/Mathlib

- **工具，不是数据源。** Mathlib 是形式声明库，不是 prose；引用是 declaration + mathlib revision。
- Loogle `/json?q=` 可用但格式不保证稳定；pin revision、缓存。
- Lean 检查是编译/证明任务，放 job/沙箱，不放在每轮热路径。
- 如需 RAG，只做精选 `source_type=formal` + `locator=lean` 子集，不进全库。

---

## 7. 下一步（按优先级）

1. **先问用户定 scope**：近期只做私有 PDF，还是要接公开语料？
2. **私有 PDF-only**：
   - 保持 v1；不重写 schema。
   - 增加 grep/lemma 工具 + 引用闸门（精确匹配 + 页图）。
   - 可选后补 `provenance`/`license`/`edition`，为未来导出/MCP 暴露做准备。
3. **要接公开语料**：
   - 先做 v2 最小契约（`document_id`/`locator`/`source_id`/`license`/`stream`/`sources`）。
   - 第一个 adapter：Wikisource（MediaWiki API，revision 级引用）。
   - 第二个：Perseus/OGL（CTS URN）。
   - 第三个：OpenStax/Wikimedia/Wikibooks（secondary，CC）。
   - Lean/Mathlib 工具化；Wolfram 可选；CBDB 后置。
4. **实验补强**：
   - 32 条 lemma 做 holdout/固定配置复验，防过拟合。
   - 中文同义词/分词扩展；英文 FTS 10% 的 tokenizer 排查。
   - 竖排/Paddle 真实 CER ground truth；引文存活 vs 真实 OCR。
   - Wolfram Engine + `math` profile 的 20 题基准（SymPy vs Wolfram）。
5. **不要做**：
   - 不要爬 ctext；不要接 Anna's/Z-Library API；不要分发商业书文本/向量。
   - 不要为了“统一”做自由 schema；不要把 Mathlib 全库切 chunks。
   - 不要默认捆绑 Wolfram/MATLAB/Lean；不要声称 SymPy 结果是“证明”。

---

## 8. 可复用产物（临时/私有，未进 git）

### 8.1 检索/实验脚本

| 文件 | 用途 |
|---|---|
| `D:\Guo-Code\temp\grep_vs_rag.py` | 100 问 grep baseline（jieba + BM25-lite） |
| `D:\Guo-Code\temp\grep_translate.py` | 32 条希腊/拉丁 grep + 翻译/词干对照 |
| `D:\Guo-Code\temp\fts_translate.py` | 项目 FTS 在翻译 query 上的对照 |
| `D:\Guo-Code\temp\lemma_simplemma.py` | simplemma lemma 索引 + BM25/proximity |
| `D:\Guo-Code\temp\lemma_grid.py` | 48 组参数网格（输出 `lemma_grid.json`） |
| `D:\Guo-Code\temp\lemma_best.py` | 最佳配置逐条结果 |
| `D:\Guo-Code\temp\degrade_eval.py` | 单 seed 退化 + FTS 重建 |
| `D:\Guo-Code\temp\degrade_multi.py` | 3 seed 退化均值（输出 `degrade_multi.json`） |
| `D:\Guo-Code\temp\quote_survival.py` | 20 字引文存活率（输出 `quote_survival.json`） |
| `D:\Guo-Code\temp\tok_test.py` | 项目 `tokens()` 对希腊/拉丁的测试 |

### 8.2 OCR 抽样

目录：`D:\Guo-Code\rag-build\data\experiments\ocr_study\`

| 文件 | 内容 |
|---|---|
| `pdf_text_scan.json` | 900 个 PDF 的文字层抽样统计 |
| `selected_books.json` | 20 本扫描书选择 |
| `rapid20.json` | 20 页 RapidOCR 结果/置信度 |
| `paddle5.json` | 6 页水平文本 PaddleOCR 结果 |
| `pages_fast/` | 抽样页图（jpg） |
| `run_rapid20.py` / `run_paddle5.py` | OCR 脚本 |

### 8.3 环境/坑

- `simplemma` 安装在 `D:\Guo-Code\temp\nlp_libs`；脚本里已 `sys.path.insert`。
- `jieba` 在 `.venv-bge`；base Python 可通过 `PYTHONPATH` 使用。
- PaddleOCR 在 `rag-build\.venv-ocr`（2026-11-06 从 `socratic-tutor/.venv-ocr` 迁入）；需设 `PADDLE_PDX_CACHE_HOME=D:\Guo-Code\rag-build\cache\paddlex`，`enable_mkldnn=False`。
- 本机 venv 的 Python 进程写 `D:\Guo-Code\temp` 会 `PermissionError`；让 base Python 写 temp，或让 venv 写 `rag-build\data\experiments\` / workspace。
- PaddleOCR 在密集竖排页可能 >1 分钟/页；抽样时优先水平页，或降低分辨率/跳过大图。

---

## 9. 未决/风险

- **scope 未定**：只私有 PDF，还是要公开语料？这决定 v2 是否现在做。
- **Wikisource 覆盖率/质量**：目标古籍是否都有校对版？需要逐书验证。
- **HF 数据集 license/provenance**：`dzxr`、`greathangpt` 的 card 本次未稳定读取；未核实前不可 citation-grade。
- **lemma 过拟合**：32 条、48 组网格；需 holdout/固定配置复验。
- **竖排 OCR**：Paddle 自身 CER 未测；跨引擎 58.3% 是代理。
- **Wolfram Engine 兼容性**：`mathematica-mcp-full` 文档要求 Mathematica 14+；免费 Engine 是否可用需实测。
- **Wolfram 许可**：生产/分发边界需按条款；不能在 MIT 仓库捆绑。
- **answer_key/stream**：公开语料的译本/注释需要 stream 级隔离；v1 只有 chunk 级 `visibility`。
- **公开仓边界**：私有库文本/向量/页图不进公开仓；schema 的 `license`/`redistribution` 应能强制执行。

---

## 10. 可直接粘给下一个 Agent 的接手提示

```text
你在 D:\Guo-Code\socratic-tutor 接手一个“引用优先的苏格拉底式 RAG 教学 Agent”。
先读 docs/HANDOFF.md、docs/RAG-DB-SCHEMA.md、docs/HANDOFF-2026-11-05-rag-strategy.md。

本轮结论：
1) 私有 PDF 库继续用 FTS5 + BGE-M3 + rerank；grep/lemma 只做补充通道和引用闸门，不替换 hybrid。
2) 当前 search.db 是“有文字层”的约 10% 页，不是 90% 扫描 OCR；0.60/0.82 是 clean-text 数字。
3) 32 条希腊/拉丁：lemma+强排序 0.56–0.66，hybrid+翻译 0.688；不要宣称 lemma 超过 hybrid。
4) 文本干净度：12% CER 召回只掉 6 点，20 字引文存活只剩 11%；clean text 优先用于引用/公式。
5) ctext 放弃（订阅/机构增值，禁止抓取）；汉语文言文优先 Wikisource（MediaWiki API，revision 引用），HF 数据集只做辅助。
6) 只做私有 PDF 时 v1 schema 够；接公开语料前先做 v2 “稳定核心 + source adapter”，不要自由 schema。
7) SymPy 默认；Wolfram Engine 可选 fallback；MATLAB 放弃；Mathlib/Lean 只做工具，不直接读数据源。

先问用户 scope：只私有 PDF，还是要接公开语料？不要先写代码。
不要爬 ctext；不要接 Anna's/Z-Library API；不要分发商业书文本/向量；不要默认捆绑 Wolfram/MATLAB/Lean。
```
