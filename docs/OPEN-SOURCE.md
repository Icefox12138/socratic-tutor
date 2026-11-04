# 开源价值评估与代码整理

| 项 | 值 |
|---|---|
| 日期 | **2026-11-03** |
| 结论 | 全项目 **1 个包可发布**（`classics-index`）；插件与服务是"可打包但不宜上架"；eval 是方法不是库 |
| 已做 | 抽出 `packages/classics-index`（16 测试、CLI、真实数据复现） |

---

## 1. 评估维度

一个模块值不值得进市场，看四件事：**别人能不能用**（数据依赖）、**装了会不会坏**（服务依赖）、**边界清不清**（是库还是实验）、**有没有 license**。

| 模块 | 复用价值 | 自包含 | 市场可行性 | 判断 |
|---|---|---|---|---|
| `packages/classics-index` | **高**：任何有扫描古籍的人 | **高**：纯标准库 | **高** | ✅ 做成 PyPI 包 |
| `sidecar/`（FastAPI） | 中：检索/引用/页图 | 低：绑 `D:\Guo-Code\PDF`、BGE 模型文件 | 低 | ⚠️ 作为独立服务，不进插件市场 |
| `plugin-socratic/`（host+client） | 中：教学状态机/硬拦截/引用卡 | **低**：所有工具都调 sidecar | 低 | ⚠️ 作为**示例/参考实现**，不做市场包 |
| `eval/p3/` 索引脚本 | 高：版心/标题带 OCR | 中：要 PaddleOCR | 中 | ✅ 已并入 `classics-index`（脚本保留为"数据生产端"） |
| `eval/p1`、`eval/p2` harness | 中：TEDS / 复盘 / token 对比 | 中 | 低 | ⛔ 方法可复用，代码不必发布 |
| `docs/` 证据纪律 | — | — | — | ⛔ 不是代码，但可作为仓库 README 的方法论 |

## 2. 为什么插件不宜直接上架

市场的用户没有你的 27 GB 书库、没有 sidecar、没有 BGE 模型。装上 `dsh-socratic` 后：

1. `kb_search` 直接 500（sidecar 不在）；
2. `socratic_init` 也 500；
3. 唯一能跑的是 `compute_math`——那不如直接用计算器插件。

要让它"装上不坏"，至少需要：sidecar 可选（degraded mode）、书库路径可配、API 版本化、离线示例数据、license + CI。这是**一个产品化项目的工作量**，不是整理代码能解决的。

## 3. 已经做的整理

```
packages/
  classics-index/          ← 新增，可发布
    classics_index/core.py     卷/篇核心（从 sidecar/app/toc.py 抽出，去掉 SQLite）
    classics_index/hui.py      章回小说回目分段（从 eval/p3/build_hui_segments.py 抽出）
    classics_index/cli.py      volumes / pian / hui / find / at
    tests/                     16 条，可离线跑
    pyproject.toml, README.md
  README.md                ← 包地图与"为什么只有这一个"
```

抽出时修掉了两个只在大盘数据上才暴露的 bug：

1. `merge_pian` 对已经展开过的 `level=2` 行会重复插入（现在入口处过滤）；
2. 章回小说"换书边界"用的是**重排后的编号**，导致分书永远晚一回（现在用页眉上真正读到的 `detected` 号）。

## 4. 真实数据复现

```powershell
cd packages/classics-index
python -m classics_index.cli volumes --headers ../../eval/p3/out/C1_heads.jsonl --out toc.json
python -m classics_index.cli pian    --toc toc.json --band ../../eval/p3/out/C1_titles.jsonl --out index.json
python -m classics_index.cli hui     --ocr ../../eval/p3/out/hui.jsonl --names "1=西游记,2=水浒传" --out hui.json
```

结果与项目内脚本一致：史记 9 行卷 / 16 行卷+篇（覆盖 358/358）；四大名著 101 + 106 + 9 回。

## 5. 若要真正发布，还缺什么

| 缺项 | 工作量 | 说明 |
|---|---|---|
| LICENSE | 5 分钟 | 建议 MIT；**未选之前不要发布** |
| 示例数据 | 半天 | 一本公版书的页眉 OCR 片段（不能带版权书） |
| CI | 半天 | GitHub Actions 跑 16 条测试 + ruff |
| 版本策略 | 2 小时 | 0.1.0 起，CLI 参数视为不稳定 |
| 包名/命名空间 | 10 分钟 | `classics-index` 可能被占，先查 PyPI |

## 6. 插件解耦（本轮已做）

结论：**能解耦到"可上架的前端插件"的程度，但不能解耦成"独立可用"**——因为它没有数据。

### 耦合面有多大

12 个工具，9 组端点，全部走同一个 HTTP 边界：

| 层 | 内容 | 是否领域 |
|---|---|---|
| 传输 | baseUrl / token / sessionId / 错误规范化 / 健康探测 | ❌ 通用 |
| 契约 | search、chapters、pages、compute、state、critic、citations、review、health | ❌ 通用 |
| 领域 | 教学章程、状态机调用序列、单问/泄漏/引用硬拦截、页图卡 | ✅ 苏格拉底专属 |

唯一不依赖 sidecar 的是 `ptc_calc` 的沙箱本身（它调用的 `compute_symbolic` 仍然要 sidecar）。

### 做了什么

1. **抽传输层** `plugin-socratic/lib/transport.js`：settings / call / callBinary / probe / degraded，领域代码只 import 它；
2. **降级门**：每个工具执行前探测 `/health`（缓存 5 秒），不可达时返回
   `{"ok":false,"error":"sidecar_unreachable","tool":"kb_search","base":"...","hint":"启动 sidecar ..."}`，
   而不是抛栈；`socratic_health` 例外，永远执行并报 `reachable:false`；
3. **契约文档** `docs/SIDECAR-CONTRACT.md`：9 组端点 + 响应形状 + 降级规则——这是真正的解耦产物，别人可以写自己的 sidecar；
4. **契约测试** `plugin-socratic/test/plugin.test.mjs`（5 条，`node --test`）：工具面完整、侧车不可达时结构化报错、health 例外、正常透传、baseUrl 覆盖。

### 还没解耦的

- **客户端引用卡**仍按 sidecar 的响应字段渲染（`lang`/`image_only`/`page_image`）——契约已把它写成公开形状，但代码没有抽象成"任意来源的卡片"；
- **没有自带数据**：装上空转是必然的，只能靠"请自备 sidecar + 书库"的说明；
- 没有 degraded 下的 `compute_math` 本地实现（需要 SymPy，Node 侧没有等价物）。

### 对"上市场"的判断

| 路径 | 可行性 | 代价 |
|---|---|---|
| 作为"需要配套服务"的插件上架 | 中（要看市场是否允许） | 需要一个 sidecar 发行方式（Docker/uvx） |
| 作为**示例仓库**发布 | 高 | 几乎零成本，README 已写明边界 |
| 做成独立可用 | 低 | 等于把 sidecar + 27 GB 书库重做一遍 |

## 7. 不建议做的事

- 不要把 `plugin-socratic` 拆成"教学插件"上架——它没有独立价值，只会让用户装上就报错；
- 不要把 `eval/` 的实验脚本包装成库——它们是针对特定数据的断言，不是通用 API；
- 不要为了"开源"去删掉项目里的路径常量——那会让本体跑不起来，收益为零。
