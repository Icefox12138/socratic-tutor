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

- 只对 `headword` / `lemma` 建索引，**不建向量**；
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
| Perseus 的词典 XML | 多为公版/CC | ⚠️ 逐文件核对 |
| Wiktionary | CC BY-SA | ⚠️ 需署名 + 相同方式共享，**不能只写 MIT** |
| 王力《古汉语字典》等现代辞书 | 版权保护 | ❌ 仅本地 personal |
| 现代语法书（如 Cambridge Grammar） | 版权保护 | ❌ 仅本地 personal |

因此 `documents.license` 与 `documents.redistribution` 必须在入库时填写，
`/v1/lexicon` 原样返回；导出/分享工具按这两个字段拒绝。

## 7. 在线适配器（可选，最后做）

| 源 | 接口 | 注意 |
|---|---|---|
| Perseus | CTS + 词典文本 | 429 限流，需缓存 |
| Wiktionary | MediaWiki API | CC BY-SA，需署名 |
| 本地词典 | — | 默认路线，离线可用 |

原则：**离线优先**；在线适配器只做"本地没有时的补充"，并在响应里标注来源。

## 8. 里程碑

| 阶段 | 内容 | 产出 | 估时 |
|---|---|---|---|
| **M0** | rag-build 侧：把 LSJ/L&S 导入为 `documents(kind=dictionary)` + `lexicon_headwords` | 一个可查的 `lexicon.db` | 2–3 天 |
| **M1** | sidecar：`/v1/lexicon` + 契约 + 测试 | 端到端可查词 | 2 天 |
| **M2** | 词形还原：simplemma + 规则表 + 每级 `matched_by` | 变格形式可命中 | 3–5 天 |
| **M3** | 语法书：入库 + `kind=grammar` 检索 + 工具参数 | "什么是绝对夺格"可答 | 2 天 |
| **M4** | 插件工具 `lexicon_lookup` + critic/cite_verify 适配 | 教学流程可用 | 1–2 天 |
| M5 | 在线适配器（Perseus/Wiktionary） | 本地缺失时兜底 | 3 天 |

## 9. 评测

| 指标 | 方法 | 目标 |
|---|---|---|
| 词条命中率 | 100 条"变格形式→词元"金标 | ≥ 95% |
| 义项正确率 | 同一批取首义项，人工判 | ≥ 90% |
| 语法主题 R@5 | 50 条概念问题 | ≥ 0.9 |
| 延迟 | 单次查词 | < 50 ms（本地索引） |

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
