# 语法书 / 词典能力开发方案

| 项 | 值 |
|---|---|
| 日期 | 2026-11-12 |
| 范围 | 运行时的"查词"与"查语法"能力；数据工程部分属于 `rag-build` |
| 现状 | 只有 `lexical.py` 的 grep/lemma 检索；**没有词典义项，也没有语法书** |
| 结论 | 词典是**查表**问题不是向量问题；先做精确词条索引，语法书才用检索 |

---

## 0. 一句话

词典和语法书要分开设计：**词典靠词条精确匹配（含词形还原）**，**语法书靠主题检索**。
把 30 万词条塞进向量库既慢又没必要。

> **数据侧需求**：词典/语法书的 OCR-RAG 与经典文本不同，详见 rag-build 的
> `docs/DICTIONARY-GRAMMAR-PIPELINE.md`（先数字版、后 OCR；词条级切分；字母序质检）。

## 1. 两个能力，两条路径

| 能力 | 典型问题 | 正确通道 | 为什么 |
|---|---|---|---|
| 词典 | "λύομεν 是什么意思？" | 词形 → 词元 → 精确查表 | 答案唯一且短；向量召回只会引入噪声 |
| 语法 | "什么是绝对夺格？" | 主题/术语检索（FTS + 向量） | 问题是概念性的，措辞多样 |
| 用例 | "给我看《史记》里'以为'的用例" | 现有 `kb_search` + grep | 已有能力，不需要新系统 |

## 1b. 词典和语法书也不是一回事

前面那张表区分的是"查词 vs 查语法"，这里再往下切一层：**这两类出版物本身的结构、
检索方式、甚至是否该建向量都不一样。**

| 维度 | 词典 | 语法书 |
|---|---|---|
| 回答的问题 | "这个词什么意思" | "这个现象怎么解释" |
| 抽取单元 | **词条**（词目 + 义项层次） | **小节**（§ 编号） |
| 数量级 | 数万条，每条几十到几百字 | 数百节，每节数千字 |
| 结构 | 词目 → 义项 → 书证 | 章 → 节 → 规则 → 例句 / 表格 |
| 顺序 | **字母序**（可做全局质检） | 教学顺序（§ 编号，无字母约束） |
| 检索方式 | **精确查表**（词形 → 词元 → 词条） | **主题检索**（FTS + 向量） |
| 是否建向量 | ❌ 不建 | ✅ 建（小节级） |
| 切片粒度 | 单个词条（通常 < 1 KB） | 单个小节（2–10 KB） |
| 引用单位 | `page + column + headword + sense` | `§N + page` |
| 失败模式 | 词目错 = 查不到；释义错 = **误导** | 漏节 = 答不全，但页图可兜底 |
| 质量门 | 词目 ≥ 99.5%、字母序违例 < 0.1% | 节号覆盖 ≥ 98%、交叉引用解析 ≥ 90%、表格 ≥ 90% |
| 评测 | 词形→词元命中 ≥ 95%，首义项正确 ≥ 90% | 概念题 R@5 ≥ 0.9 |
| 公版来源 | LSJ / Lewis & Short（Perseus XML） | Smyth / Goodwin（Perseus，公版） |
| 现代版权本 | 仅本地 `personal` | 仅本地 `personal` |

### 由此产生的三个设计后果

1. **两条数据管线**：词典走"版面 → 词条切分 → 词目索引"；语法书走"版面 → 小节切分 →
   交叉引用解析 → 向量索引"。共用 OCR 与页图，但**切分与索引不同**。
2. **两套质量门**：词典的核心指标是**词目字符准确率**（错一个字母即不可达）；
   语法书的核心指标是**小节覆盖与主题召回**（错几个字仍可读）。
3. **两套检索路径**：`/v1/lexicon?word=` 走精确索引、毫秒级、无向量；
   `/v1/lexicon/search?kind=grammar` 走 FTS + 向量，和现有 `kb_search` 同一套机制。

### 教学上的分工

| 学生问题 | 用哪个 | 说明 |
|---|---|---|
| "λύομεν 是什么意思" | 词典 | 定义性，给义项 + 词目出处 |
| "为什么这里用与格" | 语法书 | 解释性，给 § 与例句 |
| "这个词在《史记》里怎么用" | 语料检索 | 已有 `kb_search` + grep |

三者可以串起来：语法书给出规则 → 词典确认词义 → 语料检索给真实用例。

## 1c. 两类材料的共同点

- 都需要**页图回页**（pypdfium2 已具备）；
- 都需要 `license` / `redistribution` 字段（现代本只能本地）；
- 都**不应该**按页切块（现有 `chunks` 的页级假设不适用）；
- 都优先用数字版，OCR 是兜底。

