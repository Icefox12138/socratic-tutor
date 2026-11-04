# 硬件需求与云选型分析

| 项 | 值 |
|---|---|
| 日期 | 2026-11-02（2026-11-03 回填） |
| 当前机器 | RTX 4060 Laptop 8 GB / 31.7 GB RAM / 32 逻辑核 / D 盘 |
| 自有机器 | Ryzen 7 6800HS（8C/16T）/ 16 GB RAM / 512 GB SSD / Radeon 680M 核显 |
| 结论 | **6800HS 做日常教学/文本；开发机 4060 做 GPU 验证；24 GB 以上 VLM 才上云，不租常驻** |

---

## 1. 结论先行

1. **6800HS + 16 GB + 512 GB 足够跑“收窄 MVP”**：文本解析、FTS bigram 检索、页图渲染、DeepSeek API 教学、SQLite/Qdrant 本地。
2. **不够跑“全量 OCR + BGE-M3 全量嵌入 + 本地 7B+ LLM + VLM OCR”**：16 GB 内存是硬约束，无 CUDA 是第二约束。
3. **当前 4060 8 GB 已实测可跑 BGE-M3**：148k chunks 14–20 min，显存峰值 3.8 GB；MinerU 1.2B 可，OCRFlux-3B 仍勉强，7B LLM 慢。
4. **推荐混合**：本机做日常与文本；BGE 嵌入可用 4060 或 **8 GB 级云卡**；24 GB 只留给 3B VLM。对象存储做备份。**不租常驻 GPU，不买新机器。**

---

## 2. 负载画像

| 负载 | CPU | RAM | GPU | 磁盘 | 实测/估算 |
|---|---|---|---|---|---|
| 编目/哈希 801 本 | 1 核 | 1 GB | 无 | 28 GB | 4.4 s（哈希） |
| 61 本文本解析 | 4 核 | 2 GB | 无 | 2 GB | 分钟级 |
| 横排 OCR（330k 页） | 8–16 线程 | 4–8 GB | 无 | 2 GB | **2.2 s/页**；单核 202 h，8 并发 ≈25–30 h |
| 竖排 OCR | 8 线程 | 4 GB | 无 | — | P0 判定不可用，不排 |
| BGE-M3 嵌入（148k chunks） | 8 核 | 3 GB | **8 GB 起** | 0.29 GB fp16 | 4060 实测 14–20 min；CPU 2–5 h |
| Qdrant/向量检索 | 2 核 | 1–2 GB | 无 | 1 GB | p95 <100 ms |
| 页图渲染 | 1 核 | 0.5 GB | 无 | 2 GB 缓存 | 冷 16–134 ms，热 0 ms |
| 教学运行时（DSH+sidecar） | 2 核 | 4–6 GB | 无 | 10 GB | LLM 走 API |
| 本地 7B LLM q4 | 8 核 | 8 GB | **6–8 GB** | 5 GB | 可用但慢，不建议 |
| VLM OCR（MinerU 1.2B / OCRFlux-3B） | 8 核 | 8 GB | **8–24 GB** | 5–10 GB | 8 GB 勉强，24 GB 稳 |
| 全量备份 | — | — | — | 2× 29 GB | 3-2-1 |

**瓶颈排序**：显存 > 内存 > 磁盘 > CPU。

**BGE-M3 实测（2026-11-02）**：148,261 个 tutor chunks，RTX 4060 8 GB，256 tokens 844 s / 512 tokens 1,209 s；显存峰值 **3.8 GB**；向量 **290 MB fp16**；查询编码 ~3.2 ms。**Reranker 2.27 GB，100 查询 108 s**；与 BGE 同时加载约 6 GB，8 GB 可放下。结论：嵌入+重排 8 GB 卡足够，24 GB 只留给 3B VLM。

---

## 3. 两台机器评估

### 3.1 自有：6800HS / 16 GB / 512 GB / 680M

