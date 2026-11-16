# 交接报告（新对话入口）

| 项 | 值 |
|---|---|
| 日期 | **2026-11-16** |
| 提交 | `72f9c10`（main，CI 绿） |
| 项目 | `D:\Guo-Code\socratic-tutor` |
| 范围 | **教学运行时**：sidecar + 两个 DSH 插件（工具 / 人格）+ MCP + 章回索引器 + 发布流水线 |
| 不含 | OCR / 解析 / 切块 / 向量化 / 库构建 → 私有工程 `D:\Guo-Code\rag-build` |
| 判定 | **收窄 GO**（检索门未过，人工验证 0） |
| 测试 | sidecar **341** / plugin **6 + 13**（工具 / 人格）/ classics-index **18** / socratic-mcp **6** |
| 发布 | npm `dsh-socratic` **0.5.1**、`dsh-socratic-persona` **0.1.1**（OIDC + SLSA provenance）；PyPI `classics-index` 0.1.3、`socratic-mcp` 0.2.0、`calcbox` 0.3.1；sidecar 0.2.1（仅源码） |

---

## 0. 一句话

**引用优先的苏格拉底式教学层已经跑通**：检索（v1 私有 PDF / v2 公开语料 / 联邦）、引用回页、状态机、critic、复盘、学习者模型、计算后端、内嵌 UI 都有测试覆盖；**数据由使用者自建**，本仓只读库教学。教学行为已从插件里拆成独立 bundle，开发会话不会再被当成学生。

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
| 联邦检索 | 完成（首版） | `scope=all` 合并、`scope=routed` 路由；合并模式 `rrf`（默认）/`weighted`/`tiered` |
| 引用策略 | 完成（M0–M5） | `/v1/policy`、`/v1/channels`、`/v1/policy/reload`；tier/role 查表；`book_meta` → `doc_kind`/`subject` |
| 页图 | 完成（可选） | pypdfium2 按需渲染，**加锁串行**（PDFium 非线程安全）；`SOCRATIC_RENDER=off` 退化纯文本 |
| 引用核验 | 完成 | 页图 `/v1/pages` 或页内文本 `/v1/verify` |
| 章回 | 完成 | `classics-index` 出 卷/篇/回；`toc` 可存 state.db 或 RAG 库 |
| 教学状态机 | 完成 | init/step/events/replay；ALIGN→…→SUMMARY |
| 判定 / critic | 完成 | 单问、引用、leak 硬拦截；`/v1/critic*` |
| 学习者模型 | 完成 | BKT + FSRS（缺 `fsrs` 时跳过） |
| 复盘 | 完成 | 判定 100%、错误分类 **86.7%**、undetermined 0% |
| 计算后端 | 完成 | 实现已迁到独立包 **calcbox 0.3.1**（PyPI, MIT）；`sidecar/app/compute.py` 只是适配层 |
| DSH 插件 | 完成（已拆包） | **`dsh-socratic`**：13 工具 + `client.js` 卡片；**`dsh-socratic-persona`**：章程 + `agent/pre-step` + `llm/stream` |
| 发布流水线 | 完成 | `publish-npm.yml`：打 tag → OIDC 发布两个包（无长期 npm token） |
| 打包 | 完成 | `Dockerfile` + `docker-compose.yml`（Linux 镜像未实跑） |
| PTC | 条件通过 | 原生 `run_code` 可用；token −2.2%，**不默认** |

## 3. 架构与不变量

```
L3 DSH Host 插件
   dsh-socratic           13 工具（kb_*/socratic_*/compute_math/ptc_calc/…）+ client.js 卡片
   dsh-socratic-persona   章程 section + agent/pre-step 摘要 + llm/stream 硬拦截
        │ HTTP（docs/SIDECAR-CONTRACT.md）
L2 FastAPI sidecar 0.2.1（:8765）
   检索 v1/v2 · 词法 · 联邦 · 引用策略 · 页图 · 计算 · 状态机
        │
L1 数据：search.db（chunks + chunks_fts）· bge-*.npy · state.db · （可选）book_meta.json
```

- **答案隔离**：`visibility=answer_key` 在 SQL 与向量层过滤，不靠提示词。
- **状态真源**：sidecar `state.db`（会话/引用/复盘/章回）；每轮显式摘要。
- **引用**：`locator` 必存在且可核验；页图是"渲染可用时的增强"。
- **教学**：确定性状态机；LLM 只做措辞与判定解释。
- **硬拦截**：`llm/stream` 顺序 引用→leak→单问；顺序与阈值都在 persona 包里。
- **两种部署**：只装工具包 = 普通助手 + 13 工具；再装人格包 = 教学模式。人格是 **profile 级**，不能按会话切换。

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
| 测试 | 341 + 19 + 18 + 6 |

