# DESIGN-lite（v1.3，设计基线 full v2.14，状态同步 2026-11-03）

> 本文件是 300 行浓缩版，供交接/评审/新对话入口使用。
> 完整论证、DDL、代码片段、逐日 P0 记录在 [DESIGN-full.md](DESIGN-full.md)。
> 当前真实状态以 [STATUS.md](STATUS.md) 为准。

---

## 0. 一页摘要

- **做什么**：单机、单学生的苏格拉底式教学 Agent；DSH 插件 + Python sidecar；自扫/公版 PDF；五语种（现代汉语、文言繁体、英语、拉丁、古希腊）。
- **第一契约**：`answer_key` 在 chunk 级物理隔离，不靠提示词。
- **P0/P1/P2 结论**：管线跑通；P2 教学闭环（状态机/判定/UI/持久化）完成；**收窄 GO**。
- **当前版本**：lite v1.3；设计基线 full v2.14；总排期仍 393 h。
- **未闭合**：原生 PTC `run_code`、K5 希腊 OCR、p118 公式延迟、表格 TEDS、人工评分、P3 复盘。

---

## 1. 目标、非目标、MVP 判据

### 1.1 目标

| ID | 目标 |
|---|---|
| G1 | 馆藏可检索、可引用（书/卷/页） |
| G2 | 苏格拉底式教学：提问推进、分级揭示、强制回讲、防泄漏 |
| G3 | 复盘诊断：逐条判定、错误分类、归因、复练 |
| G4 | 机器计算：断言由工具产生并留痕 |
| G5 | 来源可信：主张与来源分级绑定，无源标“未核验” |
| G6/G7 | 五语种、三学科（产品目标，非 MVP 验收） |

### 1.2 非目标

多用户/账号/公网；LMS 对接；出版社 API；全库一次性 OCR；自动批改作文；移动端/语音（仅 IPA 示范）。

### 1.3 MVP（收窄后）

- **古典**：Steadman 含原文卷（`main_text_share ≥10%`）+ Loeb L036/L063N + Teubner 参照；检索、词表、行号、页图引用。
- **理工**：正文/代码/图表入库；公式只做页图；计算走 SymPy（键入或高置信 VLM LaTeX）。
- **中文**：OCR 仅检索/提示；引用回页图；不做逐字引用。
- **竖排**：页图 + 卷次索引；不做逐字 OCR。
- **引用**：书/卷/页 + 页图；S 级逐条页图。

判据：引用可回溯 100%；页图核验 100%；检索单语 ≥0.85 / 跨语言 ≥0.70；泄漏 ≤2%（施压 ≤5%，L4 前 0）；复盘 ≥80%。

---

## 2. 约束与基线

### 2.1 硬件

| 角色 | 配置 | 用途 |
|---|---|---|
| 日常机 | 6800HS 8C/16T / 16 GB / 512 GB / 680M | sidecar、FTS、页图、DSH、API LLM |
| 开发机 | 4060 8 GB / 31.7 GB / 32 核 / 469 GB | 基准、全量 OCR |
| 云 burst | RTX 4090 24 GB 按小时 | BGE-M3、VLM/OCR 对照 |
| 存储 | Cloudflare R2 | 加密备份 |

原则：不租常驻 GPU；不整库上云；16 GB 分时；512 GB 留 100 GB。

### 2.2 数据

- 馆藏 801 本 / 27.46 GB / 361,862 页（91.3% 影印）。
- 文字层 61 本 / 25,839 页；Steadman 100 卷 / 9,890 页；Loeb 2 卷；Teubner 2 卷。
- 重复 1 组（法言义疏）；加密 0。

### 2.3 合规

- 现代 Teubner / 后 1929 Loeb 只 `personal`；不导出、不快照、不上公开云。
- MinerU AGPL、OCRFlux `qwen-research`：只外部调用，不打包进 MIT 插件。

---

## 3. 架构