| 项 | 判断 |
|---|---|
| CPU 8C/16T | 文本解析、OCR（8 并发）够用；全量 OCR 约 30–40 h，可夜间跑 |
| 16 GB 共享内存 | **最紧**：DSH + 浏览器 5–6 GB，Qdrant 1–2 GB，OCR 3–4 GB，余量小；并发高会 swap |
| 512 GB SSD | 够：原件 29 GB + 派生 5 GB + 模型 10 GB + 备份 30 GB ≈75 GB，留 100 GB 余量 |
| 680M 核显 | 跑 ONNX RapidOCR 可以；**BGE-M3 只能 CPU（2–5 h）**，不实用；3B VLM 不现实 |
| 结论 | **日常主力**：教学、FTS、页图、API LLM；批量 GPU 任务上云 |

建议：OCR 时关浏览器/IDE；把并行度降到 4–6；页图缓存上限从 2 GB 降到 1 GB。

### 3.2 当前：4060 8 GB / 31.7 GB / 32 核

| 项 | 判断 |
|---|---|
| 8 GB 显存 | **BGE-M3 实测可行**（峰值 3.8 GB，14–20 min/148k）；MinerU 1.2B 可；OCRFlux-3B 勉强；7B LLM 可但慢 |
| 31.7 GB 内存 | 可并行 OCR + 解析 + 检索 |
| 32 逻辑核 | 全量 OCR 约 8–10 h（8–12 并发） |
| 469 GB 磁盘 | 够全量与备份 |
| 结论 | **短期开发/基准机**；不是长期归属，不能当部署目标 |

---

## 4. 云选型

### 4.1 策略：burst GPU + 对象存储，不做 lift-and-shift

- 单用户、低频批处理，**常驻 GPU 是浪费**；
- 教学时 LLM 走 DeepSeek API，不需要 GPU；
- 只有“嵌入、VLM OCR、四引擎对照、全量 OCR”需要弹性算力；
- 原件 29 GB 上传是瓶颈，**按任务选书上传**，不整库上云。

### 4.2 GPU 选型

| 场景 | 最低显存 | 推荐卡 | 理由 |
|---|---:|---|---|
| BGE-M3 嵌入 | **8 GB** | **RTX 4060 8 GB / L4 24 GB** | 实测峰值 3.8 GB，148k chunks 14–20 min |
| MinerU 2.5（1.2B） | 8 GB | 4090 / L4 | 权重 ~3 GB，24 GB 可并行 |
| OCRFlux-3B | 16 GB | **4090 24 GB / A10 24 GB** | fp16 ~7 GB + 视觉/激活，8 GB 易 OOM |
| 本地 7B–14B LLM | 8–16 GB | 4090 24 GB | q4 7B 约 5 GB，14B 约 9 GB |
| 微调/训练 | 40 GB+ | A100 40/80 | 本项目不需要 |

**不推荐**：8 GB 卡跑 3B VLM（易 OOM）；A100（性价比低，除非训练）。**BGE-M3 用 8 GB 卡即可**。

### 4.3 供应商

| 类型 | 代表 | 适合 | 注意 |
|---|---|---|---|
| 按小时 GPU | **RunPod**、Vast.ai | 批量嵌入/VLM/对照 | BGE 选 8 GB；VLM 选 24 GB；Vast 便宜但机器质量参差 |
| 托管 GPU | Lambda、AWS g5/g6 | 稳定、合规 | 贵 2–3 倍；g5 A10G 24 GB、g6 L4 24 GB |
| Serverless GPU | Modal、Replicate | 偶发 60 页 bake-off | 冷启动、模型上传；按秒计费 |
| 对象存储 | **Cloudflare R2**、Backblaze B2 | 备份/交换 | R2 无出网费；B2 便宜 |
| 小 VPS | Hetzner CX32 | 可选常驻 sidecar | 单用户不必；本地即可 |

**推荐组合**：

