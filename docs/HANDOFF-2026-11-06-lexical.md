# grep/lemma 最小闭环交接（2026-11-06）

| 项 | 值 |
|---|---|
| 日期 | **2026-11-06** |
| 项目 | `D:\Guo-Code\socratic-tutor` |
| 范围 | grep 精确串 + lemma 词形归并；API/插件/MCP/测试/评估 |
| 状态 | **最小闭环 + 融合进 v2 主检索**；未提交 git |
| 测试 | sidecar **240/240**（上一轮 222 + 新 18：13 词法 + 5 融合）；MCP 6/6 |
| inflected 评估 | FTS 0.083 / grep 0.000 / lemma 0.917（无 simplemma）或 **1.000**（simplemma）R@5 |

---

## 0. 一句话

新增 `GET /v1/grep` 与 `GET /v1/lemma`：前者做**精确子串**，后者把希腊/拉丁
变格形式归并（`ira ↔ iram`、`μῆνις ↔ μῆνιν`）。两者都返回与搜索一致的
citation，并且已经作为 **v2 检索的额外 RRF 列表**（grep 2.0 / lemma 1.3）。

---

## 1. 交付物

| 文件 | 作用 |
|---|---|
| `sidecar/app/lexical.py` | `grep()`、`lemma_search()`、词干/lemma、IDF 覆盖率排序 |
| `sidecar/app/main.py` | `/v1/grep`、`/v1/lemma` |
| `plugin-socratic/index.js` | `lexical_search` 工具（grep/lemma） |
| `packages/socratic-mcp/.../tools.py` | `kb_lexical` 工具 |
| `sidecar/tests/test_lexical.py` | v1/v2、过滤、answer_key、端点、变格 |
| `scripts/eval_lexical.py` | FTS/grep/lemma 对照 |
| `eval/public/queries-lexical.jsonl` | 12 条变格查询 |
| `sidecar/pyproject.toml` | 可选依赖 `lemma = ["simplemma>=2.0"]` |

## 2. 接口

```http
GET /v1/grep?q=&view=&limit=&source=&lang=&book=&document_id=&section=
GET /v1/lemma?q=&view=&limit=&source=&lang=&book=&document_id=&section=
```

- `grep`：v1/v2 都可用；`match={start,end,snippet,count}`。
- `lemma`：**仅 v2**；v1 返回 400；`match={coverage,lemmas,exact}`。
- 只返回 `visibility='tutor'`；`view=student` 在 v2 还过滤非 `text` 流。

## 3. 实现

### grep

- Unicode `casefold()` 子串；SQL 先用 `instr()` 收窄。
- v2 小库在 accented 大写查询无 SQL 命中时回退内存扫描。
- 按出现次数、chunk_id 排序；返回原样片段与偏移。

### lemma

- 查询词：中文二元组；希腊/拉丁用 `simplemma`（可选）+ 后缀词干并集。
- 词干：希腊/拉丁常见变格后缀剥离 + 前 4 字符（降级方案）。
- chunk 侧 lemma 集合缓存；按 IDF 加权覆盖率排序，`min_coverage=0.5`。
- `SOCRATIC_LEMMA_SCAN` 默认 50000，超限截断并置 `truncated`。

### 与 verify 的区别

- `grep` 是原样子串检索；`/v1/verify` 会去标点/空白后做引文校验。
- 引用核验仍以 `verify` 为准；grep 用于找候选。

## 4. 评估

`eval/public/queries-lexical.jsonl`：12 条查询，形式故意不是原文子串。

| mode | R@1 | R@3 | R@5 | MRR@5 |
|---|---:|---:|---:|---:|
| FTS | 0.000 | 0.083 | 0.083 | 0.042 |
| grep | 0.000 | 0.000 | 0.000 | 0.000 |
| lemma（降级词干） | 0.583 | 0.917 | 0.917 | 0.750 |
| **lemma / fusion（simplemma 2.0）** | **0.667** | **1.000** | **1.000** | **0.833** |

130 人工题上的融合：bge+auto 0.854/0.969 → bge+auto+lex **0.862/0.977**，
MRR 0.906→0.915；中文词面 R@1 0.9→1.0、中→希腊 R@1 0.583→0.75。

结论：
- 精确 grep 对变格形式必然 0；lemma 是必要的；
- `simplemma` 把 R@5 从 0.917 提到 1.000；
- 中文 lemma 实际接近 FTS 二元组，收益主要在希腊/拉丁。

## 5. 复现

```powershell
cd D:\Guo-Code\socratic-tutor

# 降级词干
python scripts/eval_lexical.py --db data/public.db

# 安装/指向 simplemma 后
$env:PYTHONPATH="D:\Guo-Code\temp\nlp_libs"
python scripts/eval_lexical.py --db data/public.db

# 测试
cd sidecar
$env:PYTHONPATH="D:\Guo-Code\socratic-tutor\sidecar;D:\Guo-Code\socratic-tutor\.tmp-testenv"
..\.venv-bge\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

## 6. 边界

1. **lemma 只支持 v2**；v1 PDF 页需要另建 lemma 索引或只用 grep。
2. 降级词干是启发式，可能误合并共享前 4 字符的词。
3. grep 无正则/邻近/模糊；复杂查询用 FTS/BGE。
4. **已融合**进 v2 主检索（`SOCRATIC_LEXICAL=auto`）；权重是经验值，中文语义题
   仍可能被词法列表抢 top-1。
5. 没有逐条人工检查 lemma 结果；12 条只是变格样例。
6. `simplemma` 不在默认依赖里（`pip install .[lemma]`）；当前 venv 没装，
   评估时通过 `D:\Guo-Code\temp\nlp_libs` 注入。

## 7. 下一步

1. **权重/触发调优**：grep 2.0、lemma 1.3 是经验值；用 dev/holdout 调。
2. **引文闸门**：LLM 给出引文时先 grep/lemma 找候选，再 `verify`。
3. **v1 lemma 索引**：或明确只给 v2 用；不要扫描 167k 页。
4. **扩评估**：30+ 变格/不规则形式，含 simplemma 失败例。
5. **正则/邻近**：只在 grep 上做可选开关，默认关闭。
