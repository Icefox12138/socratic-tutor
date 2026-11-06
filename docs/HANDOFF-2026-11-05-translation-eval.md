# v2 查询翻译 + 公开语料评估交接

| 项 | 值 |
|---|---|
| 日期 | **2026-11-05** |
| 项目 | `D:\Guo-Code\socratic-tutor` |
| 范围 | 中文问题→希腊/拉丁/英文检索词；43 问公开语料评估集 |
| 状态 | **首版完成并实测**；未提交 git |
| 测试 | sidecar **219/219**（上一轮 205 + 新 14） |
| 评估库 | 4 文档 / **87 chunks**：史記/卷001、史記/卷002、Iliad 1.1–1.10、Aeneid 1.1–1.16/20 |
| 结果 | FTS R@5 **0.535** → 词表翻译 **0.977**；BGE+翻译 **0.977** |

> **后续**：语料扩到 7 书/331 chunks、评估扩到 130 问后，bge+词表 R@5 为
> **0.938**，小集 0.977 偏乐观；未知词表子集见
> [HANDOFF-2026-11-06-eval-130.md](HANDOFF-2026-11-06-eval-130.md)。

---

## 0. 一句话

中文问题现在先扩成希腊/拉丁/英检索变体再检索：默认离线词表（确定性、~2 ms），
可选 LLM；原查询走 BGE，翻译变体走 FTS。43 问评估上 R@5 从 0.535 提到 0.977。

---

## 1. 交付物

| 文件 | 作用 |
|---|---|
| `sidecar/app/translate.py` | 词表/LLM 翻译、缓存、语料语言过滤 |
| `sidecar/app/glossary.json` | 64 条术语（希腊/拉丁词形、简繁别名） |
| `sidecar/app/search.py` | 多变体检索、RRF（权重）、`translated`/`translations` |
| `sidecar/app/config.py` | `SOCRATIC_TRANSLATE*`、`SOCRATIC_LLM_*` |
| `scripts/eval_public.py` | 多模式评估（fts/fts+tr/bge/bge+tr/fts+llm/bge+llm） |
| `eval/public/queries.jsonl` | 43 条 gold（`document_id` + `section`） |
| `eval/public/RESULTS.md` | 结果、分语言表、延迟、结论 |
| `sidecar/tests/test_translate.py` | 词表/LLM/边界 |
| `sidecar/tests/test_v2_translation.py` | 端到端翻译检索 |

### 配置

```powershell
$env:SOCRATIC_TRANSLATE = "glossary"   # glossary(默认) | auto | llm | off
$env:SOCRATIC_TRANSLATE_WEIGHT = "1.5" # 希/拉/英变体权重；中文别名固定 0.8
$env:SOCRATIC_TRANSLATE_BGE = "0"      # 1 = 翻译变体也走 BGE（默认只走 FTS）
$env:SOCRATIC_LLM_BASE = "https://api.deepseek.com"
$env:SOCRATIC_LLM_MODEL = "deepseek-chat"
$env:SOCRATIC_LLM_KEY = "..."          # 或 DEEPSEEK_API_KEY / 本地 key 文件
$env:SOCRATIC_TRANSLATE_TIMEOUT = "6"
```

响应新增：

```json
{"translated": true,
 "translations": [{"lang": "greek", "text": "Ἀχιλλεύς μῆνιν", "source": "glossary"}]}
```

翻译只用于检索，不进入答案、不作为引用证据。

---

## 2. 机制

1. `translate.expand(query, targets)`：
   - 目标语言 = 库里实际存在的 `documents.lang`（没有英文语料就不生成 en 变体）；
   - 词表：最长/全部命中，按 target 拼成词串；ASCII 词用词边界匹配（`war` 不匹配 `warm`）；
   - LLM：DeepSeek/OpenAI 兼容 `/chat/completions`，返回 JSON 数组；失败静默回退。
2. 检索：
   - 原查询：BGE+rerank（有向量）或 FTS；
   - 翻译变体：默认 FTS（关键词足够；BGE 会把 `Iliad 1.6` 这类短句排前）；
   - 多列表按 RRF 融合：原查询权重 1.0，中文别名 0.8，希/拉/英 1.5。
3. 过滤/隔离：变体同样走 `view=student` 的 stream 过滤；`answer_key` 永不出现。

---

## 3. 评估结果（43 问，k=5）

| mode | R@1 | R@3 | R@5 | MRR@5 |
|---|---:|---:|---:|---:|
| fts | 0.512 | 0.535 | 0.535 | 0.523 |
| **fts+tr** | **0.907** | 0.977 | **0.977** | **0.942** |
| bge | 0.651 | 0.698 | 0.721 | 0.679 |
| **bge+tr** | **0.907** | 0.953 | **0.977** | 0.936 |
| fts+llm | 0.884 | 0.977 | 0.977 | 0.930 |
| bge+llm | 0.884 | 0.953 | 0.977 | 0.924 |

