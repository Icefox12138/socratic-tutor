# 引用策略（citation policy）：角色、层级与分科默认

| 项 | 值 |
|---|---|
| 日期 | **2026-11-06** |
| 状态 | **设计稿，未实现**；实现前行为不变 |
| 范围 | sidecar 服务路径（`/v1/search`、`/v1/chunks`、`/v1/verify`）+ citation 契约 |
| 前置 | [RAG-DB-SCHEMA.md](RAG-DB-SCHEMA.md)（v1）、[RAG-DB-SCHEMA-V2.md](RAG-DB-SCHEMA-V2.md)（v2） |

---

## 0. 一句话

把"**引用谁**"和"**跟谁核对**"分开：前者必须产出学生能翻开的 locator；后者是裁决器，只产出"已验证 / 未验证"，不产出 locator。

分科差异真实存在，但它的正确投影是**可信度层级（tier）**与**排序**，不是"学科偏好"。学科只决定 tier 怎么排。

## 1. 三个角色（role）

同一个源在不同用途下角色不同，**角色与层级正交**：

| role | 产出 | 进 citation | 典型 |
|---|---|---|---|
| `cite` | locator（`p.111` / Wikisource rev / CTS URN） | ✅ | 教材页、校对文本 |
| `template` | 无 | ❌ 只能作为写作参考 | [NaturalProofs](https://datasets-benchmarks-proceedings.neurips.cc/paper/2021/file/d9d4f495e875a2e075a1a4a6e1b9770f-Paper-round1.pdf)（定理陈述 + 自然语言证明，源自 ProofWiki）、[TheorIA](https://theoria-dataset.github.io/theoria-dataset/)（物理方程与推导链） |
| `verify` | `verified` / `unverified` + 证据 | ❌ | SymPy/SciPy/pint、Wolfram Engine、Lean/Mathlib |

三条硬规则：

1. **`template` 永远不能变成引用**。它回答的是"这类证明通常怎么组织"，无法支撑"这本书第几页这么说"。
2. **`verify` 不改写引用**。教材与 Lean 冲突时，回答必须**同时呈现**（"教材 p.111 写作 …；按 Lean 该陈述不成立"），不能静默偏向教材页——教材印错是真实存在的失效模式。
3. Lean 的定理名是**另一种 locator scheme**。若将来要引 Lean，必须作为新 scheme 显式登记并支持 `verify`，不能借用页/URN 的槽位。

## 2. 可信度层级（tier）

| tier | 定义 | 引用形态 |
|---|---|---|
| `A` | 有校对层的文本（Wikisource revision、CTS、出版社电子版） | 文本 + `url` |
| `B` | 原页渲染（自扫 PDF 页图；可核，但无校对层） | 页图 + `locator` |
| `C` | 机器 OCR 文本 | `locator`，**文本需回落页图** |
| `D` | 机器生成（翻译/合成） | 默认不可引 |

tier 只决定**同一 claim 有多个候选时谁排前**；可引性由 `role` 决定。`C` 级不是"不能引"，而是"引了要能翻到图"——这正是 [policy.py](../sidecar/app/policy.py) 现在对希腊文做的事。

**多源并存时**：tier 与 `cite` 顺序只决定**谁当锚点**（每条事实句恰好一个，`role_in_answer=anchor`），**不决定谁为真**；源间分歧必须双呈现，不得以优先级压制。合并模式与锚点闸门见 [CITATION-POLICY-PLAN.md §1.6](CITATION-POLICY-PLAN.md)。

## 3. 分科默认表

| 学科 | 引用首选 | 回退 | 结构范本 | 裁决 |
|---|---|---|---|---|
| 古典学 / 文言 | 开放校对文本 `A` | 原页 `B` | — | 词法/lemma 通道（`/v1/grep`、`/v1/lemma`） |
| 数学 / 物理 | **教材原页 `B`** | 开放校对文本 `A` | NaturalProofs、TheorIA | SymPy/SciPy、Wolfram Engine、Lean/Mathlib |
| 计算机 · 工程层 | 官方文档原页 `A`/`B`（**locator 带版本**） | 书 `B` | — | 运行代码 / 测试 |
| 计算机 · 理论层 | 教材原页 `B`（**locator 带版次**） | 论文（教材未覆盖时） | — | 证明、Lean/Mathlib |
| 计算机 · 前沿层 | 论文（**DOI + 版本日期**） | — | — | 复现 / 文献对照 |
| 乐理 | 谱面或教材原页 `B`（小节级 locator） | — | — | 无 |

数学物理这一行值得展开，因为它是"看起来该反过来"的那一行：

- **教材优先**：教材是系统的、有习题与推导顺序、且**就是学生手里那一本**；OpenStax / Wikibooks / Wikimedia 提供的是不成体系的通识片段，做背景可以，做引用锚会把"可核"变成"可查但不完整"。
- **开放文本只作回退**：命中不足或教材无覆盖时用，且必须标注它是背景件。
- **裁决独立**：Python 科学计算栈 / Wolfram Engine / Lean-Mathlib 决定"这句话算对了没有"，输出是 `verified` 标记与证据摘要，**不进排序**。问"角动量定义"时第一名仍应是教材页，而不是 Mathlib 的 `AngularMomentum`。

## 3b. 计算机为什么必须再分层

同一个"计算机"里，三层的变化轴完全不同，用一行表达会掩盖真正的失效模式：

| 层 | 典型内容 | 变的是什么 | 失效模式 | locator 必须带 | 裁决 |
|---|---|---|---|---|---|
| 工程 / 规范 | 语言语义、API、工具链、官方文档 | **事实本身** | 旧文档 = 错 | `version` | 跑代码 / 测试 |
| 理论 / 教材 | 算法、复杂度、编译原理、OS 抽象、网络原理、导论、组成原理 | **页码 / 版次**，不是结论 | 版次错 → 页码对不上 | `edition`（依赖 ISA 的陈述再加 ISA 版本） | 证明、Lean/Mathlib |
| 前沿 | "当前最好的矩阵乘法指数"、最新最优算法 | **结论本身** | 结论被新结果取代 | DOI / arXiv 版本日期 | 复现 / 文献对照 |

关键判断：**理论层的"时效"其实是版次问题，不是过期问题。** `O(n log n)` 比较排序下界、Dijkstra 的正确性不随版本变；但 CLRS 3e 与 4e 的页码、习题编号不同——这与古典学里 Bacchae 页号 16 vs 44 对不上是同一结构（见 `HANDOFF-2026-11-06-v1-federated.md` §1a）。要的是**版次锁定 + 跨版映射**，不是调整优先级。

因此策略的匹配键不能只是 `subject`，必须是 **`subject × doc_kind`**（`textbook | reference | paper | docs | notes`）。各层的回退方向也不同：

- 古典学：教材 → **更权威的校对文本**；
- 计算机理论：教材 → **更晚的文献**（教材必然滞后于前沿）。

两者不能共用一个无方向的 `fallback` 字段。

## 4. 配置形状（草案）

```yaml
# policy.yaml — 与 sidecar 一起发布；SOCRATIC_POLICY 可指向覆盖文件
version: 2026-11-06.2
sources:
  wikisource:    {tier: A, role: cite}
  cts:           {tier: A, role: cite}
  library-pdf:   {tier: B, role: cite}          # 原页渲染，可核无校对层
  ocr-text:      {tier: C, role: cite}          # 引用需回落页图
  official-docs: {tier: A, role: cite, locator: {requires: [version]}}
  paper:         {tier: A, role: cite, locator: {requires: [doi, version_date]}}
  naturalproofs: {tier: D, role: template}
  theoria:       {tier: D, role: template}
  sympy:         {role: verify}
  wolfram:       {role: verify}
  lean:          {role: verify}
subjects:
  classics:
    cite:     [wikisource, cts]
    fallback: [library-pdf]
  math:
    cite:     [library-pdf]                     # 教材优先，即使 tier 是 B
    fallback: [wikisource, cts]
    template: [naturalproofs, theoria]
    verify:   [sympy, wolfram, lean]
  cs:
    # 匹配键是 subject × doc_kind；doc_kind 是文档级元数据，入库时标注
    - when: {doc_kind: docs}                    # 工程层：版本即事实
      cite: [official-docs]
      fallback: [library-pdf]
      verify: [tests]
    - when: {doc_kind: textbook}                # 理论层：版次即定位
      cite: [library-pdf]
      locator: {requires: [edition]}
      fallback: [paper]                         # 教材滞后于前沿，回退方向相反
      verify: [lean]
    - when: {doc_kind: paper}                   # 前沿层：结论本身会变
      cite: [paper]
      verify: [reproduce]
  music:
    cite: [library-pdf]
    locator: {requires: [measure]}              # 小节级单位，见 §8.4
fallback: {cite: [wikisource, cts, library-pdf, ocr-text]}
```

- 学科默认可被单次请求覆盖（`?subject=math`），但**不允许**按 query 关键词猜学科（见 §8.2）。
- 默认表必须与当前实测行为等价：希腊 → 页图、中国史 → v2、其余 → v1。

## 5. 与现有代码的映射

| 现在 | 位置 | 改法 |
|---|---|---|
| `citation.tier` 恒为 `"A"`（v2）/`"unknown"`（v1） | [catalog.py:118](../sidecar/app/catalog.py#L118)、[search.py:488](../sidecar/app/search.py#L488) | 按 source 计算真实 tier；回传 `role` 与 `policy_version` |
| `scope=routed` 用关键词表选源 | [federated.py:33](../sidecar/app/federated.py#L33) | 表搬进 policy；`routed` 退化为 `all` 的特例（两库都查 + tier 加权 + 命中不足才回退） |
| `image_only_langs` 按语言强制页图 | [policy.py](../sidecar/app/policy.py) | 成为 policy 的一个字段（langs → tier `C` 强制回落页图） |
| `scope=all` 无权重 RRF | [federated.py](../sidecar/app/federated.py) | 按 tier 加权合并 |
| 无 `doc_kind`；v1 无 documents 表 | v2 `documents`（已有 `edition`、`chunks.source_version`、`chunks.quality`） | 入库时标 `doc_kind`（暂放 `metadata_json`）；v1 需旁表或路径前缀映射 |

顺带修掉 `_V2_WORK` 的已知缺陷：它只匹配 `iliad` 等拉丁转写，`Ἰλιάς` 不命中。

## 6. 生效与版本化

- 每个结果带 `citation.policy_version`、`citation.tier`、`citation.role` 与命中的规则名；
- **改排序 = 改评估基线**：v1 的 0.80–0.82 / 跨语言 0.667、v2 的 R@5 0.977 都是在固定排序下测的，任何加权改动必须重跑并写入 `eval/v1/RESULTS.md` / `eval/public/RESULTS-project.md`，否则数字不可比；
- 默认策略等价性优先于"更聪明"的默认值。

## 7. 为什么暂不做配置界面

1. 单机单读者，政策一年改两次；YAML 比界面便宜且可进版本库、可 diff、可评审。
2. 界面会把"调矩阵"变成默认动作，而证据量撑不住：希腊文只有 12 道题，单题波动就是 8 个百分点。没有 eval 支撑的表，调得越顺手越危险。
3. 用户真正遇到的问题是"**为什么选了这个源**"，不是"让我拖动排序"。所以先做**只读诊断**（每条结果回传命中规则），界面留到有多库、多用户需求时再谈。

## 8. 已知限制

1. **tier 需要逐源标定**：v1 的 167k chunks OCR 质量不一，`B`/`C` 只能按"是否有校对层"粗分。
2. **学科无法从 query 稳定推断**：显式传 `subject`，或由会话 `concept` 决定；不要用关键词表（现有 `_route` 已经是反例）。
3. **版本时效不是 tier**：CS 文档 2019 vs 2024 是"对/错"，不是"高/低"。需要 locator 带版本，并在 `verify` 时拒绝旧版本。
4. **乐理缺 locator scheme**：当前 v1/v2 都没有小节级引用单位，页图无法承载"第 3 小节"。
5. **`template` 源缺入库路径**：NaturalProofs/TheorIA 若要真正使用，需要 adapter 与"不产 citation"的独立索引通道，不要塞进 v1/v2 的 chunks 表。
6. **`doc_kind` 必须在入库时标注**，不能从正文猜：猜错会把"文档层"的版本要求套到教材上（或反之），且无从自证。v2 已有 `documents.edition`、`chunks.source_version`、`chunks.quality`，只缺显式 `doc_kind`（暂只能放 `metadata_json`）。
7. **v1 没有 documents 表**：只有 `chunks`（book/page/lang/visibility），`doc_kind` 与 `edition` 无处存放，只能靠路径前缀映射或新增旁表；这是 v1 做不了分层策略的结构性原因。
8. **同一主题的"教材 vs 论文"回退方向随学科相反**（古典学→更权威校对文本；计算机理论→更晚文献），因此 `fallback` 必须带方向，不能做成一个全局列表。

## 9. 最小可行路径

实施细节（逻辑源 × 通道的分层、能力矩阵、合并与锚点、配置方式、里程碑与回归验收）见 [CITATION-POLICY-PLAN.md](CITATION-POLICY-PLAN.md)。

| 步 | 内容 | 风险 | 影响评估 |
|---:|---|---|---|
| 1 | `tier` 真实化 + 回传 `role`/`policy_version`（**不改排序**） | 低 | 不动基线 |
| 2 | routing 表抽成配置，默认值与今天等价 | 低 | 行为不变 |
| 3 | `scope=all` 按 tier 加权，重跑 100 问 | 中 | 必须重测并记录 |

第 1、2 步是纯重构 + 契约补齐；第 3 步才可能改动检索数字，单独评估。
