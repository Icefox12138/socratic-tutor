# v1 检索提升 + 统一检索交接（2026-11-06）

| 项 | 值 |
|---|---|
| 范围 | v1 P1 100 问；v1+v2 `scope=all` 联邦检索 |
| 状态 | **完成并实测**；未提交 git |
| 测试 | sidecar **259/259**（上一轮 243 + 新 3 路由 + 计算测试） |
| v1 主结果 | BGE 0.760 → **bge+llm 0.80–0.82** R@10；R@1 0.540 不变 |
| 统一检索 | `scope=all` 合并；`scope=routed` 路由；真实两库冒烟通过 |

---

## 0. 一句话

v1 用“**只翻译非中文查询 + base top-1 锚定**”把 page recall@10 从 **0.760**
提到 **0.820**，中文题 top-1 不变；同时新增 `scope=all`，把 v1 私有库和
v2 公开语料按 RRF 合并。

## 1. v1 结果（P1 100 问）

| mode | R@1 | R@3 | R@10 | MRR@10 | median ms |
|---|---:|---:|---:|---:|---:|
| fts | 0.400 | 0.520 | 0.600 | 0.467 | 76.6 |
| bge | 0.540 | 0.670 | 0.760 | 0.621 | 697.9 |
| **bge+llm（选择性翻译）** | **0.540** | **0.690–0.710** | **0.800–0.820** | **0.640** | 800 |

分语言 R@10：

| lang | n | bge | bge+llm |
|---|---:|---:|---:|
| zh | 58 | 0.931 | 0.931 |
| en | 10 | 0.500 | **0.700** |
| greek | 12 | 0.417 | **0.417–0.583** |
| latin | 20 | 0.600 | **0.700** |

- 中文 top-1 **0.724 不变**；
- 跨语言（en+el+la 42 题）**0.524 → 0.667**；
- v1 多次运行有 LLM 方差：总体 0.80–0.82，希腊 0.417–0.583；
- 仍低于 0.85；跨语言仍差 0.70 约 3.3 点。

### 1a. 希腊专项：做了什么、为什么没稳定提升

实现了 **v1 希腊 lemma 倒排索引**：只索引 33,674 个 Greek chunks，构建约 2.1 s，
查询约 25 ms；把 LLM 译出的希腊词（特别是专名/变格）按 lemma 匹配回原文。
代码在 `lexical.greek_lemma_search`，开关 `SOCRATIC_V1_GREEK_LEMMA=1`。

实测：
- 最好一次希腊 R@10 **0.667**（新增 Odyssey φάσκε、Herodotus Pythia 两页）；
- 但会挤掉英文/拉丁题，且 LLM 非确定；默认 **关闭**（`SOCRATIC_V1_GREEK_LEMMA=0`）。
- Attic 专用提示词试过：单独希腊可到 0.667，但整体掉到 0.77，未采用。
- 根因：① 同一作品不同 edition 页号不同（Bacchae 16 vs 44）；
  ② 部分页面是英文注释，希腊词形不在页上；③ LLM 译词不在原文；
  ④ 12 题样本太小，单题波动就是 8 个百分点。

结论：**希腊 0.583 不是单纯词形问题**，当前没有稳定、不伤其他语言的提升；
保留希腊 lemma 为 opt-in 实验通道。

**英文注释页索引**（第二方案）也实现了：`lexical.commentary_search`，把
Greek/Latin 书中英文占比 >65% 的 chunks 单独建词袋索引（约 60k 行）。
实测反而更差：整体 **0.75**、希腊 **0.333**，因为页级词袋丢失语序/搭配，
把“注释页”匹配成其他书的注释。默认关闭（`SOCRATIC_V1_COMMENTARY=0`）。

**edition 页号对齐**（第三方案）：`editions.py` 用希腊/拉丁词集合做页指纹，
把同作品其它 edition 的对应页补进结果。Bacchae p44 能对齐到 p16/17，
单题可修；但希腊整体 **0.583→0.5**（低相似度邻页形成噪声），默认关闭
（`SOCRATIC_V1_EDITION_ALIGN=0`）。三个方案都失败，说明需要真正的
**行号/Stephanus 引用对齐**，而不是整页词袋。

