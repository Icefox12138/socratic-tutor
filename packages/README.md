# packages/

独立版本化、可单独发布的包。其余可发布物在仓库其它目录（见下表），各自由 tag 触发发布。

| 包 | 位置 | 渠道 | 形态 | 依赖 |
|---|---|---|---|---|
| [classics-index](classics-index/) | 本目录 | [PyPI `classics-index@0.1.4`](https://pypi.org/project/classics-index/) | Python CLI / 库 | 纯标准库；OCR 可选 |
| [socratic-mcp](socratic-mcp/) | 本目录 | [PyPI `socratic-mcp@0.2.1`](https://pypi.org/project/socratic-mcp/) | MCP server | 纯标准库；需一个 sidecar |
| `socratic-sidecar` | [../sidecar/](../sidecar/) | [PyPI `socratic-sidecar@0.3.1`](https://pypi.org/project/socratic-sidecar/) | FastAPI 服务 + CLI | 见 `sidecar/pyproject.toml`；`cards`/`compute`/`lemma` 为可选 extra |
| `dsh-socratic` | [../plugin-socratic/](../plugin-socratic/) | [npm `dsh-socratic@0.5.2`](https://www.npmjs.com/package/dsh-socratic) | DSH 插件 bundle（13 工具 + 教学台） | 需 sidecar；教学行为另装 persona |
| `dsh-socratic-persona` | [../plugin-socratic-persona/](../plugin-socratic-persona/) | [npm `dsh-socratic-persona@0.1.1`](https://www.npmjs.com/package/dsh-socratic-persona) | DSH 插件 bundle（教学层） | 需 sidecar |
| `dsh-socratic-curriculum` | [../plugin-socratic-curriculum/](../plugin-socratic-curriculum/) | [npm `dsh-socratic-curriculum@0.1.0`](https://www.npmjs.com/package/dsh-socratic-curriculum) | DSH 插件 bundle（课程层） | 需 sidecar + 课程包 |
| `calcbox` / `ragpages` | 独立仓库 | PyPI `calcbox@0.4.0` / `ragpages@0.1.0` | 计算后端 / PDF→RAG 库 | 见各自仓库 |

## classics-index——卷/篇/回逻辑的共享库

不是"构建期工具"，而是**唯一实现**：私有数据管线 `rag-build` 在构建期用它建章回索引，`sidecar`
在运行期用它服务 `/v1/chapter` 与检索路径（`sidecar/pyproject.toml` 硬依赖 `classics-index>=0.1`）。
纯标准库，OCR 引擎可选。

```
pip install -e packages/classics-index
classics-index volumes --headers heads.jsonl --out toc.json
```

## socratic-mcp

把 sidecar 的 HTTP 契约暴露成 MCP 工具（检索/词法/章回/复盘/状态机），供任意 MCP 客户端使用；
需要已运行的 sidecar。

## 为什么其余目录不在这里发布

不是复用性差，而是**数据假设**：`sidecar/` 的检索、引用、页图都假设一个本地书库与向量文件存在，
所以它以"自带数据 + 可选 demo 语料"的方式发布（`uvx --from socratic-sidecar`），而不是作为
"开箱即用"的库；`plugin-socratic*` 是 DSH bundle，走 npm；`eval/` 是一次性实验脚本，价值在方法。
详见 [../docs/OPEN-SOURCE.md](../docs/OPEN-SOURCE.md)。
