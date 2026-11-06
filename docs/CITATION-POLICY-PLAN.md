# 语料源引用配置：开发方案（一般化）

| 项 | 值 |
|---|---|
| 日期 | **2026-11-06** |
| 状态 | **M0–M2 已实现**（2026-11-06）：`/v1/policy`、`/v1/channels`、`/v1/policy/reload`；页图根由通道表派生，缺 `page_render` 返回 422；citation 的 `tier` / `tier_estimated` 改为查表。检索与排序仍走 `scope=auto/routed`（`enforced_parts.ranking: false`） |
| 依据 | [CITATION-POLICY.md](CITATION-POLICY.md)（是什么 / 为什么） |
| 目标 | 让"引用谁、从哪取、怎么定位、谁裁决"成为**数据**，且默认配置下行为与今天逐条一致 |

---

## 0. 目标与非目标

**目标**

1. 学科差异不写进代码，只写进规则表；新增学科零代码。
2. 语料源的**接入方式**（本地文件 / RAG 库 / 公共 API / 数据集 / 云存储）不写进代码，只写进通道表；新增通道类型算一次适配器，之后零代码。
3. 同一逻辑源的多副本（本地 + 云端 + 已入库的 RAG 副本）**引用身份唯一**，切换副本不改变 locator。
4. 默认策略与当前实测行为逐条等价（快照回归可证）。
5. 每条引用自证：逻辑源、角色、层级、通道、规则、策略版本。

**非目标（本期不做）**

- 不做配置界面（理由见 CITATION-POLICY §7），只做只读诊断端点。
- 不做自动学科识别，不从 query 猜。
- 不在本期接入新语料源本身（NaturalProofs/TheorIA/Lean 另立项目）。
- 不做云盘读写同步；云通道只作为**只读副本**。

## 1. 一般化模型：四层，逐层收敛

优先级只作用于**逻辑源**；"从哪取"是另一个正交维度。这是整套设计不爆炸的关键。

```
规则(subject × doc_kind)  ──选出──▶  逻辑源（有序）  ──按能力挑──▶  通道  ──▶  字节/文本
      ① 引用优先级                    ② 身份 + 角色 + 层级              ③ 接入方式
```

### 1.1 逻辑源（Source）——引用身份

```
Source = {
  id,                # ag-greenough / wikisource:zh / library / naturalproofs
  tier,              # A 校对文本 | B 原页 | C OCR 文本 | D 机器生成
  role,              # cite | template | verify
  locator_scheme,    # page | mediawiki-rev | cts-urn | edition-page | measure | doi
  content_hash?,     # 有则用于判定"多副本是否同版"
  display
}
```

### 1.2 通道（Channel）——接入方式

```
Channel = {
  source_id,         # 必属于某个逻辑源
  kind,              # local-file | rag-sqlite | public-api | dataset-dir | cloud-object
  address,           # 路径 / DSN / URL / bucket key
  auth_env,          # 只写环境变量名，绝不写值
  capabilities,      # 由 kind 推导，可覆盖
  prefer_when,       # 可选：online | LAN | always
  options            # 限流、超时、缓存策略
}
```

**硬规则：逻辑源的一个 locator 必须在它的任一通道上可解析**，否则该副本不算副本（见 §7 风险 1）。

### 1.3 能力（capability）

| kind | `search` | `page_render` | `verify` | `version` |
|---|---|---|---|---|
| `local-file`（PDF） | ❌ | ✅ | ✅（页内文本） | 文件哈希 |
| `rag-sqlite` | ✅ | ❌（除非另挂原件） | ✅（文本比对） | `chunks.source_version` |
| `public-api`（MediaWiki / CTS） | ✅ | ❌ | ✅（revision 一致） | revision / URN |
| `dataset-dir`（NaturalProofs 等） | ✅（旁路索引） | 视格式 | 视格式 | dataset version |
| `cloud-object`（S3/OSS/网盘） | ❌ | ✅（需先取回） | ✅ | ETag |

**调用方声明所需能力**，解析器只在该能力可达的通道里挑。"检索"和"取页图"天然走不同通道——这正是今天 `RAG 库（检索）+ 本地 PDF（渲染）` 的结构，只是现在被硬编码在 `config.DB` 与 `pages.ROOTS` 里。

### 1.4 规则（Rule）——优先级

