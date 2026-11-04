# C 盘迁移记录

| 项 | 值 |
|---|---|
| 日期 | 2026-11-02（2026-11-03 回填） |
| C 盘可用 | **14.6 GB → 约 24 GB**（+9 GB；Temp 旧文件已清 1.62 GB） |
| Python 3.12 | `C:\Users\...\uv\python\cpython-3.12...` → `D:\Guo-Code\python\cpython-3.12-windows-x86_64-none` |
| 受影响 venv | `.venv-bge`、`.venv-ocr`、`.venv-mineru`、`.venv-paddle-gpu` |

## 1. 已迁移

| 内容 | 原位置 | 新位置 | 大小 |
|---|---|---|---:|
| Python 3.12.14 | `C:\Users\Administrator\AppData\Roaming\uv\python\...` | `D:\Guo-Code\python\cpython-3.12-windows-x86_64-none` | 62.7 MB |
| uv cache | `C:\Users\Administrator\AppData\Local\uv\cache` | `D:\Guo-Code\cache\uv` | **6,451.1 MB** |
| pip cache | `C:\Users\Administrator\AppData\Local\pip\cache` | `D:\Guo-Code\cache\pip` | 193.8 MB |
| PaddleX 模型 | `C:\Users\Administrator\.paddlex` | `D:\Guo-Code\cache\paddlex` | 160.4 MB |
| MinerU 缓存 | `C:\Users\Administrator\.mineru` | `D:\Guo-Code\cache\mineru` | 248.2 MB |
| uv tools（mcp-cli） | `C:\Users\...\AppData\Roaming\uv\tools` | `D:\Guo-Code\cache\uv-tools` | 256.8 MB |
| 未来 TEMP | `C:\Users\...\AppData\Local\Temp` | `D:\Guo-Code\temp` | 新进程生效 |

环境变量（User）之外，还在原 C 路径建了 **目录 junction**，因此即使进程不读新环境变量，默认路径也落到 D：

```
C:\Users\...\AppData\Local\uv\cache  -> D:\Guo-Code\cache\uv
C:\Users\...\AppData\Local\pip\cache -> D:\Guo-Code\cache\pip
C:\Users\...\.paddlex                -> D:\Guo-Code\cache\paddlex
C:\Users\...\.mineru                 -> D:\Guo-Code\cache\mineru
C:\Users\...\AppData\Roaming\uv\tools -> D:\Guo-Code\cache\uv-tools
```

```
UV_CACHE_DIR=D:\Guo-Code\cache\uv
PIP_CACHE_DIR=D:\Guo-Code\cache\pip
PADDLE_PDX_CACHE_HOME=D:\Guo-Code\cache\paddlex
UV_PYTHON_INSTALL_DIR=D:\Guo-Code\python
HF_HOME=D:\Guo-Code\cache\huggingface
MODELSCOPE_CACHE=D:\Guo-Code\cache\modelscope
UV_TOOL_DIR=D:\Guo-Code\cache\uv-tools
TEMP=D:\Guo-Code\temp
TMP=D:\Guo-Code\temp
```

## 2. Python 迁移细节

- 三个 venv 的 `pyvenv.cfg` 已指向 D 盘 Python；
- venv 的 `Scripts\python.exe` 原是 uv trampoline（内嵌 C 盘路径），迁移后会报
  `uv trampoline failed to spawn Python child process`；
- 解决：用 D 盘 base Python 的 `python.exe` 替换，并补 `python312.dll`、`python3.dll`、`vcruntime140*.dll`；
- 验证：
  - `.venv-bge`：Python 3.12.14 / torch 2.5.1+cu121 / CUDA **True**；
  - `.venv-ocr`：PaddlePaddle 3.3.1 可导入；
  - sidecar：preload 后 `bge=ready`。

## 3. 未迁移（原因）

| 内容 | 大小 | 原因 |
|---|---:|---|
| `C:\Users\Administrator\.dsh` | 357.5 MB | 当前 DSH GUI/会话正在使用；停 DSH 后可整体迁到 D 并设 `DSH_HOME` |
| `AppData\Local\pnpm` | 27.8 MB | DSH 插件安装器在用；收益小 |
| HF cache | 0.1 MB | 已设 `HF_HOME` 到 D，后续写入 D |

## 4. 注意

- User 环境变量只对**新进程**生效；当前 DSH 进程仍用旧环境，重启 DSH 后完全生效。
- 现在直接在当前 shell 跑 `uv` 仍可能写回 C；新终端应使用 D cache。
- `.venv-mineru` 是空/未完成环境，可删；MinerU 依赖安装因 `watchfiles`/tokenizers 冲突未完成。
- P1-3c PaddleOCR 跑到 29/60 页时卡在希腊页，已中止；迁移后再继续。

## 5. 回滚

- Python 可重新 `uv python install 3.12`（会装到 `UV_PYTHON_INSTALL_DIR`）；
- cache 可删除重建，不影响已安装 venv；
- `pyvenv.cfg` 的 home 改回 C 即可（但 C 目录已删）。
