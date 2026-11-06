# 人工题集 + OOV 闸门交接（2026-11-06）

| 项 | 值 |
|---|---|
| 日期 | **2026-11-06** |
| 项目 | `D:\Guo-Code\socratic-tutor` |
| 范围 | 130 条人工题；OOV/领域闸门；LLM 变体权重；默认翻译模式 |
| 状态 | **完成并实测**；未提交 git |
| 测试 | sidecar **222/222**（上一轮 220 + 新 2） |
| 主结果 | **bge+auto：R@1 0.838 / R@5 0.977 / MRR 0.899** |
| 未知子集 | 0.625 → **1.000**（auto 只对 8 条 OOV 调 LLM） |

> **后续**：grep/lemma 已融合进 v2 检索；最新综合数字见
> [HANDOFF-2026-11-06-lexical.md](HANDOFF-2026-11-06-lexical.md) 与
> `eval/public/RESULTS-project.md`。

---

## 0. 一句话

把 34 条自动前缀题换成人工题，并给 `auto` 加了两道闸门：**OOV 才调 LLM**、
**中国史问题不调 LLM**。结果 `bge+auto` 全面超过 `bge+词表`：
R@5 0.938→0.977、R@1 0.815→0.838；未知子集 0.625→1.000。

---

## 1. 变更

### 题集

| 文件 | 内容 |
|---|---|
| `eval/public/queries-human.jsonl` | **主集 130 问**，无自动前缀 |
| 组成 | zh-lexical 10、zh-semantic 53、zh-to-greek 12、zh-to-latin 12、el 13、la 12、en 10、zh-unknown 8 |
| `eval/public/queries-130.jsonl` | 上一版 130（含 34 条自动前缀），保留为历史对照 |

### 闸门

1. **OOV 检测**（`translate.oov_terms`）：
   - 把词表命中片段挖掉，去掉虚词/疑问词；
   - 剩余 CJK 连续 ≥2 字或 ≥3 字母的词 = OOV；
   - `克鲁塞斯`、`银弓之神`、`Chryses` 为 OOV；`阿喀琉斯的愤怒`、`Achilles` 不是。
2. **中国史领域闸门**（`ZH_HISTORY_MARKERS`）：
   - 命中周文王/秦孝公/商鞅/纣王/史記/本紀… 等约 50 个词时不调 LLM；
   - 因为目标语料是中文，LLM 只能给希腊/拉丁/英文关键词，纯属噪声。
3. **LLM 变体权重 1.0**（词表 1.5、中文别名 0.8）：
   - LLM 只补召回，不压过原查询；之前 1.5 会把 zh-semantic 的 top-1 拉低。
4. **默认 `SOCRATIC_TRANSLATE=auto`**：
   - 无 key → 纯词表；有 key → 只对 OOV 调 LLM（中国史题仍不调）。

---

## 2. 主结果（130 人工题，k=5）

| mode | R@1 | R@3 | R@5 | MRR@5 |
|---|---:|---:|---:|---:|
| fts | 0.423 | 0.523 | 0.577 | 0.480 |
| fts+词表 | 0.554 | 0.700 | 0.762 | 0.633 |
| bge | 0.777 | 0.892 | 0.892 | 0.828 |
| bge+词表 | 0.815 | 0.938 | 0.938 | 0.872 |
| **bge+auto** | **0.838** | **0.946** | **0.977** | **0.899** |

分语言 R@5：

| subset | n | fts | fts+词表 | bge | bge+词表 | bge+auto |
|---|---:|---:|---:|---:|---:|---:|
| zh-lexical | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| zh-semantic | 53 | 0.755 | 0.792 | 0.962 | 0.962 | 0.962 |
| zh-to-greek | 12 | 0.000 | 0.667 | 0.667 | 1.000 | 1.000 |
| zh-to-latin | 12 | 0.000 | 0.667 | 0.833 | 0.917 | **1.000** |
| el-lexical | 13 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| la-lexical | 12 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| en-lexical | 10 | 0.000 | 0.600 | 0.700 | 0.800 | **0.900** |
| zh-unknown | 8 | 0.000 | 0.000 | 0.625 | 0.625 | **1.000** |

