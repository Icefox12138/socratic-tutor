# 金标目录（bake-off 用）

结构：

```
gold/
  C1/p<page>.txt    # 史记竖排：人工转写（列序 + 注文用【注】标出）
  B2/p<page>.txt    # 理想国：正文，脚注用 [^n] 标出
  K5/p<page>.txt    # Loeb 希腊：保留 polytonic
  K6/p<page>.txt    # Loeb 拉丁：保留原拼写
  A2/p<page>.txt    # 李尚志：正文 + 公式行（LaTeX 可另存 .tex）
```

要求：

- 每页一个文件，UTF-8；
- 只转写该页**正文**；页眉/页码可省；
- 竖排：按“右→左、上→下”转写；双行注用 `【注】` 前缀另起一行；
- 希腊：保留重音/气号；拉丁：保留 u/v、ae/æ 原形；
- 公式：能写 LaTeX 就写 `$...$`，不能写就保留原符号。

有了金标后，脚本会自动算：

- CER（归一化编辑距离）；
- 希腊变音符召回（U+1F00–1FFF）；
- 其余手动项（列序、注文错分、公式 CDM、表格 TEDS）仍需人工填 `scorecard.md`。

页号取自 `sample-manifest.json` 的窗口，每 12 页等距抽样；跑一次 `run_bakeoff.py` 后看 `scorecard.json` 里的 `page` 字段即可。