分语言 R@5：

| subset | n | fts | fts+tr | bge | bge+tr |
|---|---:|---:|---:|---:|---:|
| zh-lexical | 11 | 1.000 | 1.000 | 1.000 | 1.000 |
| zh-semantic | 5 | 0.600 | 1.000 | 1.000 | 1.000 |
| zh-to-greek | 7 | 0.000 | 1.000 | 0.714 | 1.000 |
| zh-to-latin | 6 | 0.000 | 1.000 | 0.000 | 1.000 |
| el-lexical | 4 | 1.000 | 1.000 | 1.000 | 1.000 |
| la-lexical | 5 | 1.000 | 1.000 | 1.000 | 1.000 |
| en-lexical | 5 | 0.000 | 0.800 | 0.200 | 0.800 |

延迟中位数：fts 0.8 ms；fts+tr 2.2 ms；bge 522 ms；bge+tr 515 ms；
fts+llm 994 ms；bge+llm 1453 ms。

唯一剩余失败：`en-03 "Aeneas"`。Aeneid 1.1–1.16/20 没有出现 `Aeneas` 这个名字，
gold 指向 1.1；属于语料边界，不是排序错误。

---

## 4. 决策

| # | 决策 | 理由 |
|---|---|---|
| 1 | **词表为默认，LLM 可选** | LLM 未超过词表（R@1 0.884 vs 0.907），且慢 ~1 s/查询、非确定 |
| 2 | 翻译变体走 FTS，原查询走 BGE | 变体是关键词；BGE 重排会把短句 `1.6` 排前，R@1 掉到 0.558 |
| 3 | 中文别名变体降权 0.8 | 避免简繁别名压过原查询；zh-semantic 从 0.4 回到 1.0 |
| 4 | 希/拉/英变体加权 1.5 | 原查询是中文、候选是外文，等权会被中文候选稀释 |
| 5 | 目标语言按库内 `documents.lang` 过滤 | 没有英文/拉丁语料时不做无用查询 |
| 6 | 翻译缓存（256，按 query+targets+mode） | 重复问句不重复调用 LLM |
| 7 | 变体顺序固定（zh→greek→latin→en） | 原先 `set` 顺序随哈希变化，RRF 平票会让 top-1 漂移 |
| 8 | RRF 平票按“命中该变体词项数”排序 | Achilles 查询不再在 Iliad 1.1 / Aeneid 1.4 之间跳；R@1 0.884→0.907 |

---

## 5. 边界

1. **评估集小且自建**：4 本书、87 chunks、43 问；查询围绕现有文档构造，0.977 不能
   与 P1 的 100 问/167k chunks 0.82 直接比较。
2. **词表覆盖有限**：64 条术语，主要是荷马/维吉尔/史記五帝夏本纪；开放问题会漏。
3. **LLM 只在有 key 时可用**；`auto` 会引入网络与非确定性，生产默认建议 `glossary`。
4. **gold 是 section 级**：同一段落在多个 chunk 时只算 section 命中；没有做段落级/答案级评估。
5. **中文单字**仍不命中（二元组索引固有）；`q` 建议 ≥2 字。
6. **翻译不是答案**：不要把 `translations` 当引用证据展示给学生。

---

## 6. 复现

```powershell
cd D:\Guo-Code\socratic-tutor
$env:HF_HOME="D:\Guo-Code\socratic-tutor\data\hf-cache"

# 评估（不传 --modes 时只跑 fts/fts+tr/bge/bge+tr）
python scripts/eval_public.py --db data/public.db `
  --modes fts,fts+tr,bge,bge+tr,fts+llm,bge+llm --k 5 --show-misses

# 测试
cd sidecar
$env:PYTHONPATH="D:\Guo-Code\socratic-tutor\sidecar;D:\Guo-Code\socratic-tutor\.tmp-testenv"
..\.venv-bge\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

---

## 7. 下一步

1. **扩评估**：更多书（史記列傳、Aeneid 后续卷、英文公版）、100+ 问；
   加“未知词表”子集，分开测 glossary vs LLM。
2. **扩词表**：按目标书单补术语/词形；或从 `rag-build` 的古典词表导入。
3. **翻译质量**：对 LLM 变体做人工抽检；目前只看检索指标，没看术语准确性。
4. **答案级评估**：现在只评“找到 section”，下一步评“引用句是否支持回答”。
5. **性能**：翻译缓存命中率、LLM 超时/降级、BGE 预热后的首查延迟。