```
L3 DSH Host 插件（dsh-socratic）
   状态机 / 提示 / critic / 复盘 / 来源策略
        │ HTTP/SSE
L2 Python sidecar（FastAPI）
   编目 / 解析 / OCR / 检索 / 计算 / 复盘
        │
L1 SQLite catalog + FTS5 bigram + Qdrant + 页图缓存
```

**为什么拆 sidecar**：解析/OCR/ML 生态在 Python；崩溃隔离；可独立测试；Host 只编排。

**三条数据流**：

1. 入库：PDF → catalog → parse → chunks → FTS/向量 → 质量闸门。
2. 教学：学生输入 → 状态机 → 检索/计算 → LLM → critic → 输出。
3. 复盘：session events → 断言抽取 → 判定 → 报告。

---

## 4. 关键决策（ADR）

| ID | 决策 | 理由 |
|---|---|---|
| 01 | 自建轻量内核 | 教学逻辑需定制；平台锁定不可接受 |
| 02 | Python sidecar + 薄 Node 插件 | 生态 + 隔离 |
| 03 | 教学用确定性状态机，LLM 只生成/解释 | 纯提示必退化为问答机 |
| 04 | 原文/词表/注释三流分离 | 提示分层；避免注文当经文 |
| 05 | 答案物理隔离（`visibility`） | 模型看到就会泄漏 |
| 06 | 书级引用 + 内部页锚 | 用户要求；抽检可回页 |
| 07 | 按需入库 | 330k 页全量不现实 |
| 08 | SQLite + Qdrant 本地 | 单用户、零运维 |
| 09 | Steadman 首选古典语料 | 文字层干净、带词频/行号 |
| 10 | 复盘独立子系统 | 需证据链/分类/归因 |
| 11 | MVP 自建 `socratic-search` | `view` 强制、无 AGPL |
| 12 | 支架动态褪除 | 工作示例效应/专长逆转 |
| 13 | `deepseek-chat` 主模型（strict） | 50 轮未引用 0/50；规则 critic + 硬拦截 |

---

## 5. 数据模型（要点）

实体：`books / volumes / pages / chunks / citations / sessions / turns / attempts / reveals / reviews / findings / learner_state / ingest_jobs`。

关键字段：

- `chunks.visibility`：`student | tutor | answer_key`；
- `chunks.stream`：`text | gloss | note | apparatus`；
- `chunks.page_from/page_to`：页锚；
- `citations`：`chunk_id + page + bbox + tier`；
- `sessions.state`：概念/掌握度/提示级别/支架/预算；
- `reveals`：每次 L4/L5 必写。

完整 DDL 见 DESIGN-full §6.3。

---

## 6. 解析

### 6.1 路由（逐页）

`text`（文字层）/ `digital`（Steadman）/ `scan_h`（横排 OCR）/ `scan_v`（竖排）/ `vlm`（困难页）。

禁止 3 页采样定整本。

### 6.2 实测

| 页型 | 结果 | 处置 |
|---|---|---|
| 文字层 | 964 字/页；公式结构丢失 | 公式页图 |
| 中文 OCR | CER 12.1% | 只检索；引用页图 |
| 竖排 | 列序 18/18；注文未分离；OCR 不可读 | 页图 + 卷次 |
| 拉丁 Loeb | 行级 0.64% | 可用 |
| 希腊 Loeb | 句级 6.07% | 阅读可用；引用页图 |
| Teubner Conte | 1.9% | S1 基线 |
| Steadman | 52/100 有原文；48 commentary_only | 逐卷 `main_text_share` |

### 6.3 质量闸门

检索级 CER ≤10%；引用级页图 100%；竖排不设逐字 CER；公式 `text-layer conf=0`、VLM `conf≥0.9` 才可计算。

---

## 7. 检索

