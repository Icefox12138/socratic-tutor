# 发布流程（如果要开源）

> 先看 [RELEASE-PLAN.md](RELEASE-PLAN.md)：发哪 4 个单元、分几批、为什么其余代码不能发。本文件只写“怎么发”。

| 项 | 值 |
|---|---|
| 日期 | **2026-11-03** |
| 现状 | 两个可发布物：`classics-index`（PyPI 包）、`dsh-socratic`（DSH 插件）；sidecar 是配套服务 |
| 前置 | license、示例数据、CI——三件都没做之前不要发 |

---

## 0. 两种动作：包发布 vs 源码开源

它们是**两件事**，解决不同问题：

| | 包发布（artifact） | 源码开源（source） |
|---|---|---|
| 交付物 | 不可变的 sdist/wheel/tarball/镜像 | 可编辑的 git 树 + 历史 |
| 谁消费 | `pip install` / `dsh plugin add` 的终端用户 | 想改、想审、想集成的人 |
| 真源 | registry 上的产物（带 hash） | git 仓库（tag 对应产物） |
| 版本 | PEP 440 / semver，**不可覆盖** | 提交历史，可 revert |
| 回滚 | PyPI `yank`、npm `deprecate`（72h 内可 unpublish） | `git revert` 或新 tag |
| 权限 | token / 2FA / OIDC trusted publishing | 仓库可见性 + 提交权限 |
| 审计 | 产物 hash、provenance 证明 | commit 签名、PR 记录 |
| 发现性 | registry 搜索页、市场条目 | GitHub topics / 文档 |
| CI | release pipeline（构建一次，多处发布） | PR pipeline（每次提交都跑） |
| 法律边界 | LICENSE + 数据版权 + 依赖许可 | 同上，但**历史会永久公开** |

关键差别是**不可逆性**：PyPI 的「同名同版本」上传后不能覆盖，只能 yank（文件还在）；npm 72 小时后不能 unpublish。而 git 历史一旦公开，删除也要重写历史才能抹掉。所以顺序必须是：

```
仓库公开（或先私有） → 打 tag → 构建产物 → 预发 registry 验证 → 正式 registry → 市场条目
```

**先发产物、再想开源**会踩两个坑：registry 页面链到一个不存在的仓库；包里混进了本不该公开的东西（日志、截图、书页）。

### Python 包（classics-index / socratic-mcp）

1. `git tag classics-index-v0.1.0`（tag 与产物一一对应）；
2. `uv build` → `dist/*.whl` + `*.tar.gz`；
3. `twine check dist/*`（README 渲染、元数据）；
4. 装 `dist/*.tar.gz` 到干净 venv，跑一遍示例数据（**产物验证，不是源码验证**）；
5. `twine upload --repository testpypi` → 从 TestPyPI 装一次；
6. `twine upload`（不可逆）；失败只能 yank 后发 0.1.1；
7. 可选：GitHub Actions + OIDC trusted publishing，免 token。

### DSH 插件（dsh-socratic）

1. 先把 `package.json` 的 `files` 写白名单——**没有它，`npm pack` 会把 `pre-step.log`（含会话 id）和书页截图一起打进去**；
2. `npm pack` → 看 tarball 内容（`npm pack --dry-run` 只列不写）；
3. 本地 `dsh plugin add ./dsh-socratic-0.2.0.tgz` 验装（比 `link:` 更接近真实安装）；
4. `npm publish --access public`（72h 内可 unpublish）；
5. 市场条目是**另一件事**：它读 npm 包 + 元数据，需要单独的图标/截图/说明，且截图必须是公版页；
6. `engines.dsh` 要与目标 DSH 版本范围一致，否则装上但加载失败。

### 没有 npm 也能打包（本机实测）

DSH 自带 Node 与 pnpm，可直接用它们代替 npm：

```powershell
$node='D:\Program Files\dsh\resources\runtime\primary-runtime\dependencies\node\bin\node.exe'
$pnpm='D:\Program Files\dsh\resources\runtime\primary-runtime\dependencies\pnpm\bin\pnpm.cjs'

cd plugin-socratic
& $node $pnpm pack --pack-destination ..\dist     # 产出 dsh-socratic-0.2.0.tgz
tar -tzf ..\dist\dsh-socratic-0.2.0.tgz          # 核对内容

# 装到一次性 profile 验证（不动自己的 profile）
dsh plugin --profile packtest add ..\dist\dsh-socratic-0.2.0.tgz
dsh --profile packtest headless "调用 socratic_health"
```

`dsh plugin add` 会自动把包名写进该 profile 的 `dsh.profile.bundles`，不用手改。
发布到 registry 时把 `pnpm pack` 换成 `pnpm publish --access public` 即可。

### 我们现在的状态

- Python 包：构建、twine check、从 sdist 安装并跑通示例，**只差上传**（无 token）；
- 插件：`files` 白名单已加，**已用 DSH 自带 node+pnpm 打出 tarball 并验装**（8 个文件，与仓库字节一致）；只差 `pnpm publish`；
- 源码开源：仓库尚未公开，历史里有 `pre-step.log` 之类的运行时文件——**公开前要清理历史**，不只是加 `.gitignore`。

---

## 1. 先看社区有什么（决定我们发什么）

