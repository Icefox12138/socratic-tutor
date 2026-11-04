# 开源发布计划（双重开源）

| 项 | 值 |
|---|---|
| 日期 | **2026-11-03（按双轨标准修订）** |
| 标准 | **双重开源**：GitHub 源码级开源（MIT）+ PyPI/npm/DSH 市场发包，两条轨道都到位才算发布 |
| 当前 | 产物轨 **PUBLISH READY**；源码轨 **5 张图阻塞**（均为版权书页截图） |
| 门禁 | 单测 125/18/6/8 · 契约探针 9 项 · `publish_lint` 双 scope |

---

## 0. 「双重开源」是什么

同一个单元必须同时满足两条轨道：

| 轨道 | 交付物 | 面向 | 完成判据 |
|---|---|---|---|
| **源码轨** | GitHub 公开仓库（MIT） | 想改、想审、想集成的人 | 仓库可 clone、CI 绿、历史干净、资产清白 |
| **产物轨** | PyPI / npm / DSH 市场条目 | 只想装来用的人 | registry 可安装、市场页可点、版本与 tag 对应 |

只有产物 → 叫"发了个包"，不叫开源（别人无法审、无法改、无法复现）；
只有源码 → 叫"给了个仓库"，不叫可安装（用户得自己读 README 搞环境）。

### 四个单元的完成度

| 单元 | 源码轨 | 产物轨 | 市场条目 | 备注 |
|---|---|---|---|---|
| `classics-index` | ✅ 已公开 | ✅ PyPI 0.1.1 | — | — |
| `socratic-mcp` | ✅ 同上 | ✅ PyPI 0.1.1 | — | — |
| `dsh-socratic` | ✅ 同上 | ✅ npm 0.2.1 | ✅ 索引已托管 | — |
| `sidecar` | 🟡 同上 | ⬜ 无 Dockerfile | — | 需参数化 + 镜像 |

## 1. 三个批次（每批都走双轨）

### 批次 1：索引器（1–2 天）

- **源码轨**：仓库公开；LICENSE(MIT)；CI；**删除 5 张版权截图**；历史清理（`pre-step.log` 等）；
- **产物轨**：`classics-index` 发 PyPI（TestPyPI → 正式）；
- 验收：`git clone` 能跑测试；`pip install classics-index` 能用示例数据出 `toc.json`；`publish_lint --scope source` 全绿。

### 批次 2：接缝（2–3 天）

- `socratic-mcp` 发 PyPI；`scripts/contract_check.py` 作为它的验收工具；
- `dsh-socratic` 发 npm：`files` 白名单已加；**本机已可用 DSH 自带 node+pnpm 打包并验装**（见 §7），只剩 `publish` 一步；
- 市场条目：需要**公版截图**（见 §3）、安装说明（写明"需要配套 sidecar"）、`engines.dsh` 范围；
- 验收：干净机器装 MCP server → 指向任意符合契约的 sidecar → `contract_check` 通过。

### 批次 3：服务与示例（3–5 天）

- sidecar 参数化（`SOCRATIC_ROOT`）+ `Dockerfile`（**镜像不带书**）+ compose 一份；
- `ingest` 包成 CLI（`socratic-ingest`），补上"自带书库"的 onboarding；
- 验收：`docker run -v /books:/books` + `contract_check` 通过。

## 2. 不发布的东西（数据）

| 对象 | 原因 |
|---|---|
| 书库 27.46 GB / 361,862 页 | 点校本/后 1929 Loeb/影印本的版权 |
| `bge-vectors.npy`（303 MB） | 版权文本的向量化 = 衍生数据 |
| `search.db` / `state.db` | 含原文与会话 |
| `eval/` 实验脚本 | 硬编码路径、依赖私有语料 |
| 评分包 P2-6 | 含版权摘录 |
| BGE / reranker 权重 | 第三方许可，不重分发 |

**代码与数据分家**：仓库公开 = 全部内容按 MIT 授权；一张书页截图混进去，就等于把 MIT 扩到了那张图上。

## 3. 截图与资产（本轮重点）

### 陈童（东华理工大学）讲义能不能用？

本机有 9 份讲义（`D:\Guo-Code\PDF\物理\...`）。`量子力学新讲` 的版权页写得很明确：

> Copyright © 2021 陈童 … 作者本人保有**所有版权**；读者可在其网站自由下载、也可**私自传播**，
> 但**仅限用于学习或教学等非商业用途**，禁止以本讲义部分或全部获利。

| 用法 | 判定 |
|---|---|
| 自己在本地读、自己看 | ✅ |
| 放进公开仓库当 README 截图 | ❌ **超出「私自传播」**，且会被 MIT 覆盖 |
| 取得作者书面许可后使用 | ✅（在 `docs/assets/SOURCES.md` 附许可原文） |

