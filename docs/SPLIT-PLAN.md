# 拆分计划：教学运行时 / 数据工程

| 项 | 值 |
|---|---|
| 日期 | **2026-11-04** |
| 决定 | OCR-向量化-RAG 数据库的构建从本仓库**迁出**，成为私有工程；本仓库只负责"读库教学" |
| 新工程 | 私有，**不建 git**，目录暂定 `D:\Guo-Code\rag-build` |
| 影响面 | 三个发布物**不改代码**，只改文案；GitHub 仓库体积降到约 1/3 |

---

## 1. 边界

```
【私有工程 rag-build】            【socratic-tutor（公开）】
书库 + OCR + 切块 + 向量            读 search.db + 向量 → 教学/引用/页图
      │                                   ▲
      └──── RAG-DB-SCHEMA.md（契约）──────┘
```

契约见 [RAG-DB-SCHEMA.md](RAG-DB-SCHEMA.md)。**它先于一切搬迁动作存在**，否则用户自建的库 sidecar 认不出来。

## 2. 代码与数据

| 现在的位置 | 归属 | 处理 |
|---|---|---|
| `eval/`（216 个文件） | 造数据 | **迁出**（含 ingest、bge、bakeoff、p0、p3 脚本与结果） |
| `data/`（indexes/vectors/experiments/paddlex） | 造数据产物 | 迁出；本仓库只留空目录约定 |
| `sidecar/`（47） | 运行时 | 留下 |
| `plugin-socratic/`（13） | 运行时 | 留下 |
| `packages/classics-index`（24，含共 16 测试） | 索引器 | **留下并继续发布**——新工程反过来依赖它 |
| `packages/socratic-mcp` | 运行时 | 留下 |
| `samples/`（合成 5 页 + 索引生成脚本） | **测试夹具** | **留下**，否则 CI 与 `contract_check` 无数据可跑 |
| `scripts/contract_check.py` | 运行时验收 | 留下 |
| `scripts/publish_lint.py` | 发布门禁 | 留下 |

## 3. docs 拆分（46 个 md）

### 3.1 对外保留：插件的构思与实施（16）

| 文件 | 归属理由 |
|---|---|
| `DESIGN.md` / `DESIGN-full.md` | 教学 Agent 的架构与设计基线 |
| `SIDECAR-CONTRACT.md` | 插件 ↔ sidecar 的接口 |
| `RAG-DB-SCHEMA.md` | 插件 ↔ 数据的接口（新） |
| `P2-1`…`P2-7-report.md`、`P2-5-embedded-ui.md` | 状态机/判定器/学习者模型/UI/对话评估/持久化——**全是运行时功能** |
| `P2-8-PTC.md`、`P2-9-PTC-token.md` | 插件工具形态与 token 成本 |
| `P3-1-review.md`、`P3-6-chapter-retrieval.md` | 复盘与章回检索的**运行时**部分 |
| `PLUGIN-MARKET.md` | 上架方式 |

### 3.2 迁出：OCR 选型与数据库测试（17）

| 文件 | 迁出理由 |
|---|---|
| `P1-3c-K5-pageimage.md`、`P1-3c-formula-ocr.md`、`P1-3c-local-report.md` | OCR 引擎横向评测 |
| `P1-3d-ODL.md`、`P1-3d-TEDS.md` | 解析器/表格评测 |
| `P3-2`…`P3-5`（竖排索引、篇切分、带宽扫描、回目索引） | 索引**构建**方法 |
| `P0-PLAN.md`、`P0-SECURITY.md` | 可行性实验与安全测压 |
| `DATA-SOURCE.md`、`LIBRARY-DATA.md` | 数据形态与目录约定（迁出后由新工程维护，本仓只留 schema 契约） |
| `HARDWARE-CLOUD.md` | 批量 OCR 的算力选型 |
| `C-DRIVE-MIGRATION.md`、`CLEANUP.md` | 本机磁盘/环境整理记录 |
| `GAPS.md`、`REMAINING.md` | 缺口盘点里大半是数据工程项，整体迁出更清楚 |

### 3.3 留但要改写（5）

| 文件 | 改写方向 |
|---|---|
| `README.md`（docs 索引） | 删除迁出条目，补 schema 契约与"自建数据库"入口 |
| `STATUS.md` | 去掉数据管线状态，改为"运行时 + 三个发布物" |
| `HANDOFF.md` | 交接内容改为纯运行时（`NEW-PTC-SESSION.md` 已删除，并入 `HANDOFF.md` §11） |
| `RELEASE-PLAN.md` / `RELEASE.md` | 增加"使用者需自建 RAG 数据库"的前置条件 |

