# v2 公开语料向量/混合检索交接

| 项 | 值 |
|---|---|
| 日期 | **2026-11-05** |
| 项目 | `D:\Guo-Code\socratic-tutor` |
| 范围 | v2 BGE-M3 向量、混合检索、降级、工具与测试 |
| 状态 | **首版完成并实测**；未提交 git |
| 测试 | sidecar **205/205**（上一轮 192 + 新 13） |
| 实测 | 30 chunks（史記/卷001 + Iliad 1.1–1.2）编码 30×1024；首查 7.3 s，热查 0.33–0.39 s |

> **后续**：查询翻译与公开语料评估见
> [HANDOFF-2026-11-05-translation-eval.md](HANDOFF-2026-11-05-translation-eval.md)；
> 本文 §6 的“查询翻译”已落地。

---

## 0. 一句话

v2 现在可以**可选地**建 BGE-M3 向量：有向量时走
`FTS top50 + BGE top50 → RRF → rerank → top N`，没有/加载失败时自动退回
`fts-public`；v1 的向量路径完全没有改动。

---

## 1. 交付物

| 文件 | 作用 |
|---|---|
| `scripts/embed_public.py` | 批量/增量编码；`embeddings` 表；原子写 npy |
| `sidecar/app/search.py` | `v2_bge_status()`、`_load_v2_bge()`、`_v2_bge_search()`、`_v2_rerank()` |
| `sidecar/app/config.py` | `BGE_V2_VECTORS/IDS/MODEL/NAME/EMBED_VERSION` |
| `scripts/ragdb_check.py` | v2 向量行数/维度/对齐、`bge: enabled (v2 hybrid)` |
| `scripts/contract_check.py` | 接受 `mode=bge+rerank-public` |
| `sidecar/tests/test_embed_public.py` | 增量/重建/剪枝/limit/坏文件 |
| `sidecar/tests/test_v2_vectors.py` | 混合排序、过滤、stream/answer_key、降级、health |

### 存储约定

```
<DATA>/vectors/public-vectors.npy   (N, 1024) float16, L2-normalised
<DATA>/vectors/public-ids.npy       (N,) int64 = chunks.id
```

`embeddings(chunk_id, model, dim, version)` 记录编码来源；只编码
`visibility='tutor'` 的 chunk，`answer_key` 永不进入向量。

### 增量语义

- 默认：保留仍存在的 chunk 的旧向量；只编码新 chunk；删除已不存在 chunk 的
  孤儿 id/embeddings 行。
- `--rebuild`：全部重算。
- `--limit N`：只补前 N 个 chunk，**不会**丢弃已有向量。
- `--dry-run`：只报告缺口，不加载模型、不写文件。

---

## 2. 实测

### 2.1 编码

```powershell
python scripts/embed_public.py --db data/public.db --device cuda
# {"chunks":30,"embedded":30,"reused":0,"dim":1024,"model":"bge-m3","device":"cuda"}
```

### 2.2 FTS vs 混合

| 查询 | FTS 结果 | 混合 top-1 |
|---|---:|---|
| `黄帝`（简体） | 0 | `黃帝` 节 |
| `轩辕`（简体） | 0 | `黃帝` 节 |
| `尧舜禅让` | 0 | `帝舜` 节 |
| `Achilles`（英） | 0 | `Iliad 1.1` |
| `阿喀琉斯`（中→希） | 0 | `黃帝`（**未命中** Iliad） |
| `特洛伊战争`（中→希） | 0 | `黃帝`（**未命中**） |

结论：
- 简繁/英文→希腊的**词面**差异由 BGE 补齐；
- 中文→希腊/拉丁的**纯语义**仍弱，BGE 单通道不够，需要查询翻译。

### 2.3 延迟

| 场景 | 延迟 |
|---|---:|
| 首查（含 BGE-M3 + reranker 加载） | 7.33 s |
| 热查（`黄帝的出身`） | 326 ms |
| 热查（`道可道`） | 386 ms |
| 热查（`θεά`） | 375 ms |

### 2.4 契约

