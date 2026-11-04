# P1-3c 本地三引擎报告（OCRFlux 推迟）

| 项 | 值 |
|---|---|
| 日期 | 2026-11-02 |
| 范围 | 本地：RapidOCR / PaddleOCR / MinerU |
| OCRFlux | **按用户决定推迟**（需 16–24 GB 显存或云 4090） |
| 结果 | 三引擎各 **60/60** 页；K5 希腊失败、K6 拉丁可用；OCRFlux 推迟 |
| 公式 | 见 [P1-3c-formula-ocr.md](P1-3c-formula-ocr.md)：p114 GPU 5.8 s，p118 76.9 s 仍页图 |

## 1. 引擎与版本

| 引擎 | 版本/配置 | 设备 | 60 页 |
|---|---|---|---|
| RapidOCR | `rapidocr_onnxruntime`（P0 基线） | CPU | 60/60 |
| PaddleOCR | 3.7.0 + PaddlePaddle 3.3.1；PP-OCRv5 mobile；`enable_mkldnn=False`、`use_textline_orientation=False` | CPU | 60/60 |
| MinerU | 4.1.3；独立 `.venv-mineru`；本地 `mineru server`；`parse --tier flash` | DirectML/CPU | 60/60 |
| OCRFlux | 未跑 | — | — |

## 2. 文本量（平均字符/页）

| 组 | RapidOCR | PaddleOCR | MinerU |
|---|---:|---:|---:|
| C1 史记竖排 | 452 | 478 | 463 |
| B2 理想国 | 551 | 558 | 694 |
| K5 Loeb 希腊 | 1477 | 1506 | 1532 |
| K6 Loeb 拉丁 | 1289 | 1295 | 1410 |
| A2 公式 | 714 | 838 | 811 |

完整表：`eval/p1/bakeoff/scorecard-all.md`。

## 3. 关键发现：原 K5/K6 窗口无效

- **K5**（Plato L036，页 82–104）实际是 **英文导言/译本**，不是希腊原文；三引擎希腊字符数均为 **0**。
- **K6**（Vergil L063N，页 249–278）抽样 p249 是 **“Digitized by Google”空白页**；拉丁计数包含英文，不能当拉丁 OCR 结果。
- 因此原窗口的 24 页只能算“版面/文本量”，不能算古典 OCR 质量。

## 3.1 正文页复跑（12+12 页）

按 PDF 文本层重新定位：

- K5 希腊正文：页 **85–107 奇数**（12 页）；
- K6 拉丁正文：页 **251–273 奇数**（12 页）。

结果（CER 越低越好）：

| 引擎 | K5 希腊 CER | K6 拉丁 CER |
|---|---:|---:|
| RapidOCR | **0.940** | 0.141 |
| PaddleOCR | **0.851** | **0.128** |
| MinerU | **0.709** | 0.162 |

**K5 希腊：三引擎全部失败**——输出被拉丁化/ASCII 化（`AIOAORIA`、`μev`），变音符召回 **0**；MinerU 最好也只有 0.709，不可用于原文引用。

**K6 拉丁：可用**——PaddleOCR **12.8%**、RapidOCR 14.1%、MinerU 16.2%（Perseus 金标；比 silver 的 3–8% 高，说明 silver 偏乐观）。

### K6 拉丁：Perseus 金标验证

- 用 `aeneid.xml` 行号 1–354 对齐 12 页；
- CER 比 silver 高：Paddle **0.128**、Rapid 0.141、MinerU 0.162；
- 说明 silver 文本层与引擎同源、偏乐观；Perseus 才是真实水平。
- 说明 silver 文本层对拉丁页基本可靠，K6 可用 PaddleOCR。

**K6 gold 已升级为 Perseus**（`eval/p0/gold/aeneid.xml`，按行号 1–357 近似对齐）：**PaddleOCR 12.8%**、RapidOCR 14.1%、MinerU 16.2%；比 silver 高，说明 silver 偏乐观。

**K5 gold 仍是 PDF 文本层 silver**（希腊 OCR 失败，不值得先做金标）。

silver/ Perseus 抽检：6/24 页（25%）语言/行序；未做逐字人工校对。

## 4. 工程问题

- PaddleOCR 3.3.1 默认 oneDNN 在 `PP-OCRv6_medium` 上报
  `ConvertPirAttribute2RuntimeAttribute not support`；关 `enable_mkldnn` 后正常，但慢。
- 换 PP-OCRv5 mobile 后 ~12–17 s/页；K5 p92 在 harness 中会卡住，直接脚本可跑（16.8 s），已在 harness 外补跑 K5。
- MinerU 4.1.3 需要本地 `mineru server`；缺 `watchfiles`（Rust wheel 装不上）时服务起不来，已用最小 stub 绕过（仅解析用）。
- MinerU 模型/服务缓存在 `C:\Users\...\.mineru` 248 MB，已迁 D（junction）。
- 三引擎输出：`eval/p1/bakeoff/out/{rapidocr,paddleocr,mineru}`。

## 5. 公式 OCR 试验

- 用 PaddleOCR `FormulaRecognitionPipeline`（PP-FormulaNet_plus-M）跑 A2 4 页；
- 识别 **127 条 LaTeX**，示例含行列式、线性方程组；
- CPU 延迟 **39–406 s/页**，太慢，只保留样本；
- 无公式金标，未算 CDM；需要 GPU/裁公式块。
- 详见 `docs/P1-3c-formula-ocr.md`（含 bbox 裁剪：p118 8.3×，整体 2.3×，普通页反而略慢）。

## 6. 资源占用

| 项 | 值 |
|---|---:|
| PaddleOCR venv | `.venv-ocr`（Paddle 3.3.1 + 依赖） |
| MinerU venv | `.venv-mineru`（mineru 4.1.3 + 依赖，无 torch） |
| PaddleX 模型 | 160 MB（D 盘） |
| MinerU 缓存/模型 | 248 MB（D 盘） |
| OCRFlux | 0（未下载） |

## 7. 未完成

- K5/K6 gold 是 **PDF 文本层 silver**，不是人工/Perseus 金标；未做逐字双人校对；
- K5 希腊 OCR 失败，需要 VLM/希腊专用 OCR 或只做页图引用；
- OCRFlux（推迟）；
- 表格 TEDS / 公式 CDM；
- 手动列序/注文错分；
- Umi-OCR 未起服务（Paddle 同源，暂不重复）。

## 8. 下一步

1. K5：接受“希腊 OCR 不可用，只页图引用”，或试 VLM/OCRFlux（云）；
2. K6：PaddleOCR 3% 可用，保留；
3. gold：用 Perseus 文本对齐替换 silver，抽检 20–30%；
4. OCRFlux 等 24 GB 云卡再补。
