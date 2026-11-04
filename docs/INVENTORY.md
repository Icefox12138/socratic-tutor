# 本项目下载了什么

| 项 | 值 |
|---|---|
| 日期 | **2026-11-04** |
| 机器 | RTX 4060 Laptop 8 GB · driver 617.42 |
| 合计 | 依赖环境约 **11.4 GB** · 模型约 **5.3 GB** · 工具缓存约 **16.3 GB** |
| 书库 | 另计 28.9 GB（不是"下载的软件"，是语料） |

---

## 1. Python 环境（四个 venv，各自用 uv 建）

| venv | 体积 | 包数 | 关键依赖 |
|---|---:|---:|---|
| `.venv-bge` | 5.1 GB | 110 | torch 2.5.1+cu121、transformers 4.46.3、sentence-transformers 3.3.1、fastapi 0.162.0、uvicorn 0.54.0、sympy 1.13.1、numpy 2.5.4、pillow 12.3.0、pymupdf 2.0、pypdfium2 5.14.0、onnxruntime 1.31.1 |
| `.venv-ocr` | 1.1 GB | 107 | **paddlepaddle 3.3.1（CPU）**、paddleocr 3.7.0、paddlex 3.7.2、rapidocr-onnxruntime 1.4.4、opendataloader-pdf 2.5.17、pypdfium2 5.14.0 |
| `.venv-mineru` | 477 MB | 98 | mineru 4.1.3、mineru-vl-utils 2.0.8、mineru-llama-cpp 0.2.0、onnxruntime-directml 1.24.4 |
| `.venv-paddle-gpu` | 4.7 GB | 24 | **paddlepaddle-gpu 3.0.0**（含 CUDA 运行库）；**未装 paddleocr**，实际没跑起来 |

为什么是四个而不是一个：BGE 需要 torch+cu121，PaddleOCR 需要 paddle，MinerU 自带一套
依赖，三者对 numpy/pillow 的版本要求互相冲突，只能分环境。

## 2. 模型权重

| 模型 | 体积 | 用途 | 位置 |
|---|---:|---|---|
| **BGE-M3** | 2,187 MB | 向量检索（XLM-R，1024 维，8192 上下文） | `models/bge-m3` |
| **bge-reranker-v2-m3** | 2,187 MB | 交叉编码器重排 | `models/bge-reranker-v2-m3` |
| PaddleOCR 模型组 | 917 MB | 见下表 | `~/.paddlex/official_models` |

PaddleOCR 那一组是**按需自动下载**的，不是一次装齐：

| 模型 | 体积 | 用途 |
|---|---:|---|
| PP-FormulaNet_plus-M | 595 MB | 公式识别 |
| PP-DocLayout_plus-L | 124 MB | 版面分析 |
| PP-OCRv6_medium_rec / det | 73 / 59 MB | 高精度识别 |
| UVDoc | 31 MB | 文档去扭曲 |
| PP-OCRv5_mobile_rec / det | 16 / 5 MB | 快速识别 |
| PP-LCNet_x1_0_doc_ori / textline_ori | 7 / 7 MB | 方向分类 |

## 3. 工具与运行时

| 工具 | 版本 | 来源 | 用途 |
|---|---|---|---|
| git | 系统安装 | `D:\Program Files\Git` | 版本控制 |
| uv | 独立安装 | `~/.local/bin/uv.exe` | 建 venv、装包、构建 wheel |
| python | 3.14（系统） | `D:\Program Files\Python314` | 仅用于系统级脚本 |
| node | v24.21 | DSH 自带 | 打包 npm 插件 |
| pnpm | 11.28.5 | DSH 自带 | 同上 |
| DSH | 0.2.1-rc.5 | 安装包 | 宿主（插件运行环境） |

项目自身**没有 Node 依赖**：`plugin-socratic` 的 `dependencies` 是空的，只用 DSH 提供的
运行时 API。

## 4. 能从 PyPI / npm 装回来的（已发布物）

| 包 | 渠道 | 版本 |
|---|---|---|
| `classics-index` | PyPI | 0.1.2 |
| `socratic-mcp` | PyPI | 0.1.1 |
| `dsh-socratic` | npm | 0.2.2 |

## 5. 缓存（可删，会重新下载）

| 目录 | 体积 | 说明 |
|---|---:|---|
| `D:\Guo-Code\cache\uv` | **14.6 GB** | uv 的 wheel 缓存，`uv cache clean` 可清空 |
| `D:\Guo-Code\cache\paddlex` | 917 MB | 与 `~/.paddlex` 内容重复，可删其一 |
| `D:\Guo-Code\cache\mineru` | 249 MB | MinerU 的配置与模型缓存 |
| `D:\Guo-Code\cache\uv-tools` | 257 MB | `uv tool run` 装过的工具（twine 等） |
| `D:\Guo-Code\cache\pip` | 194 MB | 早期 pip 下载残留 |
| `C:\Users\Administrator\.paddlex` | 917 MB | PaddleOCR 模型本体（这个**别删**） |

清理建议顺序：`uv cache clean`（14.6 GB）→ 删 `cache\paddlex`（重复 917 MB）→
`cache\pip`、`cache\uv-tools`（约 450 MB）。合计可回收 **约 16 GB**。

## 6. 已知问题

- **PaddleOCR 当前跑不起来**：`paddle 3.3.1` + `paddleocr 3.7.0` 在 Windows 上抛
  `NotImplementedError: ConvertPirAttribute2RuntimeAttribute ... (onednn_instruction.cc:118)`。
  P3 那批 2,745 页是更早的环境跑出来的；重做 OCR 前要先解决这个。
- `.venv-paddle-gpu` 装了 4.7 GB 的 GPU 版 paddle，但**没有装 paddleocr**，等于闲置；
  要么补装，要么删掉回收 4.7 GB。
