# 资产来源登记

任何进仓库的图片/示例数据在此登记一行。`scripts/publish_lint.py --scope source` 会对照本文件：
没有登记 → 红；登记为 ⛔ → 红。

| 文件 | 类型 | 来源 | 许可 | 状态 |
|---|---|---|---|---|
| `plugin-socratic/dsh-embedded.png` | 截图 | DSH GUI + 教学台面板，引用 `samples/` 合成语料 | MIT（本项目） | ✅ |
| `plugin-socratic/dsh-page-image.png` | 截图 | 页图弹窗，显示合成横排页（`samples/`） | MIT（本项目） | ✅ |
| `plugin-socratic/dsh-per-turn.png` | 截图 | 每轮引用卡（`synthetic-book.pdf p.2`） | MIT（本项目） | ✅ |
| `sidecar/ui/screenshot.png` | 截图 | 本机 UI 空状态，无书页 | MIT（本项目） | ✅ |
| `sidecar/ui/screenshot2.png` | 截图 | 本机 UI 空状态，无书页 | MIT（本项目） | ✅ |
| `sidecar/ui/screenshot-demo.png` | 截图 | 无头浏览器对 `samples/` 合成语料的真实检索（`?q=极限`） | MIT（本项目） | ✅ |
| `sidecar/ui/screenshot-demo2.png` | 截图 | 同上，`?q=樣本`（竖排页引用） | MIT（本项目） | ✅ |
| `market/icon.png` | 图标 | 自制（`eval/p3/make_market_icon.py`） | MIT（本项目） | ✅ |
| `packages/classics-index/examples/*.jsonl` | 示例数据 | 自制（合成书 12 页，无真实文本） | MIT（本项目） | ✅ |
| `docs/assets/public/classics-index-demo.png` | 示意图 | 用上述示例数据渲染（`eval/p3/make_demo_card.py`） | MIT（本项目） | ✅ |
| `docs/assets/public/samples/formula.png` | 书页样本 | 自制（`eval/p3/make_sample_pages.py`，公式为通用形式） | MIT（本项目） | ✅ |
| `docs/assets/public/samples/zh-horizontal.png` | 书页样本 | 自制（同上，文字自撰） | MIT（本项目） | ✅ |
| `docs/assets/public/samples/zh-vertical.png` | 书页样本 | 自制（同上，繁体竖排 + 双行注） | MIT（本项目） | ✅ |
| `docs/assets/public/samples/latin.png` | 书页样本 | 自制（同上；仅 "Ars longa" 为公版格言） | MIT（本项目） | ✅ |
| `docs/assets/public/samples/greek.png` | 书页样本 | 自制（同上；首句为亚里士多德公版引文） | MIT（本项目） | ✅ |

标记：✅ 可发布；⛔ 阻塞源码开源；🟡 待补许可。
