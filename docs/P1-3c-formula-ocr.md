# P1-3c 公式 OCR 试验

| 项 | 值 |
|---|---|
| 日期 | 2026-11-02 |
| 引擎 | PaddleOCR `FormulaRecognitionPipeline`（PP-FormulaNet_plus-M + PP-DocLayout_plus-L + UVDoc） |
| 样本 | A2《线性代数》4 页（p114/118/122/126） |
| 结果 | 识别出 **127 条 LaTeX**；延迟 **39–406 s/页**（CPU） |
| 结论 | **可用但太慢**；需要 GPU 或只对公式块做识别 |

## 1. 配置

```python
from paddleocr import FormulaRecognitionPipeline
pipe = FormulaRecognitionPipeline(enable_mkldnn=False)
res = pipe.predict(img)
for f in res[0]["formula_res_list"]:
    print(f["rec_formula"])
```

- 需要 `paddlex[ocr]` extras（否则 `DependencyError`）；
- 必须 `enable_mkldnn=False`，否则 Paddle 3.3.1 oneDNN 报
  `ConvertPirAttribute2RuntimeAttribute`；
- 首次会下载 `PP-FormulaNet_plus-M`、`PP-DocLayout_plus-L`、`UVDoc`、`PP-LCNet_x1_0_doc_ori`。

## 2. 样本输出

p114（45 条）：

```latex
F_{n}=\frac{q_{2}^{n}-q_{1}^{n}}{q_{2}-q_{1}}
=\frac{\left(\frac{1+\sqrt{5}}{2}\right)^{n}
-\left(\frac{1-\sqrt{5}}{2}\right)^{n}}{\sqrt{5}}.
```

p118（23 条）：

```latex
x^{2}+y^{2}-x+2y-10=0
```

p122（16 条）：

```latex
\left\{\begin{aligned}
x&=\frac{c_{1}b_{2}-c_{2}b_{1}}{a_{1}b_{2}-a_{2}b_{1}},\\
y&=\frac{a_{1}c_{2}-a_{2}c_{1}}{a_{1}b_{2}-a_{2}b_{1}}.
\end{aligned}\right.
```

## 3. 延迟

| 页 | 公式数 | LaTeX 字符 | 延迟 |
|---:|---:|---:|---:|
| 114 | 45 | 1444 | 87.5 s |
| 118 | 23 | 3531 | **405.8 s** |
| 122 | 16 | 1580 | 38.7 s |
| 126 | 43 | 607 | 63.2 s |

p118 的 405 s 是异常慢（版面复杂）；12 页全跑预计 30 min+，因此只保留 4 页样本。

## 4. 限制

- 无公式金标，未算 **CDM / BLEU / 编辑距离**；
- 未验证 LaTeX 可编译/语义等价；
- 延迟 CPU 不可接受，需 GPU 或只裁公式区域；
- 多栏/表格内公式会漏或串行；
- 版面检测会把整页公式区域都送进模型，重复/碎片较多。

## 5. bbox 裁剪加速

流程：`LayoutDetection` 找 `formula`/`formula_number` 框 → PIL 裁图 → `FormulaRecognitionPipeline(use_layout_detection=False, batch=8)` 只做识别。

| 页 | 整页 | 裁剪 | 加速 | 公式数（整页/裁剪） |
|---:|---:|---:|---:|---:|
| 114 | 87.5 s | 93.9 s | 0.93× | 45 / 47 |
| 118 | **405.8 s** | **48.8 s** | **8.3×** | 23 / 28 |
| 122 | 38.7 s | 43.5 s | 0.89× | 16 / 19 |
| 126 | 63.2 s | 71.2 s | 0.89× | 43 / 46 |
| 合计 | 595.2 s | 257.3 s | **2.3×** | 127 / 140 |

结论：

- 裁剪只对 **p118 这类版面异常** 有 8× 加速；普通页反而慢 10–15%（布局+裁图+批处理开销）；
- p118 裁剪后 LaTeX 字符从 3531 降到 400，**质量明显下降**（区域切碎/重叠）；
- 真正瓶颈是 CPU 上的 PP-FormulaNet 推理（47 个框约 91 s），不是布局检测（2–3 s）；
- 想稳定提速：GPU、batch≥32、合并相邻公式框、只裁 `formula` 类（不裁 `formula_number`）。