## 2. v1 改了什么

1. **选择性翻译**：只对**非中文查询**调 LLM（`SOCRATIC_V1_TRANSLATE_NONCJK_ONLY=1`）。
   P1 的希腊/拉丁题是英文问句；中文题指向中文书，翻译是噪声。
2. **base top-1 锚定**：翻译变体只补召回，原查询第一名固定 rank 1
   （全量翻译时 R@1 会掉到 0.37）。
3. **按页去重**：v1 金标是页，top-10 同一页只留一个 chunk。
4. **grep 融合**：精确串作为额外 RRF 列表；概念题通常无命中，不影响。
5. **可选加宽**：`SOCRATIC_BGE_TOPK` / `SOCRATIC_RERANK_TOPK=100` 只到 0.770，
   延迟翻倍，不默认。

开关：

```powershell
$env:SOCRATIC_V1_RETRIEVAL="1"       # 默认 0，保持旧路径
$env:SOCRATIC_TRANSLATE="llm"        # 或 glossary（对英文题基本无效）
$env:SOCRATIC_V1_TRANSLATE_NONCJK_ONLY="1"
```

## 3. 统一检索

```http
GET /v1/search?q=arma&scope=all&limit=8      # 合并两库
GET /v1/search?q=黃帝&scope=routed&limit=8   # 路由到一个库
```

- `scope=auto`（默认）：只查当前库，行为不变。
- `scope=all`：v1 + v2 各查一次，按 RRF 合并，每条结果带 `schema`。
- `scope=routed`：每个库一次 FTS 探针（limit 3），按语言/覆盖选一个库；
  选中库 0 命中才 fallback 到另一库，不做双查。
  - 中国史标记/`史記`/`Iliad`/`Aeneid`/短希腊引文 → v2；
  - 现代中文/英文/拉丁 → v1；
  - 实测：`黃帝`→v2、`史記`→v2、`μῆνιν`→v2、`量子力学`→v1、`arma`→v1、
    `Achilles`→v1。

## 4. 文件

| 文件 | 作用 |
|---|---|
| `sidecar/app/federated.py` | 两库串行搜索 + RRF 合并 + `routed` 路由 + 配置锁 |
| `sidecar/app/lexical.py` | `greek_lemma_search` / `commentary_search`（均 opt-in） |
| `sidecar/app/editions.py` | 跨 edition 页指纹对齐（opt-in） |
| `sidecar/app/search.py` | v1 enhanced 路径；`scope` 分派 |
| `sidecar/app/config.py` | `V1_RETRIEVAL`、选择性翻译、锚定、去重、BGE topk |
| `sidecar/app/main.py` | `/v1/search?scope=` |
| `sidecar/tests/test_federated.py` | 合并/答案隔离/端点 |
| `scripts/eval_v1.py` | P1 100 问 v1 评估 |
| `eval/v1/RESULTS.md` | v1 数字 |
| `docs/FEDERATED-SEARCH.md` | 统一检索契约 |

## 5. 边界

1. v1 **0.80–0.82 仍低于 0.85**；跨语言 0.667 < 0.70。
2. 希腊 **0.417–0.583**，没有稳定提升；希腊 lemma 默认关闭。
3. 选择性翻译依赖 LLM key；无 key 退回 0.760；LLM 有方差。
4. `scope=all` 只合并两库各 top-limit；`scope=routed` 是启发式，不是学习路由。
5. `book`/`document_id` 在两库语义不同；跨库过滤会写 `errors`。
6. BGE 全开时 v1/v2 各一份模型/向量，8 GB 卡显存吃紧。
7. 100 题是 LLM 生成、page 级金标，不是人工答案级评估。

## 6. 下一步

1. 希腊：edition 对齐/页号映射，或把英文注释页单独索引。
2. 跨语言到 0.70：翻译质量 + 选择性 rerank。
3. 路由加学习/统计阈值，而不是手写信号。
4. 真实学生问句/答案级评估。
5. 提交与发布。
