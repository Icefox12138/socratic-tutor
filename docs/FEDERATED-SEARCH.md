# 统一检索：v1 私有库 + v2 公开语料（2026-11-06）

| 项 | 值 |
|---|---|
| 入口 | `GET /v1/search?...&scope=all` |
| 代码 | `sidecar/app/federated.py` |
| 默认 | `scope=auto`（只查当前库，行为不变） |
| 合并 | 两库各取 `limit`，按 RRF 合并；结果带 `schema` |
| 测试 | sidecar 264/264；`test_federated.py` 6 条（3 合并 + 3 路由） |
| 实测 | 真实 v1 310 MB + v2 331 chunks，`黃帝`/`arma`/`μῆνιν` 均返回两库 |

## 1. 配置

```powershell
$env:SOCRATIC_V1_DB="D:\Guo-Code\rag-build\data\indexes\search.db"
$env:SOCRATIC_V1_BGE_VECTORS="D:\Guo-Code\rag-build\data\vectors\bge-vectors.npy"
$env:SOCRATIC_V1_BGE_IDS="D:\Guo-Code\rag-build\data\vectors\bge-ids.npy"
$env:SOCRATIC_PUBLIC_DB="D:\Guo-Code\socratic-tutor\data\public.db"
```

`SOCRATIC_V1_DB` 不设时默认等于 `SOCRATIC_DB`；v2 部署要显式设，否则会把
同一个库当两库（代码会按路径去重，但标签会错）。

## 2. 请求

```http
GET /v1/search?q=arma&scope=all&limit=8
GET /v1/search?q=黃帝&scope=routed&limit=8
```

`scope=all` 合并两库；`scope=routed` 只查一个库，按语言/覆盖路由（见 §3）。

响应：

```json
{"query": "arma", "schema": "federated", "mode": "federated",
 "schemas": ["v1", "v2"],
 "results": [
   {"schema": "v1", "book": "conte_aeneis", "page": 12, "citation": {"page_image": "..."}},
   {"schema": "v2", "document_id": "urn:cts:latinLit:...", "section": "1.1",
    "citation": {"scheme": "cts", "url": "..."}}
 ],
 "lexical": {"grep": 2, "lemma": 0},
 "errors": [], "took_ms": 95.2}
```

- 每条结果多一个 `schema`，其余字段与单库一致。
- `mode=federated`；`schemas` 列出实际查到的库。
- 某库失败时写 `errors`，另一库仍返回；两库都失败才 503。

## 3. 路由（`scope=routed`）

不做全查，先用**每个库一次 FTS 探针**（limit 3）判断覆盖，再只搜选中的库。

路由表**不再写死在代码里**：M3 起由引用策略的 `routing` 段提供
（`sidecar/app/citation_policy.py`，可用 `SOCRATIC_POLICY` 覆盖，
`GET /v1/policy` 可查生效值）。默认表与旧行为等价：

| 查询信号 | `route_reason` | 优先库 | 理由 |
|---|---|---|---|
| 中国史标记（史記/黃帝/周文王…，`markers.zh-history`） | `classical-zh` | v2 | 干净文本 + revision 引用 |
| 作品名（Iliad/Aeneid/Homer/Virgil **及希腊文写法**，`markers.v2-works`） | `v2-work` | v2 | CTS/MediaWiki 引用 |
| 短希腊文引文（≤80 字，正则规则） | `greek-quote` | v2 | CTS 行级引用 |
| 其他（现代中文/英文/拉丁） | `v1-default` | v1 | 167k 页覆盖更大 |
| 选中库 0 命中 | `+fallback` | 另一库 | 一次 fallback，仍不双查 |

匹配对**变音符号不敏感**（NFD 去组合符、统一 σ/ς），所以 `Ἰλιάς` 与
`Iliad` 命中同一条规则——旧的关键词表只收了拉丁转写，希腊文原写作会漏。

响应额外带 `routed_to`、`route_reason`、`route_probe`、`errors`。
实测：

| 查询 | 路由 | 探针 |
|---|---|---|
| `黃帝` | v2 | v1 0 / v2 3 |
| `史記` | v2 | v1 0 / v2 1 |
| `μῆνιν` | v2 | v1 0 / v2 1 |
| `量子力学` | v1 | v1 3 / v2 0 |
| `arma` | v1 | v1 3 / v2 2 |
| `Achilles` | v1 | v1 3 / v2 0 |

## 4. 合并语义

1. 串行执行：v1 搜索（含可选翻译/grep）→ v2 搜索（含翻译/OOV/lemma）。
2. 每库内部已经是 RRF/rerank；跨库再按排名做一次 RRF：
   `score += 1/(60+rank+1)`。
3. 同一个 `chunk_id` 在 v1/v2 中视为不同结果（键是 `schema+chunk_id`）。
4. 不做跨库正文去重；同一段文本若两库都有，会各出现一次。

## 5. 并发与成本

- `federated._LOCK` 串行化配置切换，避免两个请求同时改 `config.DB`。
- BGE 开启时 v1/v2 各一份模型/向量（`_BGE` / `_V2_BGE`），显存约翻倍；
  8 GB 卡建议 v1 用 BGE、v2 用 FTS，或分时。
- 实测（BGE 关）`arma` 约 95 ms；BGE 开需加载两份索引，首查更慢。

## 6. 边界

1. `scope=all` 只合并两库 **各 top-limit**，不是全库重排。
2. `document_id`/`section` 只对 v2 有意义；v1 会忽略/报错并写入 `errors`。
3. `book` 在 v1 是相对路径、v2 是标题/ID，跨库过滤语义不一致。
4. 两库的分数不可比；跨库只用排名 RRF，不用原始分数。
5. 没有自动路由（“该查 v1 还是 v2”）；默认仍是单库。
6. `federated` 是同步串行；高并发下会成为瓶颈。

## 7. 测试

```powershell
cd sidecar
$env:PYTHONPATH="D:\Guo-Code\socratic-tutor\sidecar;D:\Guo-Code\socratic-tutor\.tmp-testenv"
..\.venv-bge\Scripts\python.exe -m unittest tests.test_federated -v
```

覆盖：两库合并、`answer_key` 不出现、HTTP 端点、`routed` 的 v1/v2 决策。