## 6. batch=32 + 合并相邻框

在裁剪基础上：

- `formula_recognition_batch_size=32`；
- 只取 `formula` 类；
- 相邻/重叠框外扩 12 px 后合并（`merge_boxes`）。

| 页 | 整页 | 裁剪 batch8 | batch32+合并 | 对整页加速 |
|---:|---:|---:|---:|---:|
| 114 | 87.5 s | 93.9 s | **84.7 s** | 1.03× |
| 118 | 405.8 s | 48.8 s | **35.8 s** | **11.3×** |
| 122 | 38.7 s | 43.5 s | **43.1 s** | 0.90× |
| 126 | 63.2 s | 71.2 s | **55.7 s** | 1.13× |
| 合计 | 595.2 s | 257.3 s | **219.3 s** | **2.7×** |

质量：

| 页 | 框数（原→合并） | LaTeX 字符（整页/合并） |
|---:|---:|---:|
| 114 | 47→40 | 1444 / 1455 |
| 118 | 28→20 | 3531 / **297** |
| 122 | 18→16 | 1580 / 1734 |
| 126 | 46→28 | 607 / 1488 |

结论：

- batch32 让普通页再快 **10–25%**，总加速从 2.3× 提到 **2.7×**；
- p118 合并后字符只剩 297，**过度合并/丢行**，质量不可接受；
- 合并只适合“同一公式被切成多块”的场景，不能盲目合并相邻独立公式；
- 生产建议：batch32 + 不合并（或仅 IoU>0.5 合并），并对 p118 单独保留整页。

## 7. 生产策略：batch32 + 不合并

`formula_prod.py` 默认 **batch32、不合并**，p118 标记 `special` 单独处理。

| 页 | 整页 | batch32 不合并 | 框数 | LaTeX 字符 |
|---:|---:|---:|---:|---:|
| 114 | 87.5 s | 95.6 s | 47 | 1421 |
| 122 | 38.7 s | 46.3 s | 18 | 1715 |
| 126 | 63.2 s | 81.6 s | 46 | 647 |
| **118（special）** | **424.8 s** | **整页 424.8 s** | 23 | **3531** |
| 合计（普通页） | 189.4 s | **223.5 s** | — | — |

p118 单独走整页：**424.8 s / 23 条 / 3531 字符**，质量恢复；但**延迟不可接受**，`p118.json` 标记 `fallback=page_image`，UI 直接贴原页图。Paddle 安装的是 **CPU build**（`is_compiled_with_cuda()=False`），无法用 4060 加速；要 GPU 需换 `paddlepaddle-gpu`。

### GPU 复测（4060）

已建独立 `.venv-paddle-gpu`：PaddlePaddle **3.0.0 CUDA 11.8**，`is_compiled_with_cuda()=True`，设备 `gpu:0`。

| 页 | CPU | GPU 4060 | 公式数 | 字符 |
|---|---:|---:|---:|---:|
| 114 | 87.5 s | **5.8 s** | 46 | — |
| 118 | 424.8 s | **76.9 s** | 23 | 2658 |

- p114 约 **15×** 加速；
- p118 仍 **76.9 s**，且字符从 3531 降到 2658，仍不达生产阈值 → 保留页图 fallback；
- GPU venv 复用 `.venv-ocr` 的 PaddleOCR/paddlex（`sys.path.append`），因为 PaddleOCR 3.7 尚未装进 GPU venv。

结论：

- 不合并能保住公式数和字符（p114 47 条、p126 46 条），但 **比整页更慢**（多一次布局+裁图）；
- p122 少了 1 个框，但字符更多（合并版 1734 vs 1715）；
- 因此生产默认应是 **整页 pipeline**；p118 异常页单独走整页（424.8 s），不裁剪；
- 若追求速度且能人工复核，再用 batch32+合并（2.7×，但 p118 会丢内容）。

## 8. 下一步

1. 用 GPU 跑 12 页 A2，记录 CDM；
2. 裁公式 bbox 再识别，减少延迟；
3. 只对 `formula` 类版面块调用，不整页；
4. 与 MinerU advanced / OCRFlux 的公式输出对比。
