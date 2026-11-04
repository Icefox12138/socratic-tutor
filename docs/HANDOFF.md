# 交接报告（新对话入口）

| 项 | 值 |
|---|---|
| 日期 | **2026-11-03** |
| 项目 | `D:\Guo-Code\socratic-tutor` |
| 设计 | lite v1.2 / full v2.14（状态已回填 `STATUS.md`） |
| 状态 | **P0 完成；P1 主体完成；P2-1…P2-8 完成（P2-8 条件通过）；P3 未开始** |
| 判定 | **收窄 GO** |
| 人工评分 | **跳过（无 2 名评分者）** |
| 测试 | sidecar **106/106** |

---

## 0. 一句话

**检索、引用、教学状态机、UI、持久化、安全门都已跑通；PTC、表格 TEDS、K5 页图策略三个选型都已收口；P3 复盘 v1（86.7%）与竖排卷级章回索引 + 页图浏览已交付；剩下的是篇级切分与人工评分。**

---

## 1. 不可违反的用户约束

- 单学生、单机；不接出版社 API/Key；只用自扫/公版 PDF。
- 五语种：现代汉语、文言繁体、英语、拉丁、古希腊。
- 来源可信分级；“以知乎回答为下限”；书级引用 + 页锚。
- 分级揭示 + “停止学习并回顾”；`answer_key` 物理隔离。
- 目标机 6800HS / 16 GB / 无独显；开发机 4060 8 GB；云只做 burst。
- 现代 Teubner / 后 1929 Loeb 只进 `personal`，不导出。

## 2. 当前状态

| 模块 | 状态 | 结果 |
|---|---|---|
| P0 预检/编目 | 完成 | 801 本 / 27.46 GB / 361,862 页 |
| P0 安全 | 完成 | 7/7 拦截 |
| P1-0 LLM | 完成 | strict 未引用 0/50、SR 100% |
| P1-1/1-2 入库 | 完成 | 167,192 chunks；transsheet 隔离 |
| P1-3 检索 | 完成 | 问句 **0.82**；中文 95%、跨语言 68.8% |
| P1-4 页图 | 完成 | 冷 16–134 ms、热 0 ms |
| P1-5/1-6 | 完成 | 100/100 可回页；基线 0.60→0.82 |
| P1-3c OCR | 完成（本地） | K6 Paddle **12.8%**；K5 页图（服务端强制，text 置空）；公式 GPU **5.8 s** |
| P1-3d ODL | 完成 | ODL 11–31 ms/页；bbox 更高；表格 TEDS 0.437 vs 0.527 → 不换 |
| P2-1 状态机 | 完成 | 15/15；ALIGN→…→SUMMARY；L0–L5 |
| P2-2 判定/critic | 完成 | 单问/引用/leak 硬拦截；47/47 |
| P2-3 BKT/FSRS | 完成 | 参数未标定；51/51 |
| P2-4/5 UI | 完成 | `/ui` + composer 面板 + turnTail 引用卡 + K5 页图 |
| P2-6 对话评估 | 完成（自动） | 100 段/266 回合；人工评分跳过 |
| P2-7 持久化 | 完成 | 事件溯源 + replay |
| P2-8 PTC | 条件通过 | `ptc_calc` 10/10、逃逸 0；原生 `run_code` 未注入（**已过期，见 P2-9**） |
| P2-9 PTC token | 完成（否定） | 原生 `run_code` 可用；PTC −2.2% / 计费 +6.5% / 墙钟 +23.6% |
| P3 | 复盘 v1 + 章回/篇级索引完成 | 复盘 86.7%；C1 15 行索引覆盖 358/358；检索已支持 `book`+`chapter`（扫描本回页图） |

## 3. 架构与不变量

```
L3 DSH Host 插件（dsh-socratic）
   状态机/提示/critic/pre-step/llm-stream 硬拦截
        │ HTTP
L2 FastAPI sidecar（:8765）
   检索/引用/页图/计算/状态机/事件
        │
L1 SQLite catalog + FTS5 bigram + BGE npy + 页图缓存
```

- **答案隔离**：`visibility=answer_key` 在 SQL/向量层过滤，不靠提示词。
- **状态真源**：sidecar `sessions/state_events`；每轮显式摘要。
- **引用**：书/卷/页 + 页图；S 级逐条页图。
- **教学**：确定性状态机；LLM 只做措辞/判定解释。
- **硬拦截**：`llm/stream` 顺序 引用→leak→单问；纯文本流失去逐字流式。

## 4. 关键数字

| 项 | 值 |
|---|---:|
| 馆藏 | 801 本 / 27.46 GB / 361,862 页 |
| 合并 chunks | 167,192 |
| 问句 recall | **0.82** |
| 中文 / 拉丁 / 希腊 | 95% / 75% / 58% |
| 中文 OCR CER | 12.1% |
| K6 拉丁 CER（Perseus） | Paddle 12.8 / Rapid 14.1 / MinerU 16.2 |
| K5 希腊 CER | 70.9–94.0（不可用） |
| 公式 p114 | CPU 87.5 s → GPU **5.8 s**（46 条） |
| 公式 p118 | GPU 76.9 s；仍页图 fallback |
| sidecar | 预热 p95 ~830 ms；缓存 ~10 ms |
| 测试 | **106/106** |