```
Rule = {
  when:    {subject?, doc_kind?},   # 首个命中；无条件规则兜底
  cite:    [source_id, ...],        # 有序：优先级就是数组顺序
  fallback:{toward: earlier|later} | [source_id, ...],
  require: {locator: [field...]},   # edition / version / doi
  verify:  [mechanism...],
  weight_profile: string            # 引用命名档，见 §2.4；不直接写数字（内联 weight 仅作例外）
}
```

- 优先级 = `cite` 顺序，**不是 tier 排序**：数学 `[library-pdf(B), wikisource(A)]` 与古典学 `[wikisource(A), library-pdf(B)]` 是同一引擎的两行数据。
- `fallback.toward` 带方向：古典学→更权威校对本；计算机理论→更晚文献。

### 1.5 解析器（Resolver）——三段

```
plan = resolve(subject, doc_kind, need: {search, page_render, verify})
# 1) 规则命中 → 有序逻辑源
# 2) 过滤：该源是否存在具备 need 中能力的通道
# 3) 在剩余源内按通道优先序挑：本机 → 局域网 → 云（可被 prefer_when 覆盖）
```

失败要**可诊断**，不能静默降级：`需要 page_render，但 cite 列表里只有 rag-sqlite 通道` 应返回 422 + 可执行提示，而不是返回无图的结果。

### 1.6 多源并存时的引用优先级（合并与锚点）

`cite` 数组只回答"谁先"，不回答"并存时怎么办"。后者要三件事：

**① 合并模式**（规则级，默认 `tiered`）

| 模式 | 语义 | 后果 |
|---|---|---|
| `tiered` | 高优先源占满 `limit` 才轮到下一源 | 排序纯粹，但可能整份回答只有一个源 |
| `weighted` | 各源分数乘权重后统一排序 | 混合，但**弱源的高分条会压过高源的低分条**，需要权重可解释 |
| `interleave` | 按名次交错（A1, B1, A2, B2…） | 天然多源，但稀释锚点 |

默认 `tiered`：教学场景要的是"这句话出自哪本书第几页"的确定性，不是召回多样性。

**② 锚点资格（anchor eligibility）**

一条回答可以引用多个源，但每条事实句的**锚点只能有一个**，且必须来自该学科 `cite` 列表里、具备该 claim 所需能力的源：

```
citation.role_in_answer = anchor | corroborating
```

- `anchor`：locator 可核，学生据此翻页；每条事实句恰好一个；
- `corroborating`：只作旁证（校对文本、另一 edition），不占锚点席位，缺失不影响可核性。

这条规则由**服务端闸门**强制（沿用 `llm/stream` 的引用硬拦截）：无锚点的事实句改写成"尚未核验"，锚点源不在 `cite` 列表内的引用降级为 `corroborating`。

**③ 冲突与配额**

- 源间冲突时，优先级只决定**谁当锚点**，不决定**谁为真**：冲突必须同时呈现（"教材 p.111 写作 …；Wikisource 校对本作 …"），不得用高 priority 静默压制。
- `quota` 可选：某源至少保留几席（用于"必须给出第二来源"的学科）。
- `tie_break` 默认 `tier → 源内 rank`，不再引入第三种分数。

### 1.7 权重（weight）由学科配置，只作用在名次空间

`weight` 是**用户/学科给定的数字**，不硬编码任何学科特性。但它必须落在 RRF 的倒数名次项上：

```
fused[key] += weight[source] / (RRF_K + rank + 1)      # RRF_K = 60
```

**为什么不能乘原始分数**：两库分数不同量纲——v1 的 `similarity` 是 BM25 量级（实测 `9.4017`），v2 的 `score` 是 0–1（`0.83`），v1 内部还有 FTS 与 BGE 两种尺度。把同一个 `0.6` 乘上去，在 v1 是"压低 9.4 的四成"，在 v2 是"压低 0.83 的四成"，含义不同。名次空间没有这个问题。

三条约束：

1. **同一规则内生效**：`weight` 只对该规则 `cite` 列表内的源有意义，跨规则不比较。
2. **必须有等权基线**：`weight: {…: 1.0}` 即等权；`weight_profile` 用于给一套权重命名（`default` / `classics-strict`…），写进 `policy_version`，否则 R@10 不可复现。
3. **与 tier 冲突时标注**：允许给 `B` 源高权重（教材优先），但响应需带 `weight_overrides_tier: true`，避免"为什么校对文本排在 OCR 之后"的困惑。