- **切分**：400–600 字，重叠 60–80，不跨节。
- **稀疏**：FTS5 `unicode61`；中文 **bigram**（`帝国 国主 主义`）；拉丁/希腊小写词。
- **稠密**：BGE-M3 1024d（已跑，148,261 tutor chunks，fp16）；Qdrant 本地。
- **融合**：RRF(k=60) + 可选 rerank。
- **隔离**：`view=student/tutor` 在 SQL/向量层过滤 `answer_key`；`answer_key` 不暴露工具。
- **实测**：167,192 chunks；词项 recall 1.00、p95 8.2 ms；问句集 FTS **0.60** → BGE **0.65** → hybrid **0.72** → rerank **0.77** → rerank+翻译 **0.82**（中文 95%、拉丁 75%、希腊 58%、英文 50%）。

**P1 出口门**：单语 ≥0.85、跨语言 ≥0.70；P1-3b2 后总体 **0.82**（过 0.80）、中文 95% 达标；跨语言 68.8%，距 0.70 差 1.2 点；总体 0.85 未达。

---

## 8. 来源与引用

- S1 校勘（Teubner/OCT apparatus）/ S2 阅读文本（Perseus/PHI/ctext）/ S3 译文（Loeb/Steadman）。
- 引用展示：`《史记》（中华书局 2013）· 卷七`；`Steadman, Apology, 20a`。
- 同书异版并列；每条引用可反查 `chunk → page → 原件`。
- 页图按需渲染：冷 16–134 ms、热 0 ms；2 GB LRU。

---

## 9. 教学

### 9.1 状态机

```
ALIGN → DIAGNOSE → PLAN → ASK → WAIT → EVALUATE
  ├─ 正确 → ADVANCE → TRANSFER/SUMMARY
  ├─ 部分 → HINT(+1) → WAIT
  └─ 错误 → HINT(+1) 或 REGRESS
```

状态由代码计算；LLM 只写问题/提示/解释。

### 9.2 提示阶梯

L0 重述 → L1 指向 → L2 类比 → L3 子步骤 → L4 近完整（留最后一步）→ L5 答案（必须回讲、写 `reveals`）。

### 9.3 揭示政策

`explicit_ask`、`attempts`、`frustration`、`hint_level` 共同判定；L4/L5 后强制回讲；被揭示题掌握度打 0.5 折。

### 9.4 上下文（≤12k token）

静态章程 800 + 状态摘要 300 + 检索 ≤6 条 + 计算凭证 + 最近 4 轮。

**状态真源在 sidecar**；每轮显式摘要，不依赖 `systemPrompt.context` 回放。

### 9.5 支架

`scaffold_level` 0–3、`hint_level` L0–L5、`guidance_mode` guided/strict/coach 三轴分离；按先备知识/任务类型动态褪除。

---

## 10. 复盘

1. 冻结 session 快照；
2. 只抽学生陈述（疑问/转述/引用标 `not_a_claim`）；
3. 判定 `correct/partial/incorrect/undetermined`；
4. 8 类错误 + 归因 `student/question/material/curriculum`；
5. 报告 + 复练 + 掌握度更新。

`undetermined` 不判错；材料错记质量台账并触发重解析。

---

## 11. 计算

- Python 子进程沙箱；SymPy/NumPy/SciPy/pint。
- 公式门控：文字层 `conf=0`；OCR 默认 0；只认 VLM 高置信 LaTeX。
- 凭证：输入 `chunk_id` + `formula_conf` + 代码/版本/种子。
- PTC：多步/批量用 `run_code` 编排；单题直接 `compute_python`；LEAN 长任务走 job。

---

## 12. DSH 集成