v2 sidecar（`SOCRATIC_DB=data/public.db`, `SOCRATIC_BGE=1`）：

```
ok health               schema=v2 chunks=30
ok search               mode=bge+rerank-public
ok citation scheme      scheme=mediawiki
ok citation url         https://zh.wikisource.org/wiki/…
CONTRACT OK
```

`/health`：首查前 `bge:"lazy"`，首查后 `"ready"`；无向量文件时
`bge:"missing: <path>"`，检索自动走 FTS。

---

## 3. 关键决策

| # | 决策 | 理由 |
|---|---|---|
| 1 | v2 向量独立文件 | 不与 v1 的 `bge-vectors.npy` 混用；两库可指向不同模型 |
| 2 | 默认增量编码 | 重灌单本文档不应重算全库 |
| 3 | 向量可选，缺失即降级 | 公开语料先可用，再谈召回 |
| 4 | RRF + rerank 与 v1 同构 | 少一套排序逻辑；行为可对照 |
| 5 | student stream 过滤在 rerank 前 | 避免注释/译本进入学生候选 |
| 6 | `mode=bge+rerank-public` | 客户端能区分 v2 混合与 v1 混合 |
| 7 | 不把 `answer_key` 编码 | 与 v1 一致：向量层也不应出现答案键 |

---

## 4. 边界

1. **中文→希腊/拉丁纯语义仍不达标**：需要 LLM 查询翻译，或人工双语 query 扩展。
2. 没有公开语料的 recall 金标；目前只有少量语义样例，不能宣称“达到 0.82”。
3. 首次查询会加载两个模型（BGE-M3 + reranker），约 7 s；
   `SOCRATIC_PRELOAD=1` 会在启动线程里预热（v2 已接）。
4. 向量文件与 chunk id 强绑定；重新入库会换 id，`embed_public.py` 需重跑
   （默认增量会剪孤儿、补新 id）。
5. **没有热重载**：向量在首次查询/启动预热时载入内存；重新编码后要重启
   sidecar 才会用新文件。
6. GPU 8 GB 下 BGE-M3 + reranker 可共存，但跑 OCR/其它模型前要注意显存。
7. `embeddings.version` 目前是 `fp16-normalized`，不是模型 commit 号。

---

## 5. 复现

```powershell
cd D:\Guo-Code\socratic-tutor
$env:HF_HOME="D:\Guo-Code\socratic-tutor\data\hf-cache"

# 1) 编码（GPU）
python scripts/embed_public.py --db data/public.db --device cuda

# 2) 库自检
$env:SOCRATIC_DB="D:\Guo-Code\socratic-tutor\data\public.db"
python scripts/ragdb_check.py
# vectors: 30x1024 float16 ids=30 aligned=True
# bge: enabled (v2 hybrid)

# 3) 起 sidecar + 契约
cd sidecar
$env:SOCRATIC_DB="D:\Guo-Code\socratic-tutor\data\public.db"
$env:SOCRATIC_BGE="1"
..\.venv-bge\Scripts\python.exe -m uvicorn app.main:app --port 8765
# 另开：python scripts/contract_check.py --query 黃帝

# 4) 测试
$env:PYTHONPATH="D:\Guo-Code\socratic-tutor\sidecar;D:\Guo-Code\socratic-tutor\.tmp-testenv"
..\.venv-bge\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

---

## 6. 下一步

1. **查询翻译通道**：中文问题 → 希腊/拉丁/英文检索词，再合并排序；
   这是 v2 跨语言的关键缺口。
2. **公开语料评估集**：从 P1-6 的 100 问里挑出公开文本可答的子集，
   测 FTS / BGE / +翻译 的 recall，给出可比较数字。
3. **预热**：`SOCRATIC_PRELOAD=1` 已接；下一步是测启动内存与首查延迟。
4. **阈值/分数**：rerank 分数低于阈值时标注“未核验”，不要硬凑引用。
5. **规模化编码**：10 万 chunk 级别的 batch/显存策略；目前 30 chunk 只验证链路。