**这些数字是示例，不是推荐值。** 在没有 100 问对照之前，默认一律等权；用户可自行在 `policy.yaml` 改。

## 2. 配置方式与形状（推荐）

### 2.0 为什么是文件，且拆成两个

三类输入的性质不同，混在一个文件里迟早出问题：

| 输入 | 变化频率 | 是否机器相关 | 是否可公开 | 归属 |
|---|---|---|---|---|
| 学科 → 源顺序、权重、角色、tier | 低（按学科调一次） | 否 | 是（无路径、无密钥） | `policy.yaml` |
| 源 → 地址（本地路径 / RAG DSN / API URL / bucket） | 中（换盘、加云盘） | **是** | **否**（含个人路径） | `sources.local.yaml` |
| 密钥 | 低 | 是 | 否 | 只写环境变量名 |

所以推荐：

```
policy.yaml          学科/权重/角色/tier —— 可进 git、可分享、跨机器一致
sources.local.yaml   地址与本机凭据名 —— gitignore，永不进公开仓
```

公开仓只发布 `policy.example.yaml`（含学科表，地址留空或写相对示例），用户复制出自己的 `sources.local.yaml`。**不要把地址写进公开仓的示例**：`D:\Guo-Code\library\...` 这类路径对别人无意义，还会泄漏本机结构。

查找顺序（后者覆盖前者）：

1. 内置默认（代码内常量，随版本发布，**等于今天的行为**）；
2. 仓库内 `policy.example.yaml`；
3. 用户 `policy.yaml`：`SOCRATIC_POLICY` 指定 → 否则 `%APPDATA%\socratic-tutor\policy.yaml`；
4. `sources.local.yaml`：同目录，或 `SOCRATIC_SOURCES` 指定；
5. 环境变量（少量扁平项，兼容现有 `SOCRATIC_DB`/`SOCRATIC_LIBRARY`/`SOCRATIC_IMAGE_ONLY_LANGS`）；
6. 请求参数 `?subject=&doc_kind=`（只覆盖"选哪条规则"，**不允许**覆盖权重）。

`SOCRATIC_POLICY=off` 直接回到第 1 层，作为回滚开关。

### 2.1 生效与重载

- 启动时加载 + 校验；**校验失败拒绝启动**，不静默降级。
- 运行中 `POST /v1/policy/reload`（本机回环 + 现有 token 机制）重新读取；
- 采用双缓冲：新配置校验通过才替换，失败则保留上一版，并把错误放进 `/v1/policy` 的 `last_reload_error`；
- `policy_version` 取**合并后配置的内容哈希**前 12 位（`policy_sha`），不手写版本号；
- `/v1/policy` 回显**每个生效值来自哪一层**（`origin: builtin|example|user|env|request`），否则"为什么我的权重没生效"无法排查。

### 2.2 校验与自检

- YAML → JSON Schema 校验（引用完整性、终止回退、`require.locator` 与 `locator_scheme` 兼容、通道指向已定义的源、`auth_env` 只允许变量名）；
- `python scripts/policy_check.py` 打印生效策略 + 解析出的通道 + 每个源的能力，风格对齐现有的 `ragdb_check.py` / `contract_check.py`。

### 2.3 配置形状