## 5. 已验证 / 未验证

**已验证**：`answer_key` 过滤；引用可回页；S 级页图；strict LLM 未引用 0/50；状态机回放；硬拦截；安全 7/7；v2 adapter（Wikisource/CTS）；词法融合；联邦 `scope=all` 冒烟；引用策略 M0–M5（含 book_meta 富化）；DSH **0.2.2-rc.2** 上两个包可安装、可组合、测试全绿；OIDC 发布两次成功（0.5.1 / 0.1.1，带 provenance）；341 条 sidecar 单测。

**未验证**：人工评分（0）；v1 检索门（0.80–0.82 < 0.85）；跨语言（0.667 < 0.70）；v2 评估是小集（130 题 / 7 书 / 331 chunks）；希腊专项未稳定提升（0.417–0.583）；Wolfram/Lean 未接入；Docker 镜像未实跑；macOS 未实测；教学 profile 的端到端 UI 冒烟（插件拆包后尚未在 GUI 里实际走一遍）。

## 6. 关键决策

| 决策 | 内容 |
|---|---|
| 数据与运行时分离 | 2026-11-04 拆分；本仓不再含 OCR/切块/向量化（见 `SPLIT-PLAN.md`） |
| 数据契约 | 私有 PDF 用 `RAG-DB-SCHEMA.md`（v1）；公开语料用 `RAG-DB-SCHEMA-V2.md` |
| 不换 hybrid | grep 0.59 vs hybrid 0.82（100 问）；词法只做补充通道与引用闸门 |
| clean text 的收益 | 在**引用**不在召回：CER 12% 召回 −6 点，20 字引文存活降到 11% |
| ctext 放弃 | 订阅/机构增值入口，禁止抓取 |
| 计算 | SymPy 默认；Wolfram 可选；MATLAB 放弃；Lean 只做工具；实现迁 calcbox |
| PTC | 原生 `run_code` 可用但不省 token，不作默认 |
| **插件拆包** | 人格（章程/摘要/改写）是 profile 级副作用；2026-11-06 拆成独立 bundle，用"装不装"当开关，取代 0.4.x 的 `persona: false` |
| **发布用 OIDC** | npm Trusted Publishing，工作流 `publish-npm.yml`；不再有长期 token 可泄露 |

## 7. 文档地图