| 能力 | 现成开源件 | 我们是否需要重造 |
|---|---|---|
| PDF 解析 / OCR | MinerU、Marker、docling、Unstructured、PaddleOCR | 已用 MinerU/Paddle；不必重造 |
| 向量库 | Qdrant、Chroma、Weaviate、pgvector | 现在用 npy；要扩容再接（见 `DATA-SOURCE.md`） |
| RAG 服务 | RAGFlow（页级引用 + DeepDoc）、Onyx/Danswer、PrivateGPT、AnythingLLM、txtai | **没有**"页图回看 + answer_key 隔离 + 五语种 + 章回索引"的组合 |
| 古籍语料 | CBETA（佛典）、ctext、Kanripo | 是语料/API，不是索引器；章回索引没人做 |
| 教学编排 | LangGraph、Letta（通用 agent 框架） | 没有苏格拉底状态机 + L0–L5 提示预算 |

结论：**零件都有，"教学闭环 + 可回页引用"的整机没有**。所以发布物应该是"整机的插件"与"索引器"，而不是再发一个通用 RAG。

## 2. 发布物 A：`classics-index`（PyPI）

**前置清单**

| 项 | 状态 |
|---|---|
| LICENSE（建议 MIT） | ❌ 未定 |
| 版本号 0.1.0、CHANGELOG | ❌ |
| 公版示例数据（页眉 OCR 片段） | ❌ |
| CI（ruff + 16 条测试） | ❌ |
| 包名查重（PyPI） | ❌ |

**流程**

```powershell
cd packages/classics-index
python -m build                      # sdist + wheel
twine check dist/*
twine upload --repository testpypi dist/*   # 先发 TestPyPI
pip install -i https://test.pypi.org/simple classics-index
twine upload dist/*                  # 再发正式
```

发版同时打 git tag（`classics-index-v0.1.0`），Release notes 写"支持什么版式、验证过哪几本书、已知缺陷"。

## 3. 发布物 B：`dsh-socratic`（DSH 插件）

**前置清单**

| 项 | 状态 |
|---|---|
| package.json 补 `description/keywords/license/repository` | ❌ |
| 契约测试（5 条）进 CI | ✅ 已有，未接 CI |
| sidecar 发行方式（Docker/uvx） | ❌ |
| 首次启动引导（sidecar 未运行时给出可操作提示） | ✅ 降级门已做 |
| 截图 / 30 秒 demo | ❌ |

**流程**

1. `plugin-socratic/package.json` 补齐字段，确认 `dsh.bundle` 与 `dsh.client` 仍指向 `cordis.patch.yml` / `client.js`；
2. 打包：`npm pack` 生成 tarball，本地用 `dsh plugin add link:...` 与 `dsh plugin add <tarball>` 各验一遍；
3. 发布到 npm（或私有 registry）；
4. 市场条目写清"**需要配套 sidecar**"，并给出 `docker run` 一行命令；
5. 版本兼容：插件 `0.x` 只保证 `SIDECAR-CONTRACT` v1；契约破坏就升 major。

```json
{
  "name": "dsh-socratic",
  "version": "0.1.0",
  "description": "Socratic tutor tools for DSH: cited retrieval, page images, chapter index, session review",
  "keywords": ["dsh-plugin", "tutor", "rag", "citations", "chinese-classics"],
  "license": "MIT",
  "repository": { "type": "git", "url": "..." },
  "dsh": { "bundle": { "patch": "./cordis.patch.yml" }, "client": { "platform": "web" } }
}
```

## 3b. 发布物 B2：`socratic-mcp`（MCP server）

比 DSH 插件更通用的接缝：任何 MCP host 都能用。

```powershell
cd packages/socratic-mcp
python -m unittest discover -s tests -p "test_*.py" -t .   # 6 条
python -m build && twine upload --repository testpypi dist/*
```

市场说明里给一行 `~/.dsh/dsh-mcp-plus/servers.json` 配置即可，不需要 DSH 插件。

## 4. 发布物 C：sidecar（配套服务）

不建议做成 pip 包（依赖 PyMuPDF + BGE 模型 + 书库）。两种可行形态：

| 形态 | 命令 | 适用 |
|---|---|---|
| Docker | `docker run -p 8765:8765 -v /books:/books ghcr.io/…/socratic-sidecar` | 有 GPU 或愿意用 CPU 的人 |
| uvx / 单文件 | `uvx socratic-sidecar --root /books` | 开发者 |

镜像里**不要**带书库（版权 + 体积），只带代码与模型；书库挂卷。首次启动读 `SOCRATIC_ROOT`，没有索引就给"先跑 ingest"的提示。

## 5. 检查清单（发之前逐条打勾）

```
[ ] LICENSE 文件存在且与 package.json / pyproject.toml 一致
[ ] 示例数据为公版或自制，不含版权书页
[ ] 三套测试全绿：sidecar 119、classics-index 16、插件契约 5
[ ] CI 跑测试 + ruff（Python）/ eslint 或 node --check（JS）
[ ] 插件在"无 sidecar"下给出可操作报错（不是堆栈）
[ ] README 写明"需要配套 sidecar + 自备书库"
[ ] 版本号、CHANGELOG、git tag 三者一致
[ ] 至少一次从干净环境安装并跑通（容器或新 venv）
```

## 6. 不建议做的

- 不要为了"能独立安装"把 sidecar 塞进插件——Node 里没有 PyMuPDF/SymPy 的等价物；
- 不要发布带书库的镜像；
- 不要在没定 license 的情况下发任意 registry；
- 不要把 `eval/` 的实验脚本作为包发布（它们不是 API）。