```yaml
# policy.yaml —— 可进 git：无本机路径、无密钥；跨机器一致
version: 2026-11-06.4
weight_profiles:                     # 命名档：可比较、可回滚、可 A/B；数字只在这里出现
  equal:           {}                # 基线：全 1.0
  classics-strict: {wikisource: 1.0, cts: 0.8, library-pdf: 0.5}
  textbook-first:  {library-pdf: 1.0, wikisource: 0.4, cts: 0.4}
sources:
  library-pdf:   {tier: B, role: cite, locator_scheme: page}
  wikisource:    {tier: A, role: cite, locator_scheme: mediawiki-rev}
  cts:           {tier: A, role: cite, locator_scheme: cts-urn}
  official-docs: {tier: A, role: cite, locator_scheme: edition-page}
  paper:         {tier: A, role: cite, locator_scheme: doi}
  naturalproofs: {tier: D, role: template}
  theoria:       {tier: D, role: template}
  lean:          {role: verify}
  sympy:         {role: verify}

# 通道（地址）不在这里：见 sources.local.yaml —— 本机路径与凭据名不进 git

rules:
  - when: {subject: classics}
    cite: [wikisource, cts]
    fallback: {toward: earlier}      # 向更权威校对本
    merge: {mode: tiered, corroborate: [library-pdf], tie_break: tier_then_rank}
    weight_profile: classics-strict
  - when: {subject: math}
    cite: [library-pdf]              # 教材优先，即使 tier 是 B
    fallback: {toward: earlier}
    merge: {mode: tiered, quota: {library-pdf: 3}, corroborate: [wikisource, cts]}
    weight_profile: textbook-first
    template: [naturalproofs, theoria]
    verify: [sympy, lean]
  - when: {subject: cs, doc_kind: docs}
    cite: [official-docs]
    require: {locator: [version]}
    verify: [tests]
    merge: {mode: tiered}
  - when: {subject: cs, doc_kind: textbook}
    cite: [library-pdf]
    require: {locator: [edition]}
    fallback: {toward: later}        # 教材滞后 → 更晚文献
    merge: {mode: tiered, corroborate: [paper]}
    weight_profile: textbook-first
  - when: {subject: cs, doc_kind: paper}
    cite: [paper]
    require: {locator: [doi, version_date]}
    merge: {mode: tiered}
  - when: {subject: music}
    cite: [library-pdf]
    require: {locator: [measure]}
    merge: {mode: tiered}
  - when: {}                         # 兜底：等价于今天的行为
    cite: [library-pdf, wikisource, cts]
    merge: {mode: tiered}
```

```yaml
# sources.local.yaml —— gitignore；换机器只改这一个文件
channels:
  # 一本书的三种副本：同一个逻辑源，切副本不改 locator
  - {source: library-pdf, kind: local-file,   address: 'D:\Guo-Code\library\PDF', prefer_when: always}
  - {source: library-pdf, kind: rag-sqlite,   address: 'sqlite:///D:/Guo-Code/rag-build/data/indexes/search.db#library'}
  - {source: library-pdf, kind: cloud-object, address: 's3://backup/books', auth_env: BUCKET_TOKEN, prefer_when: online}
  - {source: wikisource,  kind: public-api,   address: 'https://zh.wikisource.org/w/api.php', options: {rate_limit: 2}}
  - {source: naturalproofs, kind: dataset-dir, address: 'D:\Guo-Code\datasets\naturalproofs'}
  - {source: paper,       kind: public-api,   address: 'https://api.crossref.org', options: {rate_limit: 1}}
```

`SOCRATIC_POLICY=off` 退回内置常量（回滚开关）。

### 2.4 权重用命名档，不散落数字

规则里引用档名；数字只出现在 `weight_profiles`。数字会反复调，档名可比较、可回滚、可 A/B，规则本身也保持可读。未写 `weight_profile` 的规则使用 `equal`。

```yaml
weight_profiles:
  equal:           {}                # 全 1.0，基线
  textbook-first:  {library-pdf: 1.0, wikisource: 0.4}
  classics-strict: {wikisource: 1.0, cts: 0.8, library-pdf: 0.5}
rules:
  - when: {subject: math}
    cite: [library-pdf]
    weight_profile: textbook-first
```

### 2.5 存放位置与运维规则

