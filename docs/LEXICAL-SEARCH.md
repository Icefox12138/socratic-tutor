# 词法通道：grep / lemma（2026-11-06）

| 项 | 值 |
|---|---|
| 实现 | `sidecar/app/lexical.py`、`GET /v1/grep`、`GET /v1/lemma` |
| v1 | grep 可用（页级引用）；lemma 不可用 |
| v2 | grep + lemma（干净文本，locator/URL 引用） |
| 可选依赖 | `simplemma>=2.0`；缺失时用后缀词干降级 |
| 测试 | sidecar **240**（新增 18：13 词法 + 5 融合） |
| inflected 评估 | FTS 0.083、grep 0.000、lemma 0.917（无 simplemma）/ **1.000**（simplemma）R@5 |

---

## 0. 一句话

`grep` 解决**精确串**（引文、人名、公式、标识符），`lemma` 解决**词形变化**
（`ira` ↔ `iram`、`μῆνις` ↔ `μῆνιν`）。两者都是补充通道，不替代 FTS/BGE。

## 1. 端点

```http
GET /v1/grep?q=&view=&limit=&source=&lang=&book=&document_id=&section=
GET /v1/lemma?q=&view=&limit=&source=&lang=&book=&document_id=&section=
```

- `view=student|tutor`；两者都只返回 `visibility='tutor'` 的行。
- `source/lang/book/document_id/section` 过滤与 `/v1/search` 同义。
- `limit` 1..50，默认 20。

响应：

```json
{"query": "μῆνις", "view": "student", "schema": "v2", "mode": "lemma",
 "results": [{"chunk_id": 1, "document_id": "...", "section": "1.1",
              "citation": {"scheme": "cts", "locator": "Iliad 1.1", "url": "..."},
              "match": {"coverage": 1.0, "lemmas": ["μῆνις"], "exact": false}}],
 "took_ms": 3.2}
```

`grep.match`：`{start, end, snippet, count}`。  
`lemma.match`：`{coverage, lemmas, exact}`。

## 2. grep 语义

- Unicode `casefold()` 子串匹配；一个 chunk 只返回一次，`count` 是出现次数。
- SQL 先用 `instr()` 收窄；v2 小库在 accented 大写查询无命中时回退内存扫描。
- 返回的 `citation` 与搜索一致：v2 是 `scheme/locator/url`，v1 是页图 locator。
- **不是** `/v1/verify`：`verify` 会去标点/空白后做引文校验；grep 是原样子串检索。

## 3. lemma 语义

- 只支持 **v2** 干净文本；v1 PDF 页返回 400（没有可重建的 lemma 索引）。
- 查询词：
  - 中文：二元组（与 FTS 一致），不做词形；
  - 希腊/拉丁：`simplemma`（`grc`/`la`）给出的 lemma，**并集**一个后缀词干；
  - 简单词干：希腊/拉丁常见变格后缀剥离 + 前 4 字符。
- chunk 侧缓存所有词的 lemma 集合；按 IDF 加权覆盖率排序，`min_coverage=0.5`。
- 规模保护：`SOCRATIC_LEMMA_SCAN`（默认 50000）截断，响应带 `truncated`。
- `simplemma` 未安装时仍可工作，但希腊/拉丁 irregular 形式会漏。

## 4. 实测

数据集：`eval/public/queries-lexical.jsonl`（12 条变格查询，希腊 5 / 拉丁 7）。
查询形式故意不是原文子串（如 `μῆνις` vs `μῆνιν`、`irae` vs `iram`）。

| mode | R@1 | R@3 | R@5 | MRR@5 |
|---|---:|---:|---:|---:|
| FTS | 0.000 | 0.083 | 0.083 | 0.042 |
| grep | 0.000 | 0.000 | 0.000 | 0.000 |
| lemma（无 simplemma） | 0.583 | 0.917 | 0.917 | 0.750 |
| **lemma / fusion（simplemma 2.0）** | **0.667** | **1.000** | **1.000** | **0.833** |

`fusion` = `/v1/search` 把 FTS/BGE 与 grep/lemma 列表按 RRF 合并；在这组变格
查询上它与纯 lemma 同分，因为 grep 无命中、FTS 很弱。

复现：

```powershell
# 降级词干
python scripts/eval_lexical.py --db data/public.db

# 有 simplemma
$env:PYTHONPATH="D:\Guo-Code\temp\nlp_libs"
python scripts/eval_lexical.py --db data/public.db
```

## 5. 融合进主检索

- `SOCRATIC_LEXICAL=auto`（默认）/ `off`。
- v2 `search()` 在原有 base + 翻译变体列表之外追加：
  - grep 列表，权重 **2.0**（精确串优先）；
  - lemma 列表，权重 **1.3**（变格补充）。
- 触发条件：
  - 原文总是跑 grep；翻译变体只在**单关键词**时跑 grep（多词关键词串不做整句匹配）；
  - lemma 只对含希腊/拉丁/英文词的查询跑（纯中文跳过，避免二元组噪声）。
- 响应 `"lexical": {"grep": n, "lemma": n}`；关闭时为 0。
- 130 人工题：bge+auto 0.854/0.969 → bge+auto+lex **0.862/0.977**，MRR 0.906→0.915；
  中文词面 R@1 0.9→1.0、中→希腊 R@1 0.583→0.75；中文语义 top-1 有轻微波动。

## 6. 工具

- 插件：`lexical_search`（`mode=grep|lemma`）。
- MCP：`kb_lexical`（同参数）。
- 契约探针：若服务暴露 `/v1/grep`/`/v1/lemma`，`contract_check.py` 会额外探测。

## 7. 边界

1. **lemma 只支持 v2**；v1 需要先建 lemma 索引或只做 grep。
2. 降级词干是启发式，可能误合并（共享前 4 字符）；`simplemma` 更好但拉丁也有错例。
3. grep 没有正则/邻近/模糊匹配；复杂查询用 FTS/BGE。
4. **融合已实现**，但权重是经验值；中文语义题仍可能被词法列表抢 top-1。
5. 中文 lemma 实际是二元组匹配，和 FTS 很接近，收益主要在希腊/拉丁。
6. 单个希腊/拉丁词的 lemma 查询会有很多共享词干的候选，靠 IDF/覆盖率排序，不保证 top-1。
