# v1 私有 PDF 检索评估（P1 100 问）

| 项 | 值 |
|---|---|
| 库 | `D:\Guo-Code\rag-build\data\indexes\search.db`（167,192 chunks；tutor 148,261） |
| 向量 | `bge-vectors.npy`（148,261×1024 fp16） |
| 题集 | `rag-build/eval/p1/eval/questions.json`（100 问；zh 58 / latin 20 / greek 12 / en 10） |
| 金标 | source + book + page；**page recall@10** |
| 基线段 | BGE-M3 + FTS RRF + rerank：**R@10 0.760** |
| 提升段 | 仅非中文查询做 LLM 翻译 + base top-1 锚定：**R@10 0.80–0.82** |
| 希腊 | **0.417–0.583**（多次运行）；专项 lemma 未稳定超过 0.583 |
| 判定 | 达到历史 0.82 区间；仍低于 0.85；跨语言 0.667 < 0.70 |

## 1. 总体

| mode | R@1 | R@3 | R@10 | MRR@10 | median ms |
|---|---:|---:|---:|---:|---:|
| fts | 0.400 | 0.520 | 0.600 | 0.467 | 76.6 |
| bge | 0.540 | 0.670 | 0.760 | 0.621 | 697.9 |
| **bge+llm（仅非中文翻译）** | **0.540** | **0.690–0.710** | **0.800–0.820** | **0.640** | 800 |

多次运行有 LLM 方差；0.820 是最好一次，0.800 是最近一次。

## 2. 分语言 R@10

| lang | n | bge | bge+llm |
|---|---:|---:|---:|
| 中文 zh | 58 | 0.931 | 0.931 |
| 英文 en | 10 | 0.500 | **0.700** |
| 希腊 greek | 12 | 0.417 | **0.417–0.583** |
| 拉丁 latin | 20 | 0.600 | **0.700** |

中文 top-1 完全不变（0.724）；跨语言（en+el+la 42 题）从 **0.524 → 0.667**。

## 3. 做了什么

1. **只翻译非中文查询**：P1 的希腊/拉丁题是英文问句；中文题指向中文书，
   翻译只会加噪声。`SOCRATIC_V1_TRANSLATE_NONCJK_ONLY=1`（默认）。
2. **Base top-1 锚定**：翻译变体只补召回；原查询第一名固定在 rank 1，
   避免 LLM 变体抢 top-1（之前全量翻译 R@1 0.370）。
3. **按页去重**：v1 金标是页；top-10 中同一页只保留一个 chunk。
4. **grep 融合**：v1 精确串作为额外 RRF 列表（对概念题通常无命中，不影响）。
5. **可选加宽**：`SOCRATIC_BGE_TOPK` / `SOCRATIC_RERANK_TOPK`；
   100/100 只把 R@10 提到 0.770，延迟翻倍，不默认。

## 3. 希腊专项（未稳定提升）

实现了 v1 希腊 lemma 倒排索引（33,674 chunks，构建 2.1 s，查询 25 ms）：
`lexical.greek_lemma_search`，开关 `SOCRATIC_V1_GREEK_LEMMA=1`。
- 最好一次希腊 R@10 **0.667**；但会挤掉英文/拉丁题，默认关闭。
- Attic 专用提示词：单独希腊 0.667，整体掉到 0.77，未采用。
- 根因：不同 edition 页号、英文注释页、译词不在原文、12 题样本过小。
- 结论：希腊 0.583 不是单纯词形问题，当前没有稳定且不伤其他语言的提升。
- **英文注释页索引**（第二方案）：把 Greek/Latin 书中英文占比 >65% 的 chunks
  单独建词袋索引；实测整体 **0.75**、希腊 **0.333**，默认关闭
  （`SOCRATIC_V1_COMMENTARY=0`）。
- **edition 页号对齐**（第三方案）：`editions.py` 用页指纹补同作品其它
  edition 的对应页；Bacchae 单题可修，但希腊整体 **0.583→0.5**，默认关闭
  （`SOCRATIC_V1_EDITION_ALIGN=0`）。
- 下一步需要 **行号/Stephanus 引用对齐**，而不是整页词袋。

## 4. 配置

```powershell
$env:SOCRATIC_V1_DB="D:\Guo-Code\rag-build\data\indexes\search.db"
$env:SOCRATIC_V1_BGE_VECTORS="D:\Guo-Code\rag-build\data\vectors\bge-vectors.npy"
$env:SOCRATIC_V1_BGE_IDS="D:\Guo-Code\rag-build\data\vectors\bge-ids.npy"
$env:SOCRATIC_V1_RETRIEVAL="1"
$env:SOCRATIC_TRANSLATE="llm"
$env:SOCRATIC_V1_TRANSLATE_NONCJK_ONLY="1"
```

## 5. 边界

- 100 题是 LLM 生成，可能有词面重叠；page 级金标，不是答案级。
- 仍低于 **0.85** 目标；跨语言 **0.667 < 0.70**。
- LLM 翻译只对 32 条非中文查询调用；无 key 时退化为纯 BGE 0.760。
- 中文题 0.931 是当前强项；希腊 0.583 仍是最弱项。
