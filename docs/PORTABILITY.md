# 跨平台兼容性检查（Windows / Linux / macOS）

| 项 | 值 |
|---|---|
| 扫描 | `python scripts/portability_check.py` → **PORTABLE** |
| Windows | 本机 Windows 11 / Python 3.12：sidecar **264/264** |
| Linux | GitHub Actions `ubuntu-latest`（Python 3.12）+ Dockerfile；本机无 Docker/WSL，未实跑镜像 |
| macOS | **未实测**；纯 Python/Node 代码，无 Windows API 依赖 |
| CI | 新增 `sidecar-windows` job；原有 ubuntu packages/sidecar/plugin job 保留 |

## 1. 扫描规则

`scripts/portability_check.py` 扫描 `.py/.js/.mjs/.toml/.yml/.json`（跳过 docs/tests/data/venv）：

- 盘符绝对路径（`D:\...`）；
- Windows-only API：`WinDLL`/`windll`/`msvcrt`/`winreg`/`os.startfile`/`CREATE_NO_WINDOW`；
- POSIX 绝对路径（`/home`、`/Users`、`/tmp`…）；
- `shell=True`。

当前结果：**PORTABLE**。

## 2. 本轮修复

| 问题 | 修复 |
|---|---|
| Windows AppContainer 代码不可用且平台绑定 | **删除 `sandbox.py`**；只保留 `sandbox_policy.py` audit 沙箱 |
| `translate.py` / `evaluator.py` 硬编码 `D:\...\deepseek API key.txt` | `SOCRATIC_LLM_KEY_FILE` → `ROOT/deepseek API key.txt` → cwd 回退 |
| `make_demo_card.py` 只用 Windows 字体 | Windows / Noto / DejaVu / macOS 候选回退 |
| `ragdb_check.py` 手写 SQLite URI | `pathlib.Path.as_uri()`，Windows/Linux 都用 `file:///...` |
| `publish_lint.py` 只查盘符路径 | 同时查 POSIX 绝对路径 |
| 插件 README/SMOKE 示例硬编码 `D:\` | 改为 `/path/to/...` |
| CI 只有 ubuntu | 新增 `sidecar-windows`；两端都跑同一套测试 |

## 3. 平台相关但可接受的剩余项

1. **Windows 沙箱内的临时目录**：`tempfile.mkdtemp()` 建的目录带 owner-only DACL，DSH 的 `workspace-write` 沙箱既写不进也删不掉（`PermissionError`；SQLite 报 `unable to open database file`）。因此测试统一用 `sidecar/tests/_tmp.py`（`os.makedirs` 实现）与 `packages/classics-index/tests/test_cli.py` 里的同名函数。Linux CI 不受影响，用同一套代码即可。
2. `scripts/make_demo_card.py` 保留 Windows 字体作为**候选**，找不到时回退 DejaVu/默认字体。
3. `pypdfium2`、`scipy`、`pint`、`control` 需要各平台 wheel；Docker 只覆盖 Linux。
4. macOS 未实测；没有 macOS 专用代码。
5. audit 沙箱是 Python 层策略，不是 OS 隔离（三平台一致）。

## 3b. DSH 权限档对运行的影响（实测，Windows）

| 能力 | 只读 | 工作区可写 | 完全权限 |
|---|---|---|---|
| 读外部书库 / RAG 库（`D:\Guo-Code\library`、`rag-build`） | ✅ | ✅ | ✅ |
| 起 sidecar、检索、页图 | ⚠️ 读得到，写不进引用 | ✅ | ✅ |
| 引用写入 `state.db`（带 `session_id` 的检索） | ❌ 503 | ✅ | ✅ |
| 页图缓存 | ❌ | ✅ | ✅ |
| 公开语料 ingest → `<repo>/data` | ❌ | ✅ | ✅ |
| ingest → `rag-build`（工作区外） | ❌ | ❌ | ✅ |
| `python -m unittest discover` | ❌ | ✅（用 `_tmp.py`） | ✅ |
| `node --test`（plugin） | ❌ | ❌ `spawn EPERM` | ✅ |

结论：**工作区可写是日常开发与服务的合适档位**；只有往 `rag-build` 写数据（大批量 ingest / 模型缓存）才需要完全权限。只读档只能做“看代码 + 读库”，不能教学（写不了引用与状态）。

> 已知副作用：早期用裸 `tempfile.mkdtemp()` 跑测试时，沙箱内创建的空目录**无法删除**（连 `icacls /reset` 也被拒）。清理必须在沙箱外（普通 PowerShell / 资源管理器）进行。

## 4. 复现

```bash
python scripts/portability_check.py
python scripts/publish_lint.py --scope all
cd sidecar && SOCRATIC_BGE=0 python -m unittest discover -s tests -p "test_*.py"
```

Linux 镜像：

```bash
docker compose up --build
```
