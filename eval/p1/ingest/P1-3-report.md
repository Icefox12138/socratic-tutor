# P1-3 统一检索层：合并 + bigram + 20 条复跑

| 项 | 值 |
|---|---|
| 日期 | 2026-10-30 |
| 输入 | `steadman.db` 77,820 + `library.db` 87,566 + Teubner Conte 1,805 + canary 1 |
| 输出 | `search.db`（167,192 chunks，295.9 MB） |
| 结论 | **PASS（FTS bigram）；BGE-M3 未跑，明确挂起** |

## 1. 验收

| 指标 | 实测 | 门槛 | 判定 |
|---|---:|---:|---|
| chunks | 167,192 | — | — |
| recall@10（D4 20 条） | **1.00** | ≥0.85 | PASS |
| p95 延迟 | **8.2 ms** | <1 s | PASS |
| mean 延迟 | 3.2 ms | — | PASS |
| canary（student） | **0** | 0 | PASS |

> 口径说明：20 条是**词项查询**，测的是“能不能找到”，不是语义相关性；1.0 不代表语义检索好，只代表索引与过滤正确。

## 2. 中文 bigram 修复

P1-2 发现 trigram 不匹配 2 字中文。本版把索引文本改为：

- CJK 连续串 → **bigram**（`帝国主义` → `帝国 国主 主义`）；
- 拉丁词 → 小写词；
- 查询同样切分，`MATCH` 引号短语。

结果：`微分/极限/矩阵/函数/资本/革命` 全部命中，20/20。

## 3. BGE-M3：为什么没跑

不是忘了，是三个硬约束：

1. **模型体积**：BGE-M3 约 2.3 GB；本机网络在 P1-0/P1-1 多次出现下载中断。
2. **CPU 成本**：167k chunks × 1024d，CPU 编码估计 **2–4 小时**；本机 8 GB 显存放不下 batch。
3. **收益**：P1-3 的验收是 recall/延迟/隔离；词项查询下 bigram 已 1.0，语义层增量要等“自然语言问句”评估集才能量出来。

处置：

- `search.db` 预留 `embedding` 列与 RRF 接口；
- P2 前用 GPU 或云 API 跑 BGE-M3，重跑“问句级”评估（不是词项）；
- 在此之前，检索用 **bigram FTS**，语义缺失用 rerank/LLM 查询改写补。

## 4. 语料构成

| 来源 | chunks | 说明 |
|---|---:|---|
| Steadman | 77,820 | 含 18,930 `answer_key`（transsheets） |
| 馆藏文字版 | 87,566 | 61 本，中文 56 / 英文 5 |
| Teubner Conte | 1,805 | 拉丁原典 |
| canary | 1 | `answer_key`，检索不可见 |

## 5. 产物

`search.db`、`search-eval.json`、`build_search.py`；P1-1/P1-2 的库保留为分源版本。

## 6. 下一步

- P1-4：页图按需渲染 + 引用回看（`search.db` 的 `book/page` 已足够）；
- P1-3b（可并行）：GPU/云上跑 BGE-M3，补问句级评估；
- P1-5：质量闸门。