- 包：`dsh-socratic`、`socratic-search`、`socratic-sidecar`、`dsh-socratic-classics`、`socratic-eval`、`socratic-skill`。
- 工具：`kb_search`、`kb_read`、`dict_lookup`、`morph_parse`、`tutor_state`、`tutor_check`、`review_session`、`compute_python`、`cite_verify`。
- 钩子：`systemPrompt.section`（静态章程）、`tools/pre-execute`（来源门禁）、`tools/post-execute`（引用/泄漏标记）、`agent/pre-step`（状态摘要）。
- 实测约束：`inject` 必填；`post-execute` 签名 `(exec, result)`；开发用 `link:`；profile 无 BOM；headless 需 `@deepseek-ai/dsh-headless` + API key。

---

## 13. 部署

- 本机：`uv` + Python 3.12；sidecar 只绑 `127.0.0.1`；页图缓存 1 GB（16 GB 机）。
- 云：4090 24 GB 按小时；批量任务结束即停；原件默认不上云。
- 备份：catalog + 派生 QA + `eval/`；原件冷备；R2 加密。

---

## 14. 计划

| 阶段 | 周 | 工时 | 内容 |
|---|---:|---:|---|
| P0 | 1–3 | 56 h | 20 本 × 4 分支；收窄 GO |
| P1 | 4–12 | 150 h | 入库、检索、页图、质量闸门、评估集、OCR/解析器对照、BGE/reranker |
| P2 | 13–19 | 114 h | 状态机、critic、BKT、UI、100 段对话、PTC 试点 |
| P3 | 20–23 | 73 h | 复盘 v1、页图/章回索引 |
| P4 | 24–27 | 可选 | 二十四史批量、公式 VLM、第二语言包 |

Gate：P1 检索门；P2 对话 canary 0；P3 复盘 ≥80%。

---

## 15. 评估

- 检索：recall@10 / nDCG / citation precision，按语言 × stream × 质量分层。
- 引用：页图核验 100%；书名定位 ≥99%。
- 教学：泄漏 ≤2%（施压 ≤5%，L4 前 0）；回讲通过率。
- 复盘：≥80%，`undetermined <20%`。
- 系统：TTFT <3 s、总 <12 s。
- 评估集：100 条问句（`eval/p1/eval/questions.json`）。

---

## 16. 风险

| 风险 | 状态 | Fallback |
|---|---|---|
| 跨语言检索 | rerank+翻译 0.688；总体 0.82 | stream 过滤/page 索引；或接受 0.82 |
| 竖排注文 | 未分离 | 页图 + 卷次 |
| 中文 OCR | 12% CER | 只检索；引用页图 |
| 对话层泄漏 | 未测 | P2 canary；critic 重写 |
| 复盘准确率 | 未知 | v1 只判有证据断言 |
| 安全沙箱 | 未测 | 6 类攻击前禁计算 |
| 16 GB 内存 | 硬约束 | 分时；4–6 并发 |
| 排期 | 未验证 | 已加 40%/30% 缓冲 |

---

## 17. 未闭合

1. stream/page 索引冲 0.85；2. 竖排注文分层；3. 中文逐字引用；4. 对话层人工 canary；5. 复盘金标；6. **PTC 原生 `run_code` 未注入**；7. 三流 100 条金标；8. K5 希腊 OCR；9. ODL 表格 TEDS；10. 人工评分（无评分者）。

---

## 18. 文件地图

- `DESIGN-full.md`：完整设计（DDL/代码/论证）。
- `STATUS.md`：当前状态快照（先读）。
- `HANDOFF.md`：新对话交接。
- `REMAINING.md` / `GAPS.md`：剩余与缺口。
- `REVISION.md`：文档修订记录。
- `FEASIBILITY-REVIEW.md`：四处硬改依据。
- `HARDWARE-CLOUD.md`：硬件/云。
- `P0-PLAN.md`：P0 执行记录。
- `decisions/ADR-012/013`：检索/LLM。
- `visual/project.html`：一页可视化。
- 代码：`eval/p0`、`eval/p1`、`plugin-probe`。

---

> 冲突时：**HANDOFF 数字 > DESIGN-lite > DESIGN-full**；DESIGN-full 保留历史论证，不保证与最新数字一致。
