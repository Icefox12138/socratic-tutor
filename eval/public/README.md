# 公开语料评估集

| 文件 | 内容 |
|---|---|
| `queries-human.jsonl` | **当前主集**：130 条人工题（10 词面 + 53 中文语义 + 跨语言 + 8 未知） |
| `queries-unknown.jsonl` | 未知词表子集（8 条），用于测 OOV 闸门/LLM |
| `queries-lexical.jsonl` | 12 条变格查询，grep vs lemma（见 `docs/LEXICAL-SEARCH.md`） |
| `queries-130.jsonl` | 历史 130 问集（含 34 条自动前缀题） |
| `queries.jsonl` | 历史 43 问集（4 书/87 chunks） |
| `RESULTS-human.md` | **当前结果**：人工题 + `bge+auto`，R@5 0.977 |
| `RESULTS-project.md` | **项目综合评估**：v1 历史 + v2 融合 + 能力盘点 |
| `RESULTS-lexical.md` | 词法通道结果（也可看 `docs/LEXICAL-SEARCH.md`） |
| `RESULTS-130.md` | 历史结果：130 问（自动前缀版），R@5 0.938 |
| `RESULTS.md` | 历史结果：43 问，R@5 0.977（小集偏乐观） |

## 格式

```json
{"id": "zh-gr-01",
 "subset": "zh-to-greek",
 "query": "阿喀琉斯的愤怒",
 "gold": [{"document_id": "urn:cts:greekLit:tlg0012.tlg001.perseus-grc1",
           "section": "1.1"}],
 "note": "optional"}
```

- 一条查询可有多个可接受 gold（同义段落/相邻行）。
- 命中定义：top-k 中任一结果与任一 gold 的 `document_id` + `section` 完全一致。
- 子集：`zh-lexical`、`zh-semantic`、`zh-to-greek`、`zh-to-latin`、
  `el-lexical`、`la-lexical`、`en-lexical`、`zh-unknown`。
- 当前主集 `queries-human.jsonl` 不含自动生成的前缀题；`queries-130.jsonl`
  保留为历史对照。

## 语料前提

`data/public.db` 需包含（331 chunks）：

- `wikisource:zh:史記/卷001` … `卷005`（五帝/夏/殷/周/秦本紀）
- `urn:cts:greekLit:tlg0012.tlg001.perseus-grc1`（Iliad 1.1–1.40）
- `urn:cts:latinLit:phi0690.phi003.perseus-lat1`（Aeneid 1.1–1.40）

重建命令见 `docs/RAG-DB-SCHEMA-V2.md` §10；加向量见 §8b。
CTS 旧端点会拒绝少数行号，入库时用 `--skip-errors`。

## 运行

```powershell
# 主集（人工题，含 OOV 闸门）
python scripts/eval_public.py --db data/public.db `
  --set eval/public/queries-human.jsonl `
  --modes fts,fts+tr,bge,bge+tr,bge+auto --k 5 --show-misses

# 未知子集（含 LLM）
python scripts/eval_public.py --db data/public.db `
  --set eval/public/queries-unknown.jsonl `
  --modes fts,bge,bge+tr,bge+auto,bge+llm --k 5 --json

# 词法通道（grep vs lemma）
python scripts/eval_lexical.py --db data/public.db
```

`--json` 输出完整 report 与逐条细节。
