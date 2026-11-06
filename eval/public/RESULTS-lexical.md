# 词法通道评估（12 条变格）

数据：`eval/public/queries-lexical.jsonl`。查询形式不是原文子串，例如
`μῆνις` vs `μῆνιν`、`irae` vs `iram`。

| mode | R@1 | R@3 | R@5 | MRR@5 |
|---|---:|---:|---:|---:|
| FTS | 0.000 | 0.083 | 0.083 | 0.042 |
| grep | 0.000 | 0.000 | 0.000 | 0.000 |
| lemma（降级词干） | 0.583 | 0.917 | 0.917 | 0.750 |
| **lemma / fusion（simplemma 2.0）** | **0.667** | **1.000** | **1.000** | **0.833** |

- `fusion` = v2 `search()`：FTS/BGE + grep 2.0 + lemma 1.3 的 RRF 合并。
- 在这组查询上 fusion 与纯 lemma 同分：grep 无命中、FTS 很弱。
- 复现：`python scripts/eval_lexical.py --db data/public.db`
  （有 simplemma 时把 `D:\Guo-Code\temp\nlp_libs` 放进 `PYTHONPATH`）。