| 层 | 位置 | 用途 | 进版本库 |
|---:|---|---|---|
| 1 | 代码内常量 | 兜底；`SOCRATIC_POLICY=off` | 是 |
| 2 | 随包 `policy.yaml` | 项目默认学科表，**无路径、无密钥** | 是 |
| 3 | `policy.local.yaml`（源码检出：仓库内；安装版：`%APPDATA%\socratic-tutor\`） | 个人调参、命名档覆盖 | 否 |
| 4 | `sources.local.yaml`（同目录） | 地址与凭据名 | 否 |
| 5 | 环境变量 | 兼容现有 `SOCRATIC_DB` / `SOCRATIC_LIBRARY` / `SOCRATIC_IMAGE_ONLY_LANGS` | — |
| 6 | 请求参数 `?subject=&doc_kind=` | 只覆盖"选哪条规则"，**不覆盖权重** | — |

四条运维规则：

1. **启动即校验**：schema + 引用完整性（每个 id 有定义、`require` 与 scheme 兼容、无循环回退、无明文密钥）；失败**拒绝启动**，不静默降级。
2. **`policy_sha` 用内容哈希**：合并后配置的 SHA-1 前 12 位写进 `citation.policy_version`，不手写版本号（一定会忘记 bump）。
3. **热重载**：`POST /v1/policy/reload`；`SOCRATIC_POLICY_RELOAD=1` 时另按 mtime 自动重载，改权重不必重启 sidecar。
4. **改前先看影响**：`scripts/policy_check.py` 跑 20 条固定查询，打印"改前/改后名次变化"；没有这个对照就调权重，等于盲调。

**不推荐**

| 做法 | 原因 |
|---|---|
| 环境变量传权重矩阵（`SOCRATIC_WEIGHTS="a:1.0,b:0.4;…"`） | 不可读、不可 diff、转义易错 |
| 存进 RAG 数据库 | 策略不是数据：会随库分发、无法单独回滚、要迁移 |
| 存进 DSH 插件配置 | 检索在 sidecar，会出现两个真相源；插件只做展示与透传 |
| 每学科一个环境变量 | 学科是规则表的键，不是进程开关 |

## 3. 契约与诊断

| 端点 | 用途 |
|---|---|
| `GET /v1/policy` | 生效策略全文 + `policy_version` + 每个值的来源层 + `last_reload_error` |
| `POST /v1/policy/reload` | 重新读取并校验；失败保留上一版（双缓冲） |
| `GET /v1/channels` | 每个通道的 `kind`/能力/最近一次探测结果/是否可用（只读，带缓存 TTL） |
| `/v1/search?subject=&doc_kind=` | 可选参数；都不传 = 兜底规则 = 今天的等价行为 |
| citation 新字段 | `role`、`role_in_answer`（`anchor`/`corroborating`）、`tier`（真实值）、`tier_estimated`、`channel`、`locator_scheme`、`rule_id`、`policy_version` |

`/v1/channels` 是"为什么选它"的答案载体，也是将来配置界面的唯一数据源——先有它，再谈 UI。

## 4. 元数据与副本判定

| 需要 | v2 | v1 |
|---|---|---|
| `doc_kind` | 无（暂放 `metadata_json`） | 无 documents 表，需旁表 `book_meta` 或路径前缀映射 |
| `edition` | `documents.edition` ✅ | ❌ |
| `version` | `chunks.source_version` ✅ | ❌ |
| 副本同版判定 | 新增 `documents.content_hash` | 旁表字段 |

## 5. 里程碑

| 里程碑 | 内容 | 行为变化 |
|---|---|---|
| **M0 骨架** | policy/channel 结构 + loader + 校验器 + `/v1/policy`、`/v1/channels` + citation 新字段（值取自现有常量/配置） | 无 |
| **M1 通道收敛** | 把 `config.DB`、`pages.ROOTS` 改造成"内置通道表"；能力不足时返回 422 而非静默降级 | 无（等价） |
| **M2 tier 真实化** | v2 按 source 映射；v1 按"有无校对层"给 B/C | 无（不改排序） |
| **M3 路由表化** | `federated._route` 关键词表搬进规则；`routed` 退化为 `all` 特例 | 无（等价）；顺带修 `Ἰλιάς` |
| **M4 合并与锚点** | `scope=all` 按 `merge.mode` 合并（默认 `tiered`）+ 锚点资格闸门 + `role_in_answer`；重跑 100 问 / 130 题 | **有** |
| **M5 元数据补全** | `doc_kind` 标注（801 本）、v1 旁表、按 `doc_kind` 选规则、云副本接入 | 无（新增能力） |

M0–M3 是纯重构 + 契约补齐，用快照证明零行为变化；M4 才可能动数字。

## 6. 验收标准

| 里程碑 | 验收 |
|---|---|
| M0 | 264 测试全绿；`/v1/policy`、`/v1/channels` 均 200；10 个坏配置样例全部拒绝（缺源、空 `cite`、`require` 与 scheme 不兼容、循环回退、`role=template` 带 locator、通道指向不存在的源、密钥写成明文） |
| M1 | 同一逻辑源的两个通道产出**同一 locator**；能力不足返回 422 且提示可执行；离线时云通道被跳过 |
| M2 | 20 条固定查询快照逐条一致，仅新增字段有差异 |
| M3 | `routed`/`all` 默认行为快照一致；`Ἰλιάς` 命中 v2 |
| M4 | 100 问 R@10、130 题 R@5/R@1 记录在案；R@10 下降 > 1 点则权重回滚为等权。另需三条断言：每条事实句**恰好一个** `anchor`；`anchor` 必来自该学科 `cite` 列表；源间冲突时两说并存、未被静默压制。权重改动必须附 `weight_profile` 与等权基线对比 |
| M5 | `doc_kind` 覆盖率报告 + 30 本抽样人工核对 |

**核心保障是等价性回归**：风险不是"做得不好"，而是"悄悄改变了已有排序"。

## 7. 风险与回滚

| # | 风险 | 处理 |
|---:|---|---|
| 1 | **副本漂移**：本地与云副本被替换/重新 OCR，页码对不上 | 副本必须 `content_hash` 一致才允许互替；不一致即视为**不同 edition**，各自独立 `source_id`。这是希腊 Bacchae 页号问题的另一种形态 |
| 2 | **重复索引**：同一本书既在 v1 又在 v2，同一条 claim 出现两次 | 逻辑源身份唯一；跨库合并时按 `document_id` 去重 |
| 3 | 密钥泄漏 | `auth_env` 只写变量名；启动校验拒绝 `policy.yaml` 里出现疑似 token 的字面量 |
| 4 | 配置写错导致全库排序异常 | 加载即校验，失败优于静默降级 |
| 5 | 评估不可比 | `policy_version` 写进 `eval/*/RESULTS*` |
| 6 | 云通道慢/断网 | `prefer_when` + 超时 + 缓存；只读副本，绝不写回 |
| 7 | 回滚 | `policy.yaml` 单文件 + `SOCRATIC_POLICY=off`；无数据库迁移 |
| 8 | **多源并存时高优先级静默压制**：低优先级源给出的才是对的，但因为"它是二号源"被丢掉 | 优先级只决定**锚点资格**，不决定**真值**；同条 claim 的源间分歧必须双呈现；M4 明确断言 |
| 9 | 合并模式配错：`tiered` 让整份回答只有一个源，`weighted` 又让弱源高分条压过锚点 | 默认 `tiered`；`weighted` 只在有 eval 支撑的学科启用；`tie_break` 固定 `tier → 源内 rank`，不引入第三种分数 |
| 10 | **权重乘在原始分数上**：两库量纲不同（v1 `similarity` 9.4 / v2 `score` 0.83），同一个 0.6 在不同库语义不同 | 权重只作用于 RRF 名次项 `w/(k+rank+1)`；禁止对 `similarity`/`score` 直接加权 |
| 11 | 用户改了权重但没留下基线，导致 R@10 不可复现 | `weight_profile` 命名 + 写入 `policy_version`；等权（全 1.0）必须可一键回到 |

## 8. 工作量（单人粗估）

| 里程碑 | 估计 |
|---|---|
| M0 | 1 天 |
| M1 | 1.5 天（含通道抽象 + 能力网关） |
| M2 | 1 天 |
| M3 | 1 天 |
| M4 | 1–2 天（含重跑） |
| M5 | 3–4 天（主要成本是 801 本 `doc_kind` 标注与云副本接入） |

## 9. 为什么这是一般化，而不是给每个学科/每种存储写死一套

| 新增需求 | 代价 |
|---|---|
| 新学科 | 规则表加一行，零代码 |
| 新逻辑源 | `sources` 加一条，零代码 |
| 同一本书换存储（本地→云盘→NAS） | `channels` 改地址，**locator 与优先级不变** |
| 新接入类型（WebDAV、Git LFS、MCP 文件服务） | 新增一个 `kind` 适配器，通道表复用 |
| 新 locator 单位（小节、DOI、行号） | 新增 `locator_scheme` 实现，规则表复用 |
| 新裁决器 | `verify` 机制加一项 |

反面：按"每学科一个函数 + 每种存储一个分支"实现，上面每一行都要改代码 + 改测试——这正是现状（`_route` 的 `_V2_WORK` 表、`pages.ROOTS` 的三个硬编码根）已经证明不可维护的形态。
