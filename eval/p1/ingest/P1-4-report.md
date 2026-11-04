# P1-4 页图按需渲染 + 引用回看

| 项 | 值 |
|---|---|
| 日期 | 2026-10-30 |
| 实现 | `page_render.py`：`render(source, book, page, dpi=150, bbox=None)` |
| 结论 | **PASS**：三源可渲染；冷 16–134 ms；热 0.0 ms；裁剪 50 ms；缓存 2 GB LRU |

## 1. 契约

```python
render(source, book, page, dpi=150, bbox=None) ->
  {path, bytes, cached, ms}
```

- `source ∈ {steadman, library, teubner_conte}`；
- `book` 用 `search.db` 里的原值（Steadman 卷名 / 馆藏 rel 路径 / `conte_aeneis`）；
- `page` 为 1-based，越界抛 `ValueError`；
- `bbox` 为归一化 `[x0,y0,x1,y1]`（0–1），用于公式/表格/引文裁剪。

## 2. 路径解析

| source | 解析 |
|---|---|
| `steadman` | `PDF-new/Steadman/{greek|latin}/{book}.pdf` |
| `library` | `PDF/{book}` |
| `teubner_conte` | `teubner/conte_aeneis.pdf` |

解析只读原文件，不复制、不改名；页图只进缓存。

## 3. 实测

| 场景 | 冷/热 | 耗时 | 大小 |
|---|---|---:|---:|
| Steadman《申辩》p84 | 冷 | 134.4 ms | 353 KB |
| 史记一 p76 | 冷 | 75.1 ms | 386 KB |
| Teubner Conte p50 | 冷 | 15.9 ms | 5.5 KB |
| Steadman p84 裁剪（上半页） | 冷 | 50.1 ms | 105 KB |
| Steadman p84 再取 | **热** | **0.0 ms** | — |

## 4. 缓存

- 目录：`eval/p1/pages/`；键 = `source + sha1(book)[:10] + page + dpi + bbox`；
- 命中直接返回，不打开 PDF；
- 上限 **2 GB**，超限按 `mtime` 从旧到新淘汰（`_evict()`）；
- 当前缓存 1.1 MB（测试样本）；淘汰阈值未在真实规模触发，逻辑留待 P1-5 压测。

## 5. 引用回看接线

`search.db` 的检索结果含 `source / book / page`，直接构造：

```json
{"source":"steadman","book":"platos-apology__apology.04jan25",
 "page":84,"bbox":[0.1,0.1,0.9,0.4],
 "image":"eval/p1/pages/steadman__...__p84_150_0.100...png"}
```

UI 侧只需 `<img src=...>`；S 级引用强制 `page` + 可选 `bbox`，满足“引用回页图”的第一契约。

## 6. 风险与边界

- `book` 来自 DB，不由用户直接输入；若未来开放 URL 参数，必须白名单校验，防路径穿越。
- 页图不预生成；30 万页全量渲染会占 30–60 GB，按需 + LRU 是硬约束。
- 200 dpi 用于 OCR 复核；默认 150 dpi 平衡清晰度与体积。
- 缓存淘汰只按 mtime，未做命中率统计；P1-5 加 `hits/misses` 计数。

## 7. 产物

`page_render.py`、`pages/*.png`、`pages/page-test.json`。

## 8. 下一步

P1-5：质量闸门 + 抽检脚本（引用抽检 100 条、S 级逐条页图、缓存命中率）。
