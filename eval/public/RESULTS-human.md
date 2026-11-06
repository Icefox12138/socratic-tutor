# 公开语料评估：人工题 + OOV 闸门（2026-11-06）

> **后续**：加入 grep/lemma 融合后的最新数字见
> [RESULTS-project.md](RESULTS-project.md)。本文件的 bge+auto 是融合前的一次
> 运行；LLM 非确定，R@1 在 0.838–0.854 之间波动。

| 项 | 值 |
|---|---|
| 库 | `data/public.db`（7 文档 / 331 chunks） |
| 查询 | **130 条人工题**（`queries-human.jsonl`） |
| 组成 | zh-lexical 10、zh-semantic 53、zh-to-greek 12、zh-to-latin 12、el 13、la 12、en 10、zh-unknown 8 |
| 变化 | 去掉 34 条自动前缀题；LLM 只在 OOV 时调用；LLM 变体权重 1.0 |
| 主结果 | **bge+auto：R@1 0.838 / R@5 0.977 / MRR 0.899** |
| 未知子集 | 词表/BGE 0.625 → **auto 1.000**（R@1 0.875） |

## 1. 总体

| mode | n | R@1 | R@3 | R@5 | MRR@5 |
|---|---:|---:|---:|---:|---:|
| fts | 130 | 0.423 | 0.523 | 0.577 | 0.480 |
| fts+词表 | 130 | 0.554 | 0.700 | 0.762 | 0.633 |
| bge | 130 | 0.777 | 0.892 | 0.892 | 0.828 |
| bge+词表 | 130 | 0.815 | 0.938 | 0.938 | 0.872 |
| **bge+auto** | 130 | **0.838** | **0.946** | **0.977** | **0.899** |

`auto` = 词表 + 仅对 OOV 调 LLM；中国史问题被领域闸门挡住，不调 LLM。

## 2. 分语言 / 子集（R@5）

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

## 3. 未知词表子集（8 条，单独跑）

| mode | R@1 | R@3 | R@5 | MRR@5 |
|---|---:|---:|---:|---:|
| fts / fts+词表 | 0.000 | 0.000 | 0.000 | 0.000 |
| bge / bge+词表 | 0.500 | 0.625 | 0.625 | 0.562 |
| **bge+auto** | **0.875** | 0.875 | **1.000** | **0.906** |
| bge+LLM | 0.875 | 0.875 | 1.000 | 0.906 |

（全量 130 里 zh-unknown 的 R@1 是 0.750；LLM 非确定，单独跑是 0.875，报告时取区间。）

## 4. 延迟

| mode | median | p95 |
|---|---:|---:|
| fts | 1.0 ms | 1.6 ms |
| fts+词表 | 1.7 ms | 3.0 ms |
| bge+词表 | 461 ms | 624 ms |
| **bge+auto** | **667 ms** | 1.90 s |
| bge+LLM（全量） | 1647 ms | 2.04 s |

`auto` 只对 OOV 查询付 LLM 成本；全量 `llm` 的 p95 仍在 2 s。

## 5. 机制

1. **OOV 检测**：把词表命中的片段从查询里挖掉，去掉虚词/疑问词；剩余 CJK
   连续 ≥2 字或 ≥3 字母的词视为 OOV。
2. **领域闸门**：查询命中中国史人物/制度词（周文王、秦孝公、商鞅…）时不调 LLM，
   因为目标语料是中文，LLM 只能给希腊/拉丁/英文关键词。
3. **LLM 权重 1.0**：LLM 变体只补召回，不压过原查询；词表变体仍 1.5，
   中文别名 0.8。
4. **提示词**：要求史诗实际词形（-οιο/-ου、-is/-i/-em）与别称
   （Saturnia、ἀργυρότοξος），这是未知子集从 0.75 提到 1.0 的关键。

## 6. 结论

1. 人工题比自动前缀题难：bge+词表从 0.938（130 自动集）降到 0.938，但
   fts 从 0.608 降到 0.577；语义/跨语言占比更高。
2. **bge+auto 是当前最优**：0.977 R@5、0.838 R@1，全面优于或等于 bge+词表。
3. **OOV 闸门成立**：未知子集 0.625 → 1.000，而不用全量 LLM。
4. **领域闸门必要**：没有它，`auto` 会给中国史题调 LLM，zh-semantic R@1
   从 0.849 掉到 0.717。
5. **默认改为 `SOCRATIC_TRANSLATE=auto`**：无 LLM key 时自动退化为纯词表，
   有 key 时只对 OOV 付费。

## 7. 复现

```powershell
cd D:\Guo-Code\socratic-tutor
$env:HF_HOME="D:\Guo-Code\socratic-tutor\data\hf-cache"

# 主集（人工题）
python scripts/eval_public.py --db data/public.db `
  --set eval/public/queries-human.jsonl `
  --modes fts,fts+tr,bge,bge+tr,bge+auto --k 5 --show-misses

# 未知子集
python scripts/eval_public.py --db data/public.db `
  --set eval/public/queries-unknown.jsonl `
  --modes fts,bge,bge+tr,bge+auto,bge+llm --k 5 --json
```

## 8. 边界

1. 130 条仍是小集；53 条中文语义题由一个人撰写，存在作者偏差。
2. 中国史闸门是静态关键词表（约 50 个），新书/新人物需要补。
3. LLM 翻译非确定，未知子集单独跑与全量跑的 R@1 有 0.75/0.875 差异。
4. gold 仍是 section/行级，不是答案级。
5. `queries-130.jsonl`（34 条自动前缀）保留为历史对照；`queries-human.jsonl`
   是当前主集。
