# P1-3c OCR 四引擎 60 页 bake-off

| 项 | 值 |
|---|---|
| 日期 | 2026-10-30 |
| 页型 | C1 史记竖排 / B2 理想国横排 / K5 Loeb 希腊 / K6 Loeb 拉丁 / A2 李尚志公式，各 12 页 = **60 页** |
| 引擎 | RapidOCR（现状）、PaddleOCR（Umi 同源）、MinerU 2.5、OCRFlux-3B |
| 产物 | `run_bakeoff.py`、`scorecard.json`、`scorecard.md`、`out/<engine>/<group>/*.txt` |
| 结论 | **harness 完成；RapidOCR 基线已跑 60/60；其余三引擎待环境** |

## 1. 基线（RapidOCR，200dpi）

| 组 | 页数 | 平均字符 | 平均耗时 |
|---|---:|---:|---:|
| C1 史记竖排 | 12 | 452 | 2209 ms |
| B2 理想国横排 | 12 | 551 | 2625 ms |
| K5 Loeb 希腊 | 12 | 1477 | 2080 ms |
| K6 Loeb 拉丁 | 12 | 1289 | 2016 ms |
| A2 李尚志公式 | 12 | 714 | 2287 ms |

60/60 成功，无跳过。注意：**字符数不等于正确率**；C1 的 452 字里含大量误识（P0 已证）。

## 2. 怎么跑

```bash
# 现状基线
python run_bakeoff.py --engines rapidocr --pages 12

# PaddleOCR（需 Python 3.10–3.12 + paddlepaddle）
python run_bakeoff.py --engines paddleocr --pages 12

# Umi-OCR：先启动其 HTTP 服务（默认 1224）
python run_bakeoff.py --engines umi --umi-url http://127.0.0.1:1224

# MinerU：需 `mineru` CLI（会按单页 PDF 跑，慢）
python run_bakeoff.py --engines mineru --pages 2 --groups A2

# OCRFlux-3B：需 GPU + 权重
python run_bakeoff.py --engines ocrflux --ocrflux-model ChatDOC/OCRFlux-3B --pages 2 --groups K5
```

脚本行为：

- 从 `sample-manifest.json` 的窗口等距抽 12 页；
- 渲染 200dpi PNG 到 `pages/`；
- 每个引擎输出到 `out/<engine>/<group>/p<page>.txt`；
- 引擎缺失/服务未起 → `skipped` 并记录原因，不中断其他引擎；
- `scorecard.json` 逐页记录 `chars/cjk/greek/latin/cer/poly_recall/ms`。

## 3. 金标与自动指标

`gold/README.md` 说明格式。有金标时自动算：

- **CER**：归一化编辑距离；
- **希腊变音符召回**：U+1F00–1FFF 字符占比。

仍需人工填：

- C1：列序、注文错分；
- B2：脚注分离、结构 F1；
- K5：变音符人工抽检；
- K6：行对齐；
- A2：公式 CDM、表格 TEDS。

## 4. 判定规则（按页型，不做一刀切）

| 组 | 切入门槛 | 不过怎么办 |
|---|---|---|
| C1 竖排 | 列序 ≥95% 且 注文错分 ≤10% | **维持页图 + 卷次索引**，不投入逐字 |
| B2 中文横排 | CER ≤10% 且 脚注分离 ≥90% | 只做检索/提示，引用回页图 |
| K5 希腊 | CER ≤6.07% 且 变音符 ≥99% | 保持现有 OCR + 页图核验 |
| K6 拉丁 | CER ≤0.64% | 不换（现有已很好） |
| A2 公式 | CDM ≥0.75 | 公式页图 + VLM 高置信 LaTeX |

## 5. 当前状态

- **RapidOCR**：已跑；
- **PaddleOCR**：Python 3.14 无 paddle 轮子，待 3.11 venv；
- **Umi-OCR**：未起 HTTP 服务；引擎与 RapidOCR 同源，预期 CER 无提升，只测“竖排顺序”；
- **MinerU 2.5**：CLI 未安装；需单独环境 + 显存；
- **OCRFlux-3B**：权重/GPU 未就绪。

`mineru,umi` 已用 2 页试跑，均正确标记 `skipped`，harness 不崩。

## 6. 建议的 2–3 天执行顺序

1. 先补 **K5/K6 金标各 12 页**（最省力，能直接判希腊/拉丁要不要换）；
2. 装 MinerU 2.5，只跑 A2/B2 各 12 页（公式/版面）；
3. 起 Umi-OCR HTTP，只跑 C1 12 页（竖排顺序）；
4. OCRFlux-3B 只在 A2 上试 4 页，GPU 不足就放弃；
5. 汇总 `scorecard.md`，按 §4 规则写“采用/不采用”，回填 DESIGN §8.2。

## 7. 产物

`run_bakeoff.py`、`scorecard.json`、`scorecard.md`、`out/rapidocr/**`、`pages/**`、`gold/README.md`。

## 8. 解析器对照（P1-3d，同脚本）


un_bakeoff.py 增加 --parser：

`ash
# PyMuPDF（现状）
python run_bakeoff.py --parser pymupdf --pages 12 --groups A1,B4

# OpenDataLoader local（需 Java 11+ 与 pip install opendataloader-pdf）
python run_bakeoff.py --parser opendataloader --pages 12 --groups A1,B4
`

已试跑：

- pymupdf：A1/B4 各 2 页，4/4 成功（A1 766/769 字，B4 711/700 字）；
- opendataloader：模块未安装，正确标记 skipped（No module named opendataloader_pdf）。

对照指标：阅读顺序、表格 TEDS、bbox 覆盖率、耗时。ODL 官方称 local 0.02 s/页、Apache-2.0，但为厂商自评，需自测。
