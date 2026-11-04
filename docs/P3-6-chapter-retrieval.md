# P3-6 检索接入章回索引

| 项 | 值 |
|---|---|
| 日期 | **2026-11-03** |
| 改动 | `kb_search` 支持 `book` + `chapter`；新增 `/v1/chapter` 与 `chapter_lookup` 工具 |
| 行为 | 有文本层的书 → 章回范围内检索；扫描本 → **直接返回该章页图** |
| 测试 | sidecar **118/118**（新增 12 条） |

---

## 1. 结论

索引不再只是浏览用的旁支：检索能按"卷3 / 第7回 / 标题片段"把范围收窄，收到页码或页图。

| 场景 | 返回 |
|---|---|
| 书有 chunks（马列/哲学等） | 在该章回页码窗口内做 FTS/BGE+rerank，结果带 `chapter` 元信息 |
| 扫描本（史记/三国志/四大名著） | `mode: "page_only"`，返回该章回的逐页页图 URL，`results` 为空 |
| 给了 `page` 而非章回 | `/v1/chapter` 反查该页属于哪一章 |

## 2. 为什么必须分两条路

馆藏 163 本有文本层（167,192 chunks），但**史记、三国志、四大名著都是纯扫描、0 字符**——它们本来就不在 chunk 索引里。硬要"章回内文本检索"没有文本可搜，所以扫描本只能给页图；这也正是项目既定的"引用回页图"策略。

## 3. 接口

```
GET /v1/chapter?book=<书键>&q=卷3            -> 章回 + 页码范围 + 每页页图 + prev/next
GET /v1/chapter?book=<书键>&page=50          -> 该页所在章回
GET /v1/search?q=...&book=<书键>&chapter=卷3 -> 章回内检索（或 page_only）
```

`kb_search` 新增 `book` / `chapter` 两个可选参数；新工具 `chapter_lookup` 直接调 `/v1/chapter`。`prev`/`next` 只在同层级之间走（卷不会跳到自己的篇）。

## 4. 端到端

```
book: ...史记.一.卷一至卷七...pdf chapters: 15
chapter: 卷3 殷本紀第三 p109-128 pages: 20 next: 卷4 周本紀第四
page 50 -> 五帝本紀第一
search mode: page_only results: 0 pages: 20 chapter: 卷3 殷本紀第三
first page image: 311892 bytes
plain search: bge+rerank results: 8     # 不带 book 的普通检索不受影响
OK
```

复现：`python eval/p3/chapter_check.py`（sidecar 在 :8765）。

## 5. 章回匹配

`toc.find` 支持：`卷3`、`第7回`、纯序号、标题片段；简繁差异用 50 字对照表兜住（`紀→纪`、`傳→传`…），否则用户打"夏本纪"匹配不到 OCR 出来的"夏本紀"。同级多条命中取层级更深的那条（篇优先于卷）。

## 6. 测试

- `toc.at/find`：7 条（层级、页码反查、简繁、序号、未命中）；
- `search._range/_page_results`：5 条（章回窗口、整本、未知书、未知章回、页图列表）；
- 端到端脚本另计，不进单测。

## 7. 扫描本页图进引用卡（B）

§page_only§ 的检索现在会写一条**章回级引用**（§lang="page"§、§snippet§ 为空、locator 形如
"01001…史记.一 卷3 殷本紀第三 p.109–128"），turnTail 卡片据此渲染：

| 元素 | 行为 |
|---|---|
| 标题行 | 章回 locator（含页码范围） |
| 说明 | "扫描本：章回页图" |
| 缩略图 | 首页页图，点击放大 |
| 链接 | "打开章回 ↗" → §/browse?book=<书键>&page=<起始页>§，浏览页自动定位 |

实测：§/v1/citations/p3-chapter§ 返回 1 条 §lang="page"§，locator 含 §p.109–128§，§/browse§ 深链 200。

注意：§client.js§ 属 DSH 客户端插件，**要 GUI 重新加载插件 bundle 才生效**（重启 DSH，或在本 checkout 跑 §pnpm run dev:web§）；服务端行为已即时生效。

## 8. 限制

- 扫描本**章回内无法做文本检索**，这是数据决定的，不是实现取舍；
- 章回索引目前只有 C1《史记》一入库；三国志/四大名著的索引还停在 JSON（半本/未落库）；
- 章回匹配是子串与序号规则，不做模糊纠错（"夏本記"打错字匹配不到）；
- `page_only` 一次返回整章页图 URL（史记最长 72 页），前端要按需加载。
