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

1. `sidecar/tests/.tmp-testenv/sitecustomize.py` 是**本机 DSH 沙箱**的测试 shim，不是包内容；Linux CI 不加载。
2. `scripts/make_demo_card.py` 保留 Windows 字体作为**候选**，找不到时回退 DejaVu/默认字体。
3. `pypdfium2`、`scipy`、`pint`、`control` 需要各平台 wheel；Docker 只覆盖 Linux。
4. macOS 未实测；没有 macOS 专用代码。
5. audit 沙箱是 Python 层策略，不是 OS 隔离（三平台一致）。

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