## 2. 数据模型（沿用 schema v2，不新建库）

词典与语法书都是 `documents`，区别在 `kind` 与 `locator`：

```sql
-- documents 增加一列（v2 兼容扩展）
ALTER TABLE documents ADD COLUMN kind TEXT DEFAULT 'text';   -- text | dictionary | grammar

-- chunks.locator_json 新增两种 scheme
{"scheme":"dict","headword":"λύω","entry":"λύω","sense":"1","pos":"v"}
{"scheme":"grammar","section":"3.2","title":"绝对夺格"}
```

`chunks.stream` 复用现有取值，新增两种：

| stream | 内容 |
|---|---|
| `definition` | 义项正文 |
| `paradigm` | 变格/变位表（纯文本或 JSON 字符串） |
| `example` | 书证（带出处） |
| `commentary` | 语法书的说明文字（已有取值） |

**索引策略**：

```sql
CREATE TABLE lexicon_headwords (
  lang TEXT, headword TEXT, lemma TEXT, pos TEXT,
  entry_id TEXT, document_id TEXT, chunk_id INTEGER,
  PRIMARY KEY (lang, headword, entry_id)
);
```

- 只对 `headword` / `lemma` 建索引，**不建向量**（语法书相反：小节级 text chunk + 向量）；
- 词形 → 词元的映射表另外存（见 §3）；
- 语法书仍进 `chunks_fts`，按现有二元组/词干规则分词。

## 3. 词形还原（这是真正的难点）

古典语言的查询几乎都以变格形式出现，直接查词条会失败。

| 语言 | 手段 | 备注 |
|---|---|---|
| 古希腊 | `simplemma` + 不规则表 | 覆盖有限，需要兜底：截词尾规则 + 距离匹配 |
| 拉丁 | `simplemma` + 名词/动词变位表 | 名词 5 变格、动词 4 变位，可离线生成规则表 |
| 英语 | 直接小写化（词典词条即原形） | 少量不规则复数 |
| 中文 | 繁简转换 + 异体字表 + 去"子/儿"词尾 | 不涉及屈折；主要是字形归一 |

实现顺序：**归一化（NFC、小写、去重音可选）→ 词典直查 → 词元查 → 规则剥离 → 模糊（编辑距离 ≤2）**。
每一级命中都记录 `matched_by`，便于评测与调试。

## 4. API 设计（sidecar 新增，契约写进 SIDECAR-CONTRACT）

```
GET /v1/lexicon?word=λύομεν&lang=grc&source=lsj&limit=3
→ {
    "query": "λύομεν",
    "normalized": "λυομεν",
    "matched_by": "lemma",
    "lemma": "λύω",
    "entries": [
      {"headword":"λύω","pos":"v","sense":"1","gloss":"to loose, untie",
       "citation":{"scheme":"dict","label":"LSJ λύω 1","url":null,"page_image":null},
       "license":"public-domain","document_id":"lsj"},
      ...
    ]
  }

GET /v1/lexicon/search?q=absolute+ablative&lang=en&kind=grammar
→ 复用检索结构，只是限定 kind=grammar
```

要点：

- 返回 `matched_by`（direct/lemma/rule/fuzzy），前端可提示"按词元匹配"；
- `citation` 与现有结构一致，但 `scheme=dict`，**没有页码时 page_image 为 null**；
- `license` 直接透出，便于遵守导出限制。

## 5. 教学集成

| 场景 | 工具 | 行为 |
|---|---|---|
| 学生问词义 | 新增 `lexicon_lookup` | 先查词条；查不到再退回 `kb_search`（语料检索） |
| 学生问语法 | `lexicon_lookup(kind=grammar)` 或 `kb_search` 加 `kind` 过滤 | 返回语法书页 + 例句 |
| 回答里给词义 | `cite_verify` 扩展 | `scheme=dict` 时校验"该词条确实有此义项" |

插件侧只加一个工具，参数 `word`/`lang`/`kind`，避免工具列表膨胀。

## 6. 许可与分发（硬约束）

| 来源 | 许可 | 可否进公开仓 |
|---|---|---|
| LSJ（Liddell-Scott-Jones, 9th ed.） | 公版 | ✅ 文本可分发（仍建议只发代码） |
| Lewis & Short | 公版 | ✅ |
| **PerseusDL/lexica**（LSJ、L&S 的 TEI/XML） | **CC BY-SA 4.0**（数字化版权，非公版） | ⚠️ 可本地用；若分发派生的 `lexicon.db` 必须同样 BY-SA + 署名 Perseus |
| Wiktionary | CC BY-SA | ⚠️ 需署名 + 相同方式共享，**不能只写 MIT** |
| 王力《古汉语字典》等现代辞书 | 版权保护 | ❌ 仅本地 personal |
| 现代语法书（如 Cambridge Grammar） | 版权保护 | ❌ 仅本地 personal |