- **主**：RunPod 8 GB 级（BGE 嵌入）+ RTX 4090 24 GB（VLM 对照）+ Cloudflare R2；
- **备**：Vast.ai（更便宜，任务可中断）；
- **合规优先**：Lambda 或 AWS g6 L4；
- **不选**：常驻 GPU 云主机、8 GB 卡跑 3B VLM、A100。

### 4.4 成本量级（2026-10 参考，随地区/时段波动）

| 任务 | 配置 | 时长 | 成本 |
|---|---|---|---|
| BGE-M3 148k chunks | 4060 / 8 GB 级 | 20 min | **$0.05–0.15** |
| 60 页四引擎对照 | 4090 24 GB | 20–40 min | **$0.2–0.5** |
| 全量 OCR 330k 页 | 16 vCPU / 32 GB | 25–40 h | **$5–15** |
| 备份 100 GB | R2 | 月 | **~$1.5/月** |
| 教学 LLM | DeepSeek API | 50 轮 | **$0.1–0.5/次** |

结论：**一年批量云成本大概率 < $100**，远低于买一张 24 GB 显卡。

---

## 5. 推荐配置（按阶段）

### 阶段 A：现在（P1 收尾 / P2 开发）

- 机器：**6800HS 16 GB**；
- 做法：文本管线 + FTS + 页图 + DeepSeek API；BGE-M3 与 VLM 用 RunPod 4090 按小时；
- 磁盘：保留 ≥100 GB；页图缓存 1 GB；
- 并行：OCR 4–6 线程，避免 swap。

### 阶段 B：全量入库（可选）

- 本机夜间 OCR（8C，约 30–40 h）；或租 16 vCPU/32 GB CPU 实例（$5–15）；
- BGE-M3 租 4090（15 min）；
- 备份上传 R2（加密、只传原件与索引）。

### 阶段 C：若要做本地 LLM

- 不推荐在 6800HS 上跑 7B+；
- 真要本地：24 GB 显存台式/云机；否则继续 API。

---

## 6. 风险与注意

1. **16 GB 内存是硬约束**：OCR + 嵌入 + 浏览器并发会 swap；分时执行。
2. **8 GB 显存是假经济**：VLM 3B 容易 OOM，租 24 GB 更省时间。
3. **上传瓶颈**：29 GB 原件在 20 Mbps 下约 3.2 h；按任务选书，不整库上传。
4. **数据合规**：版权 PDF 不上公共模型训练；选无训练条款的 provider；任务后删除卷。
5. **许可**：MinerU AGPL、OCRFlux `qwen-research`，云上调用可以，但不能打包进 MIT 插件分发。
6. **Windows vs Linux**：云上 Linux 需重跑路径/编码测试；脚本已尽量用 UTF-8 与 pathlib。
7. **备份**：3-2-1；原件不可变；云备份加密，密钥本地保管。

---

## 7. 决策建议

- **不买新硬件**：6800HS 对收窄 MVP 够用；
- **不租常驻 GPU**：按小时 4090 24 GB，用完即停；
- **不上整库云**：原件留本地，按任务上传；
- **教学 LLM 用 API**：本地 7B 在 16 GB 机器上体验差；
- **云只做三件事**：BGE-M3 嵌入、VLM/OCR 对照、全量 OCR 的弹性 CPU。

---

## 8. 2026-11-03 实测回填

- **4060 可用 PaddlePaddle GPU 3.0.0（CUDA 11.8）**：`is_compiled_with_cuda()=True`；
- 公式 OCR（PP-FormulaNet）p114：CPU 87.5 s → **GPU 5.8 s**（46 条）；p118 76.9 s；
- MinerU 4.1.3 独立 venv 可跑；OCRFlux 仍未跑；
- ODL 需要 Java 17（JDK 在 D 盘），A1/B4 整本 31/11 ms/页；
- 所有 venv/缓存/模型在 D 盘，C 盘可用约 **24 GB**；
- 8 GB 显存仍是瓶颈：BGE+reranker 约 6 GB，跑 OCR 前需停 sidecar；
- 云仍只作为 24 GB VLM/OCRFlux 的 burst，不租常驻。

