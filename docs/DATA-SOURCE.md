# 数据源形态：为什么现在不是向量库，以及怎么改成向量库

| 项 | 值 |
|---|---|
| 日期 | **2026-11-03** |
| 结论 | 现在是「**SQLite 目录 + 303 MB 的 .npy 向量 + 进程内矩阵乘**」，不是向量库接口 |
| 触发改造的条件 | chunks > 50 万、需要增量索引、或多机/多进程共享 |

---

## 1. 现在的数据路径

```
PDF ──ingest──> SQLite(chunks + FTS5) ──embed──> bge-vectors.npy (303 MB) + bge-ids.npy
                                                    │
sidecar 启动 ──load──> torch 矩阵（GPU）────────────┘
查询 ──> FTS top50 ──┐
         BGE top50 ──┴─> RRF 融合 ─> bge-reranker 重排 ─> top N
```

对应代码：

| 环节 | 位置 |
|---|---|
| 切块与 FTS5 索引 | `eval/p1/ingest/build_search.py`（`chunks` 表 + `chunks_fts`） |
| 向量生成 | `eval/p1/bge/embed_bge.py` → `bge-vectors.npy` / `bge-ids.npy` |
| 运行时加载 | `sidecar/app/search.py:_load_bge()`（npy → torch 张量，全量常驻显存/内存） |
| 检索融合 | `_bge_search()`：FTS ∪ BGE → RRF → cross-encoder |

配置项（`sidecar/app/config.py`）：

```
SOCRATIC_DB            search.db 路径
SOCRATIC_BGE_VECTORS   bge-vectors.npy
SOCRATIC_BGE_IDS       bge-ids.npy
SOCRATIC_BGE_MODEL     models/bge-m3
SOCRATIC_RERANK_MODEL  models/bge-reranker-v2-m3
SOCRATIC_BGE=0         强制退回纯 FTS
```

**没有**任何 `QDRANT_URL`、`COLLECTION`、`EMBEDDING_API` 之类的接口配置——换向量库要改代码，不是改配置。

## 2. 为什么当初不选向量库

| 事实 | 影响 |
|---|---|
| 167,192 chunks × 1024 维 fp16 ≈ 340 MB | 一张 8 GB 卡整块常驻没有压力 |
| 单机、单学生、无并发 | 不需要独立服务进程与网络往返 |
| 检索已由 reranker 兜底 | 向量库的 ANN 加速对 16 万条没有意义（暴力矩阵乘 ~几 ms） |
| 冷启动 8.6 s、预热 p95 830 ms | 满足 TTFT 目标 |

向量库真正划算的门槛是：**几十万到上百万 chunk、需要按元数据过滤、需要增量 upsert、或多进程共享索引**。现在一条都不满足。

## 3. 要接口化，改哪里

最小改动是引入一个 `Retriever` 协议（与现有 `_bge_search` 同签名）：

```python
class Retriever(Protocol):
    def search(self, query: str, *, k: int, filters: dict) -> list[Hit]: ...
    def upsert(self, ids: list[str], vectors, payloads: list[dict]) -> None: ...
    def delete(self, ids: list[str]) -> None: ...
    def stats(self) -> dict: ...
```

两个实现：

| 实现 | 依赖 | 何时用 |
|---|---|---|
| `npy`（现状） | numpy + torch | 默认，单机 |
| `qdrant` | `qdrant-client` + 一个容器 | 增量索引、多机、过滤复杂 |

配置：`SOCRATIC_RETRIEVER=npy|qdrant` + `SOCRATIC_QDRANT_URL` / `SOCRATIC_COLLECTION`。

工作量估计：**1–2 天**（抽取协议 + 两个实现 + 现有 12 条检索相关测试 + 一次 A/B 验证 recall 不退化）。

## 4. 与开源组件的关系

见 `docs/RELEASE.md` `1 的对照表：PDF 解析（MinerU / Marker / docling）、向量库（Qdrant / Chroma）、RAG 服务（RAGFlow / Onyx）都有成熟件；**没有现成件的是"页图引用 + answer_key 物理隔离 + 五语种 + 古籍章回索引"这套组合**。

若要接入现成组件，最省力的顺序是：

1. 先接 **Qdrant**（替换 npy，保留自己的 chunk schema 与 reranker）；
2. 再考虑 **RAGFlow 的 DeepDoc** 替换 `ingest_library.py` 的解析段——但它不带"页图可回看"和 `visibility` 隔离，仍要自己加；
3. **不要**让 RAGFlow/Onyx 接管整个 sidecar：它们没有状态机、没有 leak 拦截、没有 `answer_key` 隔离。
