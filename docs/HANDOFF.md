# 交接报告（新对话入口）

| 项 | 值 |
|---|---|
| 日期 | **2026-11-06** |
| 提交 | `222ce39` 之后（39 commits / 17 tags） |
| 项目 | `D:\Guo-Code\socratic-tutor` |
| 范围 | 只含**教学运行时**：sidecar + DSH 插件 + MCP + 章回索引器 |
| 不含 | OCR / 解析 / 切块 / 向量化 / 库构建 → 私有工程 `D:\Guo-Code\rag-build` |
| 判定 | **收窄 GO**（检索门未过，人工验证 0） |
| 测试 | sidecar **264** / classics-index **18** / socratic-mcp **6** / plugin **8** |
| 发布 | PyPI `classics-index` 0.1.3、`socratic-mcp` 0.2.0；npm `dsh-socratic` 0.3.1；sidecar 0.2.1（仅源码） |

---

## 0. 一句话

**引用优先的苏格拉底式教学层已经跑通**：检索（v1 私有 PDF / v2 公开语料 / 联邦）、引用回页、状态机、critic、复盘、学习者模型、计算后端、内嵌 UI 都有测试覆盖；**数据由使用者自建**，本仓只读库教学。

## 1. 不可违反的约束

- 单学生、单机；不接出版社 API/Key；只用自扫/公版 PDF。
- 五语种：现代汉语、文言繁体、英语、拉丁、古希腊。
- 来源可信分级；"以知乎回答为下限"；书级引用 + 页锚。
- 分级揭示 + "停止学习并回顾"；`answer_key` **物理隔离**（SQL/向量层过滤）。
- 目标机 6800HS / 16 GB / 无独显；开发机 4060 8 GB；云只做 burst。
- 现代 Teubner / 后 1929 Loeb 只进 `personal`，不导出。
- **私有库文本、向量、页图永不进入公开仓库**；公开仓只放代码与契约。

## 2. 当前能力

| 模块 | 状态 | 说明 |
|---|---|---|
| 检索 v1（私有 PDF） | 完成 | FTS5（中文二元组）+ BGE-M3 + reranker；100 问 recall 0.80–0.82 |
| 检索 v2（公开语料） | 完成（首版） | schema v2 + Wikisource/CTS adapter；130 题 R@5 0.977 / R@1 0.862 |
| 词法通道 | 完成 | `/v1/grep`、`/v1/lemma`；已作 RRF 融合；变格 R@5 0.917–1.000 |
| 联邦检索 | 完成（首版） | `scope=all` 合并、`scope=routed` 路由 |
| 页图 | 完成（可选） | pypdfium2 按需渲染；`SOCRATIC_RENDER=off` 退化纯文本 |
| 引用核验 | 完成 | 页图 `/v1/pages` 或页内文本 `/v1/verify` |
| 章回 | 完成 | `classics-index` 出 卷/篇/回；`toc` 可存 state.db 或 RAG 库 |
| 教学状态机 | 完成 | init/step/events/replay；ALIGN→…→SUMMARY |
| 判定 / critic | 完成 | 单问、引用、leak 硬拦截；`/v1/critic*` |
| 学习者模型 | 完成 | BKT + FSRS（缺 `fsrs` 时跳过） |
| 复盘 | 完成 | 判定 100%、错误分类 **86.7%**、undetermined 0% |
| 计算后端 | 完成（首版） | SymPy/SciPy/pint/control；audit-only 沙箱；Wolfram/Lean 未装 |
| 内嵌 UI | 完成 | `/ui`、引用卡、提示级别、页图 |
| 打包 | 完成 | `Dockerfile` + `docker-compose.yml`（Linux 镜像未实跑） |
| PTC | 条件通过 | 原生 `run_code` 可用；token −2.2%，**不默认** |

## 3. 架构与不变量