因此 `documents.license` 与 `documents.redistribution` 必须在入库时填写，
`/v1/lexicon` 原样返回；导出/分享工具按这两个字段拒绝。

## 7. 公共 API 与批量数据（2026-11-12 核查）

**结论：能，但"一次性拉取入库"优于"运行时调用"。**

| 来源 | 形态 | 许可 | 建议 |
|---|---|---|---|
| **PerseusDL/lexica**（LSJ / Lewis & Short，TEI XML） | 批量下载（GitHub 仓库，`grc/lsj`、`lat/ls`） | **CC BY-SA 4.0** | ✅ **首选**：入库后离线查，引用稳定 |
| **Wiktionary** | MediaWiki API / dump | CC BY-SA | ✅ 兜底：本地查不到时按词取 |
| **CC-CEDICT** | 批量（`cedict_1_0_ts_utf-8_mdbg.txt.gz`） | CC BY-SA 4.0 | ✅ 中文词目/释义的首选开源来源 |
| **Unihan** | 批量 | Unicode License | ✅ 读音、异体字、部首 |
| **Whitaker's Words** | 批量（数据文件） | 公版 | ✅ 拉丁词形还原（与 simplemma 互补） |
| **Logeion** | JSON API：`anastrophe.uchicago.edu/logeion-api/detail?w=&type=normal&key=` | 条款不明；key 是网页 JS 里的公共 Firebase key | ⚠️ **仅实验**：key 非官方发布、随时可能失效，不进生产 |
| **ctext** | API，订阅制 | 机构订阅 | ❌ 不接（禁止抓取，前面已定） |
| 汉典 / zdic 等 | 无公开 API | 禁止抓取 | ❌ |

### 三个设计后果

1. **入库而不是代理**：把 LSJ/L&S/CC-CEDICT 一次性转成 `lexicon.db`，
   运行时零网络、毫秒级、引用稳定；API 只在"本地没有"时兜底。
2. **CC BY-SA 是传染性的**：Perseus 数字化文本是 BY-SA，不是公版。
   派生的 `lexicon.db` 若分发，必须同样 BY-SA 并署名 Perseus；
   这与本仓 "数据不随仓库分发" 的既有策略一致——**留在本地即可**。
3. **API 兜底要可降级**：超时/限流/失效时返回"本地无此词条"，不要伪造。

### 若确实要运行时调用

```
GET /v1/lexicon?word=X&allow_remote=1
→ entries[].source = "local:lsj" | "remote:wiktionary"
→ 每条都带 license 与 retrieved_at；remote 结果不入库
```

默认 `allow_remote=0`，由使用者显式开启；响应里必须标明来源与许可。

## 7b. 句法 / 形态 API（2026-11-12 实测）

**有，而且一套服务覆盖三种语言**——但不是同一个接口。

| 能力 | 服务 | 覆盖 | 调用方式 | 结果 |
|---|---|---|---|---|
| **形态分析**（词形 → 词元 + 语法属性） | **Morpheus**（Perseus）`morph.perseids.org/analysis/word?word=&lang=&engine=` | 拉丁 `morpheuslat`、古希腊 `morpheusgrc` | GET，无 key，返回 RDF/JSON | `cano` → verb, 1st sg pres act（正确） |
| 形态分析 | Alpheios morph | 同上 | GET，`engine` 参数必须匹配（否则 404 unknown engine） | 同源 |
| **句法分析**（依存树） | **UDPipe REST**（LINDAT）`lindat.mff.cuni.cz/services/udpipe/api/process` | **古希腊**（perseus/proiel/ptnk）、**拉丁**（perseus/ittb/llct/udante/circse/proiel）、**文言**（`classical_chinese-kyoto`） | POST 表单，无 key | CoNLL-U：lemma/POS/feats/head/deprel |
| 句法（离线） | UDPipe 二进制 + 模型下载 | 同上 | 本地进程 | 同上 |
| 文言句法 | **没有专门的商业 API** | — | UDPipe 的 `classical_chinese-kyoto` 是当前唯一可用通道 | 见下 |

### 实测样例