## 3. 未知子集（8 条）

| mode | R@1 | R@5 | MRR@5 |
|---|---:|---:|---:|
| fts / fts+词表 | 0.000 | 0.000 | 0.000 |
| bge / bge+词表 | 0.500 | 0.625 | 0.562 |
| **bge+auto** | **0.875** | **1.000** | **0.906** |
| bge+LLM | 0.875 | 1.000 | 0.906 |

全量 130 里 zh-unknown 的 R@1 记录为 0.750；LLM 非确定，单独跑为 0.875，
报告取区间。

## 4. 延迟

| mode | median | p95 |
|---|---:|---:|
| fts | 1.0 ms | 1.6 ms |
| fts+词表 | 1.7 ms | 3.0 ms |
| bge+词表 | 461 ms | 624 ms |
| **bge+auto** | **667 ms** | 1.90 s |
| bge+LLM（全量） | 1647 ms | 2.04 s |

`auto` 只对 OOV 查询付 LLM 成本。

---

## 5. 关键决策

| # | 决策 | 理由 |
|---|---|---|
| 1 | 去掉自动前缀题 | 34 条 zh-lexical 是送分题，掩盖真实语义能力 |
| 2 | OOV 才调 LLM | 词表覆盖时 LLM 只增加噪声/延迟 |
| 3 | 中国史问题不调 LLM | 目标语料是中文，LLM 的希腊/拉丁/英文关键词无用 |
| 4 | LLM 权重 1.0（低于词表 1.5） | 避免 LLM 变体抢走 top-1 |
| 5 | 默认 `auto` | 无 key 退化词表；有 key 只对 OOV 付费；实测最优 |

---

## 6. 文件

| 文件 | 变化 |
|---|---|
| `eval/public/queries-human.jsonl` | 新主集（130 人工题） |
| `eval/public/queries-unknown.jsonl` | 未知子集（8） |
| `eval/public/RESULTS-human.md` | 本轮结果 |
| `sidecar/app/translate.py` | `oov_terms`、`needs_llm`、`ZH_HISTORY_MARKERS` |
| `sidecar/app/config.py` | 默认 `auto`；`SOCRATIC_TRANSLATE_LLM_WEIGHT=1.0` |
| `sidecar/app/search.py` | LLM 变体权重、auto 分支 |
| `sidecar/tests/test_translate.py` | OOV/领域闸门测试 |
| `scripts/eval_public.py` | 默认主集 human；新增 `fts+auto`/`bge+auto` 模式 |

---

## 7. 复现

```powershell
cd D:\Guo-Code\socratic-tutor
$env:HF_HOME="D:\Guo-Code\socratic-tutor\data\hf-cache"

python scripts/eval_public.py --db data/public.db `
  --set eval/public/queries-human.jsonl `
  --modes fts,fts+tr,bge,bge+tr,bge+auto --k 5 --show-misses

python scripts/eval_public.py --db data/public.db `
  --set eval/public/queries-unknown.jsonl `
  --modes fts,bge,bge+tr,bge+auto,bge+llm --k 5 --json
```

---

## 8. 边界

1. 130 条人工题由一人撰写，存在作者偏差；仍不是 100 人级评测。
2. 中国史闸门是静态约 50 词，新书/新人物需要补。
3. LLM 非确定：未知子集单独跑与全量跑 R@1 有 0.75 vs 0.875 差异。
4. gold 仍是 section/行级，不是答案级；同一段跨 chunk 时偏粗。
5. 53 条中文语义题里仍有不少是“某节内容”型问题，不是真实学生提问。
6. `queries-130.jsonl`（自动前缀）与 `queries-human.jsonl` 口径不同，不要混用。

---

## 9. 下一步

1. **真实学生问句**：从对话/教材习题里收集 50 条，替代“某节内容”型问题。
2. **OOV 闸门评估**：当前未知子集只有 8 条；扩到 30 条再定阈值。
3. **答案级评估**：判引文是否支持回答，而不仅是 section 命中。
4. **领域闸门自动化**：从库内 section 标题自动生成中国史词表，而不是手写。
5. **LLM 缓存/预算**：按 query 缓存 + 每日调用上限，避免成本失控。