所以：**陈童讲义不是「公版」，不能直接替换截图**。它是"免费下载但版权保留"的教材，与点校本在许可上属于同一类风险。

### 三条可行路径（按优先级）

1. **自制渲染（首选）**：用 `classics-index` 的合成示例数据渲染一张"索引输出"卡片 / 终端截图——零第三方权利，天然 MIT；
2. **作者许可**：按版权页邮箱联系，拿到书面同意后使用，并在 SOURCES.md 记录；
3. **真公版**：1929 年前印本且扫描件标注 Public Domain（Wikimedia Commons / Internet Archive），记录来源与年份。

### 当前阻塞的 5 张图

`publish_lint --scope source` 现在精确报出：

```
FAIL plugin-socratic/dsh-embedded.png    (blocked: copyrighted)
FAIL plugin-socratic/dsh-k5-page.png     (blocked: copyrighted)
FAIL plugin-socratic/dsh-per-turn.png    (blocked: copyrighted)
FAIL sidecar/ui/screenshot-demo.png      (blocked: copyrighted)
FAIL sidecar/ui/screenshot-demo2.png     (blocked: copyrighted)
NOT READY: 5 blocking checks
```

处理顺序：先做路径 1（自制图）替换这 5 张 → lint 转绿 → 再公开仓库。**不要**先公开再换图，git 历史会留下。

**路径 1 已落地 5/5**：`samples/` 合成语料（5 页 PDF + 检索索引）跑通，`sidecar/ui/screenshot-demo*.png`
已用无头 Edge 重拍为真实检索截图（引用 `synthetic-book.pdf`），只剩 plugin 的 3 张 DSH 界面截图需要真实会话。

**书页样本**：`eval/p3/make_sample_pages.py` 产出了五种书页样本
（`docs/assets/public/samples/`：公式 / 横排中英 / 竖排繁体 / 拉丁 / 希腊），全部自制、无第三方权利。
剩下的工作是用这些样本重拍 5 张 UI 截图——图不再需要外部素材。

## 4. 对内复用

```
packages/classics-index   ← 纯逻辑（卷/篇/回），零依赖
packages/socratic-mcp     ← 契约的 MCP 包装，零依赖
        ↑                          ↑
sidecar/（服务实现）         plugin-socratic/（DSH 宿主集成）
```

- 依赖只能向上；`eval/` 只读不产出依赖；
- **toc 已收敛**：`sidecar/app/toc.py` 只剩 SQLite 层，逻辑来自 `classics_index.core`（未装包时回退到仓库路径）；
- `docs/SIDECAR-CONTRACT.md` 是唯一契约，破坏性改动升 major。

## 5. 对外共享（不共享数据时）

| 形态 | 别人得到 | 还需要 |
|---|---|---|
| 契约 + 探针 | 可自测的 API 规格 | 自己实现 sidecar |
| MCP server | 6 个工具 | 一个符合契约的 sidecar |
| DSH 插件 | 教学体验 | sidecar + 书库 |
| 索引器 CLI | 卷/篇/回索引 | 自己的扫描件 + OCR |

"自带书库"目前仍是断的（`ingest_library.py` 是脚本），批次 3 补 CLI 前，对外只承诺前三者。

## 6. 风险

| 风险 | 止损 |
|---|---|
| 版权图混入历史 | `publish_lint --scope source` 进 CI，红灯不合并 |
| 产物与源码不一致 | tag ↔ 产物一一对应；PyPI 不可覆盖，只能 yank |
| npm 包带上日志/截图 | `files` 白名单（已加，当前只含 6 项） |
| 契约漂移 | `contract_check.py` 进 CI |
| 维护负担 | 首批只发"工具"，不发"教学体验" |

## 7. 进度（2026-11-03）

| 项 | 状态 | 证据 |
|---|---|---|
| LICENSE = MIT | ✅ | 根目录 + 两个包内；`publish_lint` artifacts 绿 |
| 构建与校验 | ✅ | `dist/` 4 产物；`twine check` 全 PASSED |
| 本机安装 | ✅ | wheel 与 sdist 各装一次，示例数据输出与 `expected-toc.json` 一致 |
| CI | ✅ | `.github/workflows/ci.yml`（packages / sidecar / plugin） |
| 资产门 | ✅ | `publish_lint --scope source`：5 红（阻塞项明确） |
| 上传 PyPI | ⏳ | 需要 token |
| npm 打包 | ⏳ | 本机无 npm/pnpm |
| 资产替换 | ⏳ | 5 张版权截图待自制替换 |

## 8. 下一步（按依赖排序）

1. **自制渲染图替换 5 张截图** → 源码轨转绿；
2. **拿到 PyPI token** → 发 TestPyPI → 正式；
3. 有 Node 的机器上 `npm pack` → 市场条目；
4. 批次 3：sidecar Dockerfile + `socratic-ingest` CLI。