```
# 古希腊（UDPipe perseus）
1 μῆνιν  μῆνις  NOUN  Case=Acc|Gender=Fem|Number=Sing  2 obj
2 ἄειδε   ἀείδω  VERB  Mood=Imp|...                     0 root

# 文言（UDPipe kyoto）
1 學  學  VERB  v,動詞,行為,動作   0 root
2 而  而  CCONJ p,助詞,接続,並列   4 cc
3 時  時  NOUN  n,名詞,時,*        4 obl:tmod
4 習  習  VERB  v,動詞,行為,動作   1 conj
```

### 质量警告（必须记住）

同一句拉丁文，两个服务给出不同答案：

| 词 | UDPipe（latin-perseus） | Morpheus |
|---|---|---|
| `cano` | `canus` **形容词**（错） | `cano` 动词 1st sg pres act（对） |
| `virumque` | `virumque` ADV（错） | — |

**结论：句法用 UDPipe，词形归调用 Morpheus。** 不要让句法模型的 lemma 直接进词典索引。

### 许可

UDPipe 的模型来自 UD 各树库，**许可逐库不同**（Perseus 系多为 CC BY-SA，
PROIEL 系为 CC BY-NC-SA，含非商用条款）。因此：

- 用哪个树库，就在 `documents.license` 记哪个；
- 若将来商用，需替换掉 NC 条款的模型。

### 架构建议：解析在构建期，不在每轮对话里

```
构建期：书 → 分句 → UDPipe（本地）→ CoNLL-U 入库（tokens/heads/deprels）
运行期：/v1/syntax?sentence=&lang=  只做短句、带缓存；查不到就走词典/语法书
```

理由：句法解析是 O(句长) 的重活，且结果对同一句是确定的——没有理由每轮重算。

## 7c. 汉语路线图（CC-CEDICT + Unihan），以及和拉丁/希腊的对比

汉语不能照搬拉丁/希腊的路线：**没有屈折变化，但有字形问题**；数字源也不同。

### 三类汉语材料，三个用途

| 材料 | 内容 | 许可 | 用途 |
|---|---|---|---|
| **CC-CEDICT** | 约 12 万条现代汉语词条（简/繁 + 拼音 + 英文释义） | CC BY-SA 4.0 | **现代汉语**词目与释义 |
| **Unihan** | 约十万字的读音（kMandarin/kHanyuPinyin）、异体/简繁映射（kSimplifiedVariant 等）、部首笔画（kRSUnicode）、英文释义（kDefinition） | Unicode License（宽松） | **字形归一与索引桥梁**，不是义项来源 |
| **康熙字典 / 说文解字** | 公版文言辞书（康熙 47,035 字头；说文 9,353 字、540 部首） | 文本公版；数字化转录多为 CC BY-SA | **文言文**义项来源 |
| 汉语大词典 / 现代辞书 | 权威但版权保护 | 仅本地 `personal` | 可选补充 |

关键缺口：**CC-CEDICT 是现代汉语，不是文言**。"之、乎、者、也"的文言义项必须来自康熙/说文或版权辞书。

### 与拉丁/希腊的对比

| 维度 | 拉丁 / 古希腊 | 汉语（文言） |
|---|---|---|
| 书写系统 | 拼音文字，空格分词 | 汉字，**无空格** |
| 词形变化 | 屈折丰富（格、数、时态、语态） | **无屈折** |
| 查询键 | 词元 `lemma` | **字头**（单字）；多字词需先分词 |
| 归一化难点 | 大小写、重音符号（希腊多调） | **繁简、异体字、新旧字形、通假字** |
| 词形还原 | 必需（λύομεν → λύω） | **不需要**；需要**分词 + 字形归一** |
| 词典排序 | 字母序（可做单调性质检） | **部首-笔画序**（另一种单调性质检） |
| 主数字源 | LSJ / Lewis & Short（Perseus TEI） | CC-CEDICT（现代）+ 康熙/说文（文言） |
| 主源许可 | CC BY-SA 4.0 | CC BY-SA 4.0 / 公版 / Unicode License |
| OCR 现状（本工程实测） | 希腊文 CER **0.709**（不可用） | 中文 CER **12.1%**（可用，需校对） |
| OCR 难点 | 多调符号、行末连字符 | 竖排、繁体、小字、异体、双栏 |
| 形态 API | Morpheus（拉丁/希腊，可用） | 无对应服务；Unihan 提供字形信息 |
| 句法 API | UDPipe（perseus/proiel 树库） | UDPipe `classical_chinese-kyoto`（研究级，覆盖有限） |
| 主要失败模式 | 词目拼错 → 查不到 | 繁简/异体没归一 → 查不到；分词错 → 查错词 |

### 三条设计结论

