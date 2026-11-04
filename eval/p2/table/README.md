# eval/p2/table — 表格 TEDS 夹具

用 4 张手工金标表给 ODL / PyMuPDF 打分；结论见 `docs/P1-3d-TEDS.md`。

| 文件 | 作用 |
|---|---|
| `extract_tables.py` | 渲染页图（200 dpi）+ 导出 ODL JSON 表与 PyMuPDF `find_tables()` 到 `out/` |
| `gold/*.html` | 人工转写的金标表（`colspan` 如实标注） |
| `teds.py` | TEDS / TEDS-Struct（Zhang-Shasha 树编辑距离，无第三方依赖） |
| `run_teds.py` | 打分，写 `teds-results.json`，打印逐表明细 |
| `out/`, `pages/` | 生成的中间产物（可删，重跑 `extract_tables.py` 即恢复） |

```powershell
cd eval\p2\table
..\..\..\.venv-bge\Scripts\python.exe extract_tables.py --doc B4 --pages 337,777,780
..\..\..\.venv-bge\Scripts\python.exe extract_tables.py --doc A1 --pages 612
..\..\..\.venv-bge\Scripts\python.exe run_teds.py
```

注意：

- 金标只标"看得清的结构"；A1 p612 是公式表，只计结构分（`text_scored=False`）。
- 一页多表时取与金标最匹配的那张，选中下标写在 `teds-results.json` 里。
- TEDS 不计 `colspan`/`rowspan`：两侧 span 输出都不完整，纳入会重复扣分。