| 文件 | 用途 |
|---|---|
| `STATUS.md` | **当前快照，先读** |
| `HANDOFF.md` | 本文件 |
| `CITATION-POLICY.md` / `CITATION-POLICY-PLAN.md` | 引用策略：是什么 / 怎么实现 |
| `LEXICON-PLAN.md` / `LEXICAL-SEARCH.md` | 词典/语法能力方案（未开工）/ 现有 grep·lemma |
| `FEDERATED-SEARCH.md` | `scope=all` / `routed` 与三种合并模式 |
| `RAG-DB-SCHEMA.md` / `RAG-DB-SCHEMA-V2.md` | 数据契约（v1 / v2） |
| `SIDECAR-CONTRACT.md` | 插件 ↔ sidecar 接口 |
| `USER-GUIDE.md` | 安装与使用 |
| `PORTABILITY.md` | 跨平台 + DSH 权限档矩阵 |
| `PLUGIN-MARKET.md` / `../market/index.json` | 插件市场索引格式与当前目录 |
| `.github/workflows/publish-npm.yml` | npm 发布（OIDC） |
| calcbox（外部） | 计算内核权威文档：[github.com/Icefox12138/calcbox](https://github.com/Icefox12138/calcbox)，PyPI `calcbox` |
| `HANDOFF-2026-11-*.md` | 各阶段历史交接（保留原结论） |

## 8. 代码与数据

```
D:\Guo-Code\socratic-tutor\      ← 本仓（公开，MIT）
  sidecar\              FastAPI + 检索/引用/策略/状态/计算适配
  plugin-socratic\      DSH 工具包（13 工具 + client.js + ptc.js）
  plugin-socratic-persona\ DSH 人格包（章程 + pre-step + 流改写）
  plugin-probe\         诊断用 capability probe（可选，不随发布）
  packages\             classics-index 0.1.3、socratic-mcp 0.2.0
  market\               插件市场索引（icon.png / persona-icon.png）
  .github\workflows\    ci.yml、publish-npm.yml
  samples\              5 页合成语料（夹具）
  docs\                 见 §7
  .venv-bge\            sidecar 运行所需（唯一留在本仓的 venv）

D:\Guo-Code\library\              馆藏（28.9 GB，只读）
D:\Guo-Code\rag-build\            数据工程（私有，无 git）
  data\                            search.db 296 MB + vectors + book_meta.json
  eval\                            管线脚本与实验结果
  docs\                            23 份 OCR/数据/语料画像文档
  HANDOFF.md                       该工程唯一记忆
```

## 9. 常用命令

```powershell
cd D:\Guo-Code\socratic-tutor

# sidecar（默认读 <repo>/data；指向私有库时用 SOCRATIC_DATA）
cd sidecar
$env:SOCRATIC_DATA='D:\Guo-Code\rag-build\data'; $env:SOCRATIC_BGE='0'
..\.venv-bge\Scripts\python.exe -m uvicorn app.main:app --port 8765 --timeout-keep-alive 75

# 测试
..\.venv-bge\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"   # 341
cd ..\plugin-socratic;      node --test --test-isolation=none test\plugin.test.mjs    # 6
cd ..\plugin-socratic-persona; node --test --test-isolation=none test\persona.test.mjs # 13

# 数据自检 / 契约自检
..\.venv-bge\Scripts\python.exe scripts\ragdb_check.py
..\.venv-bge\Scripts\python.exe scripts\contract_check.py --query 极限

# 发版（打 tag 即触发 OIDC 发布；不需要 npm token）
git tag -a dsh-socratic-v0.5.2 -m "dsh-socratic 0.5.2"
git push origin dsh-socratic-v0.5.2
```

OCR 相关命令在 `rag-build\HANDOFF.md`，环境是 `rag-build\.venv-ocr`。

## 10. 坑（别重踩）

1. **插件必须 `inject`**；用 `link:`；`post-execute` 签名 `(exec, result)`。
2. `run_code` 是 PTC 保留名，注册会报错。
3. **PaddleOCR 3.7 默认 oneDNN 会崩**（`ConvertPirAttribute2RuntimeAttribute`），必须 `enable_mkldnn=False`。
4. **DSH 沙箱 `tempfile.mkdtemp()` 不可写**（owner-only DACL，也删不掉）：测试用 `sidecar/tests/_tmp.py`。
5. **沙箱内 `node --test` 默认 `spawn EPERM`**：加 `--test-isolation=none`。
6. **沙箱内 git 网络操作**：HTTPS 用 `-c http.sslBackend=openssl`；**SSH 推送要在沙箱外**（git 会 spawn `sh` 建管道，`workspace-write` 下必失败）。`origin` 现为 SSH。
7. **工作区外只读不写**：`rag-build` 可读，写入需完全权限。
8. ODL 需要 Java 17；BGE/reranker 与 OCR 抢显存。
9. **`engines.dsh` 与预发布版本**：严格 semver 只承认"比较符带同一 `major.minor.patch` 预发布"的版本，`>=0.2.1-rc.2 <0.3.0-0` **不匹配** `0.2.2-rc.2`；DSH 用 `includePrerelease` 才放行。现用并集 `>=0.2.1-rc.2 <0.3.0-0 || >=0.2.2-rc.2 <0.3.0-0`。
10. **DSH 0.2.2 的冻结纪律**：`llm/stream` 的 options 深冻结（改写即抛）；`agent/pre-step` 的 decision 不要原地改，**返回新对象**（`{...res, messages:[注入, ...res.messages]}`）。
11. **`agent.pre-step` 的 `Agent` 只有 `id`**（没有 `.session`），取会话 id 用 `agent.id`。
12. **npm Trusted Publisher 的文件名必须逐字一致**，且新配置 **2 天内**必须首次发布成功，否则失效重配。
13. **不要用 silver 文本层当最终金标**（K6 已换 Perseus）。

## 11. 新会话建议

1. 读 `STATUS.md` → 本文件；
2. 先问 scope：私有 PDF 教学 / 公开语料 / 插件与发布；
3. 不要重跑 OCR/P1 全量；不要把私有库文本/向量带进公开仓；
4. 不要声称人工评分；v1 检索门与跨语言门仍未过；
5. 改测试时保持 `_tmp.py`；改文档时同步 `STATUS.md` 与 `PORTABILITY.md`；
6. 发版只打 tag，不要手工 `npm publish`（OIDC 已接管）。