1. **汉语不需要 lemma 层，但必须有字形层**：`lexicon_headwords` 之外加一张
   `char_variants(cp, variant_of, kind)`（kind: simplified/traditional/variant/ancient），
   查询时先归一化再查。
2. **文言与现代汉语分开**：`documents.lang` 记 `lzh`（文言）或 `zh`（现代），
   不要把 CC-CEDICT 的现代义项当成文言义项返回。
3. **部首-笔画序替代字母序**做质检：康熙/说文的字头必须按部首+笔画非递减，
   违反处即 OCR 或切分错误。

### 汉语路线图

| 阶段 | 内容 | 产出 | 估时 |
|---|---|---|---|
| **C0** | 导入 **Unihan + CC-CEDICT**：建 `char_variants` 与现代汉语词条 | 字形归一 + 现代词条可查 | 1–2 天 |
| **C1** | 导入 **康熙/说文**（优先数字文本；纸本才 OCR）：按部首-笔画切字头 | 文言语义可查 | 3–5 天（含 OCR 则 +5–7 天） |
| **C2** | 文言分词与句法：字级切分 + UDPipe `classical_chinese-kyoto`（可选） | 长句可解析 | 2–3 天 |
| **C3** | 通假字/古今字表（人工维护，约数百条常用） | 查询命中率提升 | 1–2 天，持续补充 |

### 汉语质量门

| 门 | 阈值 |
|---|---|
| 繁简/异体归一覆盖率（常用 3500 字） | 100% |
| 字头字符准确率（OCR 部分） | ≥ 99.5% |
| 部首-笔画序违例率 | < 0.1% |
| 文言义项抽样正确率 | ≥ 90% |

## 8. 里程碑

| 阶段 | 内容 | 产出 | 估时 |
|---|---|---|---|
| **M0** | rag-build 侧：把 LSJ/L&S 导入为 `documents(kind=dictionary)` + `lexicon_headwords` | 一个可查的 `lexicon.db` | 2–3 天 |
| **M1** | sidecar：`/v1/lexicon` + 契约 + 测试 | 端到端可查词 | 2 天 |
| **M2** | 词形还原：simplemma + 规则表 + 每级 `matched_by` | 变格形式可命中 | 3–5 天 |
| **M3** | 语法书：小节切分 + 交叉引用 + **小节级向量索引** + `kind=grammar` 检索 | "什么是绝对夺格"可答 | 2–3 天 |
| **M4** | 插件工具 `lexicon_lookup` + critic/cite_verify 适配 | 教学流程可用 | 1–2 天 |
| M5 | 在线适配器（Perseus/Wiktionary） | 本地缺失时兜底 | 3 天 |
| M6 | 句法：UDPipe 本地解析 + `/v1/syntax` + 构建期入库 | "这句为什么用与格"可解释 | 3–4 天 |
| **C0–C3** | 汉语独立一路：Unihan+CC-CEDICT → 康熙/说文 → 分词句法 → 通假表 | 文言可查 | 7–12 天（不含 OCR） |

## 9. 评测

| 指标 | 方法 | 目标 |
|---|---|---|
| 词条命中率（词典） | 100 条"变格形式→词元"金标 | ≥ 95% |
| 义项正确率（词典） | 同一批取首义项，人工判 | ≥ 90% |
| 语法主题 R@5（语法书） | 50 条概念问题 | ≥ 0.9 |
| 节号/交叉引用（语法书） | 抽样解析核对 | ≥ 90% |
| 延迟（词典查表） | 单次查词 | < 50 ms |
| 延迟（语法检索） | 概念查询 | 与 `kb_search` 同量级 |

金标先人工写 30 条跑通，再扩到 100 条；不要先用模型生成金标。

## 10. 风险

| 风险 | 影响 | 对策 |
|---|---|---|
| 词形还原覆盖不足 | 查不到 = 功能不可用 | 多级兜底 + `matched_by` 透明 |
| 词典版权 | 不能分发 | `license` 字段 + 导出限制 |
| 一词多义 | 首义项未必是语境义 | 返回前 3 个义项 + 词性过滤；后续可用语境排序 |
| 中文异体/繁简 | 查不到 | 归一化表 + 人工补充 |
| 数据量大 | 索引膨胀 | 只索引 headword，不进向量 |

## 11. 需要你决定

1. 手上有哪些词典/语法书？（决定 M0 的范围与许可）
2. 是否接受 Wiktionary（CC BY-SA）作为兜底？这会影响仓库的许可证表述。
3. 中文侧用哪部字典？（公版《康熙字典》《说文》可取；现代辞书只能本地用）