### 3.4 纯仓库治理，留在本仓（5）

`ASSETS-POLICY.md`、`OPEN-SOURCE.md`、`REPOSITORY-TOPOLOGY.md`、`architecture-analysis.md`、`REVISION.md`

## 4. 代码改动（拆分前必须完成）

| # | 改动 | 理由 | 验收 |
|---|---|---|---|
| 1 | `/health` 在库不可用时返回 **200 + `{"ok":false,"reason":"no_index"}`** | ✅ 已完成 | 无库时 contract_check 打 SKIP 而非 FAIL |
| 2 | `toc` 读取来源可配置（`state.db` 或 `search.db`） | ✅ 已完成（`SOCRATIC_TOC_IN` / `SOCRATIC_TOC_DB`） | 两种来源都能出 `/v1/toc` |
| 3 | `config.DATA` 不再回退到 `eval/` | ✅ 已完成 | 无 `data/` 时服务能起，且不会误读旧管线 |
| 4 | README/三个包的说明加前置条件 | 对外承诺变准 | 三处文案一致 |

## 5. 新工程形态（私有、无 git）

```
D:\Guo-Code\rag-build\
├── ingest/        OCR → 文本（MinerU / PaddleOCR，选型自由）
├── chunk/         切块 + 中文二元组分词 + FTS5
├── embed/         BGE-M3 向量
├── build.py       一键：书库 → search.db + vectors（幂等、可断点）
├── check.py       按 RAG-DB-SCHEMA §7 自检
└── docs/          从本仓迁来的 OCR/数据类 md
```

不建 git 意味着：**没有版本历史、没有回滚**。建议至少保留 `BUILD-<日期>.md` 记录每次全量构建的参数与耗时。

## 6. 执行顺序

1. 写 `RAG-DB-SCHEMA.md`（✅ 2026-11-04）；
2. 改代码 1–3（health 降级、toc 来源、DATA 默认）（✅ 同日）；
3. 加观测：`/health` 回显四个路径、`scripts/ragdb_check.py`（✅ 同日）；
4. **搬文件（✅ 2026-11-04）**：
   - `data/{indexes,vectors,experiments}` → `D:\Guo-Code\rag-build\data\`
   - `data/paddlex` → `rag-build\cache\paddlex`（OCR 模型缓存）
   - `eval/`（717 文件 / 92 MB）→ `rag-build\eval\`；历史导出为 `rag-build\eval-history.bundle`（0.8 MB）
   - 18 份文档 → `rag-build\docs\`
   - 夹具生成器留在本仓：`samples/generators/{make_demo_corpus,make_sample_pages}.py`、`scripts/{make_demo_card,make_market_icon}.py`；
5. 发 `classics-index 0.1.3` / `socratic-mcp 0.1.2` / `dsh-socratic 0.2.3`（仅文案）；
6. 验收三步：
   ```powershell
   python scripts/ragdb_check.py                    # 配置指向哪个库、chunks/向量/章回是否对齐
   SOCRATIC_DATA=... python scripts/contract_check.py --query <库中必有的词>
   # 对比搬运前后的 chunks 数与首条 citation，应当完全一致
   ```

## 7. 对发布物的影响

| 发布物 | 代码 | 说明 | 版本 |
|---|---|---|---|
| `classics-index` | 不改 | README 补一句"可作为 rag-build 的依赖" | 0.1.3 |
| `socratic-mcp` | 不改 | README 补"需符合 schema 的数据库" | 0.1.2 |
| `dsh-socratic` | 不改 | README 同上 | 0.2.3 |

**不涉及 API 变化，不需要 major 版本。**

## 8. 风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 契约写得不够严，用户建的库跑不通 | 上手失败 | §7 自检清单 + `contract_check` |
| 拆分后仓库没有真实数据，demo 只能跑 5 页 | 观感差 | `samples/` 保留并写进 README 首屏 |
| 配置指向错目录却不报错 | 以为在查新库、实际查旧库 | `/health` 回显 data/db/vectors/toc 四个路径；`ragdb_check.py` 独立复核 |
| 新工程无 git，改坏无法回滚 | 数据重建成本高 | 每次构建留 `BUILD-*.md`；原始 PDF 不动 |
| `toc` 留在 state.db 造成"数据丢失"错觉 | 用户困惑 | 改代码 2，或文档明确说明 |
| 拆分后 `classics-index` 使用者与主仓脱节 | 版本漂移 | 它已是独立包，CI 独立，风险可控 |
