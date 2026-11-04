# 剩余工作盘点（2026-11-03）

| 项 | 值 |
|---|---|
| 范围 | P0–P3 |
| 结论 | P0/P1/P2 主体完成；剩余集中在 **PTC 原生、K5 希腊、表格 TEDS、人工验证、P3** |
| 先读 | `STATUS.md` / `HANDOFF.md` |

---

## 1. P0 剩余（评测债）

- [ ] 第三模型（Claude/GPT/Qwen）对照；
- [ ] `deepseek-reasoner` 补满 50 轮；
- [ ] 三流 100 条金标；
- [ ] 中文/竖排 VLM OCR；
- [ ] 竖排注文分离；
- [ ] 表格 TEDS；
- [ ] 版权导出拦截测试；
- [ ] 深度金标（每本 2–3 页）。

## 2. P1 剩余

### 检索

- [ ] Qdrant/向量库未使用：BGE 是 npy + GPU 矩阵乘；
- [ ] `socratic-search` 独立服务未做；
- [ ] stream/page 索引冲 0.85；
- [ ] 增量索引/版本切换；
- [ ] 第三模型 critic。

### OCR / 解析

- [x] K5 希腊 OCR：**策略已落地**——服务端只回 citation+页图，`text` 置空（`P1-3c-K5-pageimage.md`）；
- [ ] FTS 希腊分词：希腊词查询目前只能走 BGE，未做原词检索；
- [ ] OCRFlux 推迟（需 16–24 GB 云卡）；
- [ ] Umi-OCR 未起服务；
- [x] K6 Perseus 金标（Paddle 12.8%）；
- [ ] 公式 p118 仍 76.9 s / 质量下降 → 页图；
- [x] ODL 表格 TEDS：**0.437 vs PyMuPDF 0.527**，多行表 ODL 行切分失败 → 不替换（`P1-3d-TEDS.md`）；
- [ ] ODL bbox 字符级准确率未测。

## 3. P2 剩余

- [x] DSH 原生 PTC `run_code`：rc.5 已有 `ptc` preset + `ptc-runtime`，headless 用 `DSH_TOOLS_MODE=ptc`（已实测）；
- [x] `ptc_calc` token：**已验证，−2.2%（计费加权 +6.5%）不达标** → 不默认化（`P2-9-PTC-token.md`）；
- [ ] 人工评分跳过（无 2 名评分者）；
- [ ] 对话层 canary 只在自动评估，未做人评；
- [ ] BKT 参数未标定；
- [ ] `unit_check`/`cite_verify` PTC 门面仍是占位；
- [ ] 大结果未落 artifact。

## 4. P3 剩余

- [x] 复盘 v1：判定/错误分类/归因/复练，留出集 86.7% 过门（`P3-1-review.md`）；
- [x] 竖排章回索引：C1 卷级 7 章 + 卷首尾，覆盖 358/358（`P3-2-vertical-index.md`）；
- [x] 页图/章回浏览：`/browse`（章回列表 + 翻页 + dpi 切换）；
- [x] 竖排篇级切分：7 篇定位到篇名页，卷标题合并篇名（`P3-3-vertical-pian.md`）；
- [x] 篇级泛化：整页带宽扫描，C1 7/7 并修正卷二起点（`P3-4-vertical-scan.md`）；
- [x] 多篇卷：章回小说验证，132 回目段（`P3-5-hui-index.md`）；过切 +6%、未落库；
- [x] 检索接入章回：`book`+`chapter` 过滤、扫描本 `page_only` 回页图（`P3-6-chapter-retrieval.md`）；
- [x] 章回页图进引用卡：turnTail 显示缩略图 + `/browse` 深链（需 GUI 重载插件）；
- [ ] 四大名著全本：已扫 2745/5291 页、切分参数收紧（过切 106→101）；**换书边界晚一回**、后段未扫、未落库；
- [x] 复盘 ≥80% 验收：留出集 86.7%、undetermined 0%。

## 5. 优先级

| 优先级 | 任务 | 理由 |
|---:|---|---|
| ~~P0~~ | ~~原生 PTC preset + token~~ | **已闭**（`P2-9-PTC-token.md`，否定结论） |
| ~~P0~~ | ~~ODL 表格 TEDS 金标~~ | **已闭**（`P1-3d-TEDS.md`，不换） |
| ~~P0~~ | ~~K5 页图策略落地~~ | **已闭**（`P1-3c-K5-pageimage.md`） |
| ~~P0~~ | ~~P3 复盘 v1~~ | **已闭**（`P3-1-review.md`，86.7%） |
| ~~P0~~ | ~~P3 竖排章回索引 / 页图浏览~~ | **已闭**（`P3-2-vertical-index.md`） |
| ~~P0~~ | ~~P3 竖排篇级切分~~ | **已闭**（`P3-3-vertical-pian.md`） |
| 延后 | 人工评分（2 名评分者） | **用户决定推后**：靠个人试用 / 插件开源 / 模型进步替代；文档不得声称"人类验证通过" |
| P1 | 章回小说索引收尾（全 5291 页、书名、过切） | 已有可跑链路，缺打磨 |
| P1 | 人工评分（找 2 人） | 没有它不能声称教学有效 |
| P2 | FTS 希腊分词 + recall 复测 | K5 原词查询目前只能靠 BGE |

## 6. 明确不要做

- 不要再重跑 P0 编目/安全；
- 不要把 silver 文本层当最终金标；
- 不要在没有 token 数据时把 `ptc_calc` 默认化；
- 不要声称“人类评分通过”。