```
L3 DSH Host 插件（dsh-socratic，12 工具）
   状态机 / 提示 / critic / pre-step / llm-stream 硬拦截
        │ HTTP（docs/SIDECAR-CONTRACT.md，36 个端点）
L2 FastAPI sidecar 0.2.1（:8765）
   检索 v1/v2 · 词法 · 联邦 · 引用 · 页图 · 计算 · 状态机
        │
L1 数据：search.db（chunks + chunks_fts）· bge-*.npy · state.db
```

- **答案隔离**：`visibility=answer_key` 在 SQL 与向量层过滤，不靠提示词。
- **状态真源**：sidecar `state.db`（会话/引用/复盘/章回）；每轮显式摘要。
- **引用**：`locator` 必存在且可核验；页图是"渲染可用时的增强"。
- **教学**：确定性状态机；LLM 只做措辞与判定解释。
- **硬拦截**：`llm/stream` 顺序 引用→leak→单问。

## 4. 关键数字

| 项 | 值 |
|---|---:|
| 私有库 chunks（tutor / answer_key） | 167,192（148,261 / 18,931） |
| 向量 | 148,261 × 1024 fp16，与 ids 对齐 |
| v1 召回（100 问） | **0.80–0.82**（门槛 0.85） |
| 跨语言 | **0.667**（门槛 0.70） |
| v2 R@5 / R@1（130 人工题） | **0.977 / 0.862** |
| 引用泄漏 | L4 0 / 266 |
| 复盘错误分类 | 86.7% |
| 页图 | ~0.2 s/页（150 dpi） |

## 5. 已验证 / 未验证

**已验证**：`answer_key` 过滤；引用可回页；S 级页图；strict LLM 未引用 0/50；状态机回放；硬拦截；安全 7/7；v2 adapter（Wikisource/CTS）；词法融合；联邦 `scope=all` 冒烟；264 条单测。

**未验证**：人工评分（0）；v1 检索门（0.80–0.82 < 0.85）；跨语言（0.667 < 0.70）；v2 评估是小集（130 题 / 7 书 / 331 chunks）；希腊专项未稳定提升（0.417–0.583）；Wolfram/Lean 未接入；Docker 镜像未实跑；macOS 未实测。

## 6. 关键决策

| 决策 | 内容 |
|---|---|
| 数据与运行时分离 | 2026-11-04 拆分；本仓不再含 OCR/切块/向量化（见 `SPLIT-PLAN.md`） |
| 数据契约 | 私有 PDF 用 `RAG-DB-SCHEMA.md`（v1）；公开语料用 `RAG-DB-SCHEMA-V2.md` |
| 不换 hybrid | grep 0.59 vs hybrid 0.82（100 问）；词法只做补充通道与引用闸门 |
| clean text 的收益 | 在**引用**不在召回：CER 12% 召回 −6 点，20 字引文存活降到 11% |
| ctext 放弃 | 订阅/机构增值入口，禁止抓取 |
| 计算 | SymPy 默认；Wolfram 可选；MATLAB 放弃；Lean 只做工具 |
| PTC | 原生 `run_code` 可用但不省 token，不作默认 |

## 7. 文档地图

| 文件 | 用途 |
|---|---|
| `STATUS.md` | **当前快照，先读** |
| `HANDOFF.md` | 本文件 |
| `HANDOFF-2026-11-05-rag-strategy.md` | 检索路线、公开语料、schema 演进、计算后端 |
| `HANDOFF-2026-11-05-public-corpora.md` / `-v2-vectors.md` / `-translation-eval.md` | 公开语料、v2 向量、翻译评估 |
| `HANDOFF-2026-11-06-lexical.md` / `-v1-federated.md` / `-compute.md` / `-eval-130.md` / `-human-oov.md` | 词法、联邦、计算、130 题评估、OOV |
| `RAG-DB-SCHEMA.md` / `RAG-DB-SCHEMA-V2.md` | 数据契约（v1 / v2） |
| `SIDECAR-CONTRACT.md` | 插件 ↔ sidecar 接口 |
| `USER-GUIDE.md` | 安装与使用 |
| `PORTABILITY.md` | 跨平台 + **DSH 权限档矩阵** |
| `FEDERATED-SEARCH.md` / `LEXICAL-SEARCH.md` | 两套检索扩展的设计 |
| `SPLIT-PLAN.md` / `RELEASE-PLAN.md` / `RELEASE-2026-11-06.md` | 拆分与发布 |

