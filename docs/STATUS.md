# 项目当前状态（canonical）

> 本文件是 **2026-11-03 的唯一当前状态快照**。历史报告保留原始结论；与旧文档冲突时，以本文件 + `HANDOFF.md` 为准。

| 项 | 值 |
|---|---|
| 项目 | `D:\Guo-Code\socratic-tutor` |
| 阶段 | P0 完成；P1 主体完成（检索门未过）；P2-1…P2-9 完成；**P3-1…P3-6 完成**（复盘、卷/篇索引、页图浏览、回目、检索接入） |
| 判定 | **收窄 GO** |
| 设计版本 | lite v1.2 / full v2.14（内容状态已回填到本快照） |
| 环境 | 开发机 4060 8 GB / 32 核 / D 盘；日常目标机 6800HS 16 GB |
| 人工评分 | **延后**（用户决定：试用/开源/模型进步替代；仍不能声称人类验证） |
| PTC | 原生 `run_code` **可用**（rc.5 ptc preset）；token 实测 −2.2%，**不达标 → 不默认** |
| 测试 | sidecar **106/106** |

---

## 1. 已完成

| 模块 | 状态 | 关键结果 |
|---|---|---|
| P0 预检/编目/检索 | 完成 | 801 本 / 27.46 GB / 361,862 页；词项 recall 1.00 |
| P0 安全 | 完成 | 7/7 拦截（越权/token/穿越/注入/超长/跨会话） |
| P1-0 LLM | 完成 | `deepseek-chat` strict：未引用 0/50、SR 100% |
| P1-1/1-2 入库 | 完成 | 167,192 chunks；transsheet 隔离 |
| P1-3 检索 | 完成 | 问句 0.82；中文 95%、跨语言 68.8% |
| P1-3c OCR | 完成（本地） | K6 Perseus Paddle **12.8%**；K5 服务端强制页图（text 置空）；公式 GPU **5.8 s/页**（p114） |
| P1-3d 解析器 | 完成 | ODL 11–31 ms/页；bbox 覆盖更高；表格 TEDS **0.437 vs PyMuPDF 0.527** → 不换 |
| P2-1…P2-7 | 完成 | 状态机、判定/critic、BKT/FSRS、UI、100 段评估、持久化 |
| P2-8 PTC | 条件通过 | 10/10、逃逸 0；token 见 P2-9：−2.2%，不默认 |
| P2-9 PTC token | 完成（否定结论） | 原生 `run_code` 可用；PTC 计费加权 +6.5%、+23.6% 墙钟 |
| P3-1 复盘 v1 | 完成 | 判定 100%、错误分类 **86.7%**（留出集）、undetermined 0% |
| P3-2 章回索引/浏览 | 完成 | C1 358 页 → 7 卷 + 卷首尾；`/browse` 页图翻页；版心 OCR 1.2 s/页 |
| P3-3 篇级切分 | 完成 | 7 篇（五帝本紀第一…項羽本紀第七）定位到篇名页；一级覆盖 358/358 |
| P3-4 扫描泛化 | 完成 | 整页带宽扫描取代窗口；C1 复现 7/7 **并修正卷二为 p67**；S2 卷10–14 五篇正确 |
| P3-5 回目索引 | 进行中（2745/5291 页） | 215 回目段/3 部；过切已收紧；换书边界晚一回；未落库 |
| P3-6 检索接入 | 完成 | `kb_search` 支持 book+chapter；扫描本 `page_only` 回页图；`chapter_lookup`；turnTail 章回页图卡 |

## 2. 关键数字

| 项 | 值 |
|---|---:|
| 馆藏 | 801 本 / 27.46 GB / 361,862 页 |
| 合并 chunks | 167,192 |
| 问句 recall | **0.82**（FTS 0.60 / BGE 0.65 / rerank 0.77 / +翻译 0.82） |
| 中文 / 拉丁 / 希腊 | 95% / 75% / 58% |
| 中文 OCR CER | 12.1% |
| K6 拉丁 CER（Perseus） | Paddle 12.8% / Rapid 14.1% / MinerU 16.2% |
| K5 希腊 CER | 70.9–94.0%（不可用，页图优先） |
| 公式 p114 | CPU 87.5 s → **GPU 5.8 s**（46 条） |
| 公式 p118 | GPU 76.9 s；仍 fallback 页图 |
| sidecar 延迟 | 预热 p95 ~830 ms；缓存命中 ~10 ms |
| 测试 | sidecar **125/125** + `classics-index` 18 + `socratic-mcp` 6 + 插件契约 8 |
| 开源 | **已发布三件**：PyPI `classics-index` / `socratic-mcp` 0.1.0、npm `dsh-socratic` 0.2.0（2026-11-04） |

## 3. 运行与环境

```
DSH Host 插件 dsh-socratic
  ├─ 工具：kb_search/kb_read/cite_verify/compute_math/ptc_calc/socratic_*
  ├─ pre-step 摘要
  ├─ llm/stream：引用 → leak → 单问
  └─ client：composer 面板 + turnTail 引用卡（K5 希腊页图）
sidecar FastAPI :8765
  ├─ 检索/引用/页图/计算
  ├─ 状态机 + 事件溯源
  └─ auth/preload/query cache
```

- sidecar 启动：`.venv-bge\Scripts\python.exe -m uvicorn app.main:app --port 8765`；
- `SOCRATIC_PRELOAD=1` 预热；`SOCRATIC_REQUIRE_AUTH=1` 启用 token；
- 模型/缓存/venv 全在 D；C 盘可用约 **24 GB**；
- JDK17 在 `D:\Guo-Code\tools\jdk17`（ODL）；
- Paddle GPU venv：`.venv-paddle-gpu`（Paddle 3.0.0 CUDA 11.8）。

## 4. 未闭合/阻塞

| 项 | 状态 | 影响 |
|---|---|---|
| DSH 原生 PTC `run_code` | **已可用**（rc.5 ptc preset / `DSH_TOOLS_MODE`） | 阻塞解除 |
| `ptc_calc` token 节省 | **已验证：−2.2%**（计费加权 +6.5%） | 不默认化，试点保留 |
| K5 希腊 OCR | 失败（**策略已落地**） | 服务端只回 citation + 页图，`text` 置空 |
| 公式 p118 | 76.9 s / 质量下降 | 页图 fallback |
| ODL 表格 TEDS | **已算：ODL 0.437 / PyMuPDF 0.527** | 不替换；表格回页图 |
| 人工评分 | **延后（用户决定）** | 靠试用/开源/模型进步替代；仍不能声称人类验证 |
| 第三模型/三流金标 | 未做 | 评测覆盖有限 |
| 竖排多篇卷 | 已用章回小说验证 | 132 回目段；过切 +6%、分书晚 7 段 |

## 5. 权威产物

- 设计：`DESIGN.md`（lite）/ `DESIGN-full.md`（full）
- 交接：`HANDOFF.md`（新会话入口）
- 剩余：`REMAINING.md`
- 历史缺口：`GAPS.md`（已更新到当前）
- 报告：`P2-1…P2-8`、`P1-3c-*`、`P1-3d-ODL`、`P0-SECURITY`
- 迁移：`C-DRIVE-MIGRATION.md`

## 6. 新 PTC 会话建议

新开 PTC 会话时，第一段只给三件事：

1. 读 `docs/STATUS.md` + `docs/HANDOFF.md`；
2. PTC 已收口（`P2-9-PTC-token.md`）、表格 TEDS 已收口（`P1-3d-TEDS.md`）：都不换默认；
3. 下一步是 **K5 页图策略落地** 或 **P3 复盘 v1**，别重跑 P0/P1。