## 5. 已验证 / 未验证

**已验证**

- `view`/`answer_key` 过滤；100/100 可回页；S 级页图；transsheet 隔离。
- strict LLM 50 轮未引用 0/50。
- 状态机 + 事件回放；重启不丢。
- 硬拦截：单问、引用、leak；L4+ 放行。
- K6 拉丁 Perseus 金标；K5 页图引用实际点击。
- 安全 7/7。
- PTC `ptc_calc` 10/10、逃逸 0。

**未验证 / 未做**

- ~~DSH 原生 `run_code`~~（rc.5 已可用，`DSH_TOOLS_MODE=ptc`）。
- ~~`ptc_calc` token 节省~~（已验证：不达标，见 `P2-9-PTC-token.md`）。
- ~~K5 希腊 OCR~~（本地失败；策略已落地：服务端只回页图，见 `P1-3c-K5-pageimage.md`）。
- 公式 p118 生产级延迟/质量。
- ~~ODL 表格 TEDS~~（已测：`P1-3d-TEDS.md`，0.437 vs 0.527，不换）。
- 人工评分（无评分者）。
- 第三模型、三流 100 条金标。
- P3 复盘/竖排。

## 6. 关键决策

| 决策 | 内容 |
|---|---|
| ADR-012 | 检索层自建 `socratic-search`；`dsh-knowledge` 降 P4 |
| ADR-013 | `deepseek-chat` 主模型；critic 规则；第三模型缺凭据 |
| 收窄 MVP | 古典 + 理工正文 + 中文页图；竖排只页图 |
| 公式 | 文字层 `conf=0`；高置信 LaTeX 或页图；p118 页图 |
| 中文 | OCR 只检索；引用回页图 |
| 设施 | 本地 4060；不租常驻 GPU；不整库上云 |
| PTC | 原生 `run_code` 可用但实测不省 token；`ptc_calc` 仅试点，不默认 |

## 7. 文档地图

| 文件 | 用途 |
|---|---|
| `STATUS.md` | **当前快照，先读** |
| `HANDOFF.md` | 本文件 |
| `DESIGN.md` / `DESIGN-full.md` | lite/full 设计 |
| `REMAINING.md` | 剩余工作 |
| `GAPS.md` | 评测 vs 工程缺口 |
| `P2-8-PTC.md` | 原生 PTC 探针 + `ptc_calc` |
| `P1-3c-*` / `P1-3d-ODL.md` | OCR/公式/解析器 |
| `C-DRIVE-MIGRATION.md` | 存储迁移 |

## 8. 代码与数据

```
D:\Guo-Code\socratic-tutor\
  docs\                 设计/报告/索引
  eval\p0\              P0
  eval\p1\              P1（ingest/eval/bakeoff/pages/STATUS.md）
  eval\p2\              P2（dialogues/ptc）
  sidecar\              FastAPI + state
  plugin-socratic\      DSH 插件 + client + ptc.js
  .venv-bge\            sidecar/BGE
  .venv-ocr\            OCR（CPU Paddle）
  .venv-paddle-gpu\     Paddle 3.0 CUDA
  .venv-mineru\         MinerU
D:\Guo-Code\PDF\        馆藏
D:\Guo-Code\PDF-new\Steadman\
D:\Guo-Code\loeb\       L036/L063N
D:\Guo-Code\teubner\    Conte/West
```

常用命令：

```powershell
cd D:\Guo-Code\socratic-tutor
# sidecar
cd sidecar
..\.venv-bge\Scripts\python.exe -m uvicorn app.main:app --port 8765
# 测试
..\.venv-bge\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
# OCR / ODL
..\.venv-ocr\Scripts\python.exe eval\p1\bakeoff\run_bakeoff.py --engines paddleocr --pages 12
```

## 9. 坑（别重踩）

1. DSH 插件必须 `inject`；用 `link:`；`post-execute` 签名 `(exec,result)`。
2. `run_code` 是 PTC 保留名；注册会报错；`@deepseek-ai/dsh-ptc-runtime` 没有 `dsh.bundle`，不能直接加 bundles。
3. Paddle 3.7 默认 oneDNN 在 PP-OCRv6 报 `ConvertPirAttribute...`；必须 `enable_mkldnn=False`。
4. 公式 p118 整页 CPU 424.8 s；GPU 76.9 s；仍走页图。
5. ODL 需要 Java 17；Java 8 报 class version 55。
6. MinerU 4.1.3 需要本地 server；`watchfiles` 装不上，用 stub。
7. BGE/reranker 与 sidecar 同卡；跑 OCR 前注意 8 GB 显存。
8. 不要用 silver 文本层当最终金标（K6 已换 Perseus）。

## 10. 新 PTC 会话建议

1. 读 `STATUS.md` + 本文件；
2. PTC 已闭（`P2-9-PTC-token.md`）：原生可用、不省 token、不默认；
3. 下一步：P3 竖排章回索引 / 页图浏览，或找 2 名评分者补人工验证；
4. 不要重跑 P0/P1；不要声称人工评分。