## 8. 代码与数据

```
D:\Guo-Code\socratic-tutor\      ← 本仓（公开，MIT）
  sidecar\         FastAPI + 检索/引用/状态/计算（32 个测试文件）
  plugin-socratic\ DSH 插件（12 工具 + client.js + ptc.js）
  packages\        classics-index 0.1.3、socratic-mcp 0.2.0
  samples\         5 页合成语料（夹具）+ generators
  docs\            见 §7
  eval\public\     评测查询与结果（12 个跟踪文件）
  .venv-bge\       sidecar 运行所需（唯一留在本仓的 venv）

D:\Guo-Code\library\             馆藏（28.9 GB，只读）
D:\Guo-Code\rag-build\           数据工程（私有，无 git）
  data\            search.db + vectors + experiments
  eval\            管线脚本与实验结果
  docs\            18 份 OCR/数据类文档
  cache\paddlex\   PaddleOCR 模型
  .venv-ocr\       OCR 环境（uv 建，无 pip）
  HANDOFF.md       该工程唯一记忆
```

## 9. 常用命令

```powershell
cd D:\Guo-Code\socratic-tutor

# sidecar（默认读 <repo>/data；指向私有库时用 SOCRATIC_DATA）
cd sidecar
$env:SOCRATIC_DATA='D:\Guo-Code\rag-build\data'
..\.venv-bge\Scripts\python.exe -m uvicorn app.main:app --port 8765 --timeout-keep-alive 75

# 测试（沙箱内也可全跑）
..\.venv-bge\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"

# 数据自检 / 契约自检
..\.venv-bge\Scripts\python.exe scripts\ragdb_check.py
..\.venv-bge\Scripts\python.exe scripts\contract_check.py --query 极限

# 插件测试（沙箱内必须关闭进程隔离）
cd ..\plugin-socratic
node --test --test-isolation=none test\plugin.test.mjs
```

OCR 相关命令在 `rag-build\HANDOFF.md`，环境是 `rag-build\.venv-ocr`。

## 10. 坑（别重踩）

1. **插件必须 `inject`**；用 `link:`；`post-execute` 签名 `(exec, result)`。
2. `run_code` 是 PTC 保留名，注册会报错；`@deepseek-ai/dsh-ptc-runtime` 没有 `dsh.bundle`。
3. **PaddleOCR 3.7 默认 oneDNN 会崩**（`ConvertPirAttribute2RuntimeAttribute`），必须 `enable_mkldnn=False`。
4. **DSH 沙箱 `tempfile.mkdtemp()` 不可写**（owner-only DACL，也删不掉）：测试用 `sidecar/tests/_tmp.py`。
5. **沙箱内 `node --test` 默认 `spawn EPERM`**：加 `--test-isolation=none`。
6. **沙箱内 `git push` 报 schannel 0x8009030e**：加 `-c http.sslBackend=openssl`。
7. **工作区外只读不写**：`rag-build` 可读，写入需完全权限。
8. ODL 需要 Java 17（Java 8 报 class version 55）。
9. BGE/reranker 与 OCR 抢 8 GB 显存；跑 OCR 前先卸 BGE。
10. 不要用 silver 文本层当最终金标（K6 已换 Perseus）。

## 11. 新会话建议

1. 读 `STATUS.md` → 本文件 → `HANDOFF-2026-11-05-rag-strategy.md`；
2. 先问 scope：只做私有 PDF，还是继续扩公开语料；
3. 不要重跑 OCR/P1 全量；不要把私有库文本/向量带进公开仓；
4. 不要声称人工评分；v1 检索门与跨语言门仍未过；
5. 改测试时保持 `_tmp.py`；改文档时同步 `STATUS.md` 与 `PORTABILITY.md`。
