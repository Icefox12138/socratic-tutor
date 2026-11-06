# 公开语料检索评估（2026-11-05，43 问）

> **历史版本**：43 问 / 4 书 / 87 chunks。扩大版见
> [RESULTS-130.md](RESULTS-130.md)（130 问 / 7 书 / 331 chunks）；小集数字偏乐观，
> 两套口径不要混用。

| 项 | 值 |
|---|---|
| 库 | `data/public.db`（4 个文档 / **87 chunks**） |
| 文档 | 史記/卷001、史記/卷002、Iliad 1.1–1.10、Aeneid 1.1–1.16/20 |
| 查询 | **43** 条（`eval/public/queries.jsonl`） |
| 判定 | top-k 中任一结果的 `document_id` + `section` 与 gold 完全一致 |
| 环境 | 4060 8 GB；BGE-M3 + bge-reranker-v2-m3 |

## 1. 总体

| mode | n | R@1 | R@3 | R@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| fts | 43 | 0.512 | 0.535 | 0.535 | 0.523 |
| **fts+tr** | 43 | **0.907** | 0.977 | **0.977** | **0.942** |
| bge | 43 | 0.651 | 0.698 | 0.721 | 0.679 |
| **bge+tr** | 43 | **0.907** | 0.953 | **0.977** | 0.936 |
| fts+llm | 43 | 0.884 | 0.977 | 0.977 | 0.930 |
| bge+llm | 43 | 0.884 | 0.953 | 0.977 | 0.924 |

`tr` = 离线词表翻译；`llm` = LLM 翻译。LLM 没有超过词表（R@1 0.884 vs 0.907），词表版是默认。

## 2. 分语言/子集（R@5）

| subset | n | fts | fts+tr | bge | bge+tr |
|---|---:|---:|---:|---:|---:|
| zh-lexical | 11 | 1.000 | 1.000 | 1.000 | 1.000 |
| zh-semantic | 5 | 0.600 | 1.000 | 1.000 | 1.000 |
| zh-to-greek | 7 | 0.000 | 1.000 | 0.714 | 1.000 |
| zh-to-latin | 6 | 0.000 | 1.000 | 0.000 | 1.000 |
| el-lexical | 4 | 1.000 | 1.000 | 1.000 | 1.000 |
| la-lexical | 5 | 1.000 | 1.000 | 1.000 | 1.000 |
| en-lexical | 5 | 0.000 | 0.800 | 0.200 | 0.800 |

读法：
- 中文→希腊/拉丁：**词表翻译是决定性的**（0 → 1.000）；BGE 不行（zh→latin 0）。
- 中文语义（简繁/别名）：BGE 1.000，FTS 0.600；翻译把它补到 1.000。
- 希腊/拉丁词面：FTS 已经 1.000，BGE/翻译没有额外收益。
- 英文 query：0.800；`Aeneas` 未命中（Aeneid 前 20 行没有出现 Aeneas 这个名字）。

## 3. 延迟（单查询中位数）

| mode | median | max | 说明 |
|---|---:|---:|---|
| fts | 0.8 ms | 1.5 ms | 纯词法 |
| fts+tr | 2.2 ms | 10.4 ms | 词表翻译，无模型 |
| bge | 522 ms | 7.17 s | max 含首次模型加载 |
| bge+tr | 515 ms | 587 ms | 翻译变体走 FTS，原查询走 BGE |
| fts+llm | 994 ms | 1.44 s | 每条查询一次 LLM |
| bge+llm | 1453 ms | 3.26 s | LLM + BGE |

## 4. 结论与决策

1. **翻译通道是最大的单项收益**：R@5 从 0.535 提到 0.977。
2. **词表翻译足够，LLM 不是默认**：LLM 没有超过词表（R@1 0.884 vs 0.907），
   且慢 ~1 s/查询、非确定；默认 `SOCRATIC_TRANSLATE=glossary`，需要开放词表
   外用 `auto`/`llm`。
3. **翻译变体走 FTS，原查询走 BGE**：早期让变体也走 BGE 时，重排把 `Iliad 1.6` 这类短句排到前面，R@1 只有 0.558；改成变体 FTS 后 R@1 0.884。
4. **同脚本变体降权**（zh→zh-classical 权重 0.8）：避免中文别名压过原查询，zh-semantic 从 0.4 回到 1.0。
5. **BGE 仍有用**：对没有词表覆盖的开放语义有 0.721；但它不能替代翻译。
6. **变体顺序固定 + 覆盖度平票**：RRF 跨语言平票时按“命中该变体词项数”排序，
   而不是插入顺序；这消除了同一条查询在不同进程里 top-1 漂移（Achilles 曾
   在 Iliad 1.1 与 Aeneid 1.4 之间跳），R@1 从 0.884 提到 0.907。
7. **不要把这个 0.977 与 P1 的 0.82 直接比较**：这里是 4 本书、87 chunks、43 条、页/行级 gold，且查询围绕已有文档构造；P1 是 100 问跨 167k chunks。

## 5. 剩余失败

仅 `en-03 "Aeneas"`：Aeneid 1.1–1.16/20 的文本里没有 `Aeneas` 这个名字（只有 `Arma virumque`），gold 却指向 1.1。属于查询/语料边界，不是排序错误。

## 6. 复现

```powershell
cd D:\Guo-Code\socratic-tutor
$env:HF_HOME="D:\Guo-Code\socratic-tutor\data\hf-cache"
python scripts/eval_public.py --db data/public.db `
  --modes fts,fts+tr,bge,bge+tr,fts+llm,bge+llm --k 5 --show-misses
```
