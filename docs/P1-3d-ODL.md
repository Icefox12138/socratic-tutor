# P1-3d 解析器对照：PyMuPDF vs OpenDataLoader

> **2026-11-03 注**：§5/§6 的"表格 TEDS 未算"已补——4 张金标表结果为 ODL 0.437 / PyMuPDF 0.527，多行表 ODL 会把数据行并成一行。结论不变（默认 PyMuPDF）。详见 `P1-3d-TEDS.md`。

| 项 | 值 |
|---|---|
| 日期 | 2026-11-02 |
| OpenDataLoader | 2.5.17（jar）+ Microsoft OpenJDK 17 |
| 样本 | A1 Princeton 12 页；B4 资本论 12 页 |
| 结果 | ODL 单页边际 0 ms（整本预转换）；整本 11–31 ms/页；PyMuPDF ~20 ms/页 |
| 结论 | **默认仍用 PyMuPDF**；ODL 仅在表格/bbox 有明确收益时启用 |

## 1. 安装

- OpenDataLoader `2.5.17` 为 Java CLI，jar 在 `.venv-ocr\Lib\site-packages\opendataloader_pdf\jar\`；
- 原机 Java 8 不满足（class version 55），下载 Microsoft OpenJDK 17 到
  `D:\Guo-Code\tools\jdk17`（178 MB）；
- 运行时设置 `JAVA_HOME`/`PATH` 后即可用。

## 2. 吞吐

| 文档 | 页数 | ODL 整本转换 | 折算 |
|---|---:|---:|---:|
| A1 Princeton | 673 | 20.9 s | **31 ms/页** |
| B4 资本论 | 995 | 11.1 s | **11 ms/页** |

- 官方称 0.02 s/页（20 ms）；实测 B4 更快、A1 更慢，**不是稳定 20 ms**；
- 12 页抽样里 ODL 首行 20.9 s、其余 0 ms（整本缓存），所以“平均 1744 ms/页”是假象；
- PyMuPDF 按页抽取约 **20 ms/页**，按需抽取更简单。

## 3. 文本量

| 组 | PyMuPDF 平均字符 | ODL 平均字符 |
|---|---:|---:|
| A1 | 951 | **1385** |
| B4 | 738 | 745 |

- A1 文本量 +46%，主要来自 Markdown 结构/表格标记；
- B4 基本一致。

## 4. bbox 覆盖（补充）

用 ODL JSON 的 `bounding box` 与 PyMuPDF text blocks 比较，按 12 页平均：

| 组 | ODL 覆盖 | PyMuPDF 覆盖 |
|---|---:|---:|
| A1 | **37.6%** | 33.7% |
| B4 | **32.1%** | 21.7% |

- ODL 覆盖更高，尤其 B4（+10 个百分点）；
- 但这是“文本块面积/页面积”，**不是字符级 bbox 准确率**；
- 12 页抽样里没有表格页（A1 全文档有 186 个 table，B4 16 个），**表格 TEDS 仍未算**。

## 5. 表格结构抽样

抽样表格页：

- A1 p38–40：ODL Markdown 中 **43 行**表格；
- B4 p777/790：**18 行**表格。

问题：

- A1 表格大量单元格为空/只有图片链接，结构不完整；
- B4 表格有内容，但多行被合并/换行污染；
- **TEDS 未算**：没有表格金标，无法给 0–1 分数。

## 6. 未测/限制

- **表格 TEDS 未测**：需要表格金标/结构标注；
- **bbox 覆盖率未测**：本轮用 markdown 输出，没有解析 bbox；
- 阅读顺序只做了目测，没有逐页标注；
- 只跑 1 次，未统计方差；
- ODL 整本转换对 995 页文档 11 s，可接受，但**按页查询不划算**；
- 依赖 Java 17，部署体积 +178 MB。

## 7. 结论

- 解析器默认：**PyMuPDF**（按页、20 ms、无 JVM）；
- ODL 适合**离线整本转换**后缓存 Markdown/结构，而不是每次查询；
- 若 P1-3d 后续要表格/bbox，先补 TEDS/bbox 金标，再决定是否启用；
- 当前不替换主链路。

## 8. 产物

- `eval/p1/bakeoff/out/opendataloader/{A1,B4}`（Markdown）
- `eval/p1/bakeoff/scorecard-odl.json`
- `eval/p1/bakeoff/scorecard-pymupdf.json`
- `docs/P1-3d-ODL.md`
