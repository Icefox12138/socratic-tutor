# 安装与使用说明

| 项 | 值 |
|---|---|
| 适用版本 | `classics-index` 0.1.3 · `socratic-mcp` 0.1.2 · `dsh-socratic` 0.2.3 |
| 日期 | 2026-11-04 |
| 一句话 | 本项目**只负责读库教学**；数据（OCR/切块/向量）由你自己构建或取得 |

---

## 1. 它是怎么拼起来的

```
你的书库 ──(另一套管线)──► RAG 数据库 ──► sidecar ──► 插件 / MCP ──► 你
                            search.db      FastAPI      12 个工具
                            vectors/*.npy
```

三个已发布的包只是"前端"和"接口"，**数据不随包分发**：

| 组件 | 形态 | 装法 |
|---|---|---|
| `dsh-socratic` | DSH 插件（12 个工具） | `dsh plugin add dsh-socratic` |
| `socratic-mcp` | MCP server（任意 host） | `pip install socratic-mcp` |
| `sidecar` | 本地 FastAPI 服务 | 从源码跑（未发布到 PyPI） |
| `classics-index` | 章回索引器（可选） | `pip install classics-index` |

## 2. 前置条件

| 项 | 要求 | 说明 |
|---|---|---|
| Python | **≥ 3.12**（sidecar）/ ≥ 3.10（两个包） | sidecar 用 3.12 开发与验证 |
| 磁盘 | 书库约 30 GB + 数据约 1.2 GB（示例规模） | 视你自己的书库而定 |
| GPU | 可选 | 有则 BGE 向量检索快很多；无则 `SOCRATIC_BGE=0` 走纯 FTS |
| DSH | 若要装插件 | `dsh --version` 可查 |

## 3. 先确认数据

sidecar 需要**一个符合契约的数据库**，格式见
[`RAG-DB-SCHEMA.md`](RAG-DB-SCHEMA.md)（chunks 表 + chunks_fts + 向量 + 可选 toc）。

两条路：

**A. 已有库** → 记下它的根目录，例如 `D:\rag-data`，里面有 `indexes/search.db` 与 `vectors/*.npy`。

**B. 没有库** → 先跑合成语料，验证链路：

```powershell
git clone https://github.com/Icefox12138/socratic-tutor.git
cd socratic-tutor
python samples/generators/make_demo_corpus.py     # 生成 5 页合成书 + 索引
```

检查配置到底指向哪：

```powershell
python scripts/ragdb_check.py
# 输出 data root / database / vectors / toc 四个路径，以及行数是否对齐
```

## 4. 启动 sidecar

```powershell
cd sidecar
pip install fastapi uvicorn pypdfium2 pillow sympy
$env:SOCRATIC_DATA='D:\rag-data'      # 你的库
python -m uvicorn app.main:app --port 8765
```

自检：

```powershell
curl http://127.0.0.1:8765/health
# 有库： {"ok": true, "chunks": 167192, "db": "...", "bge": "ready"}
# 没库： {"ok": false, "reason": "no_index", "hint": "按 docs/RAG-DB-SCHEMA.md 建库…"}
```

**没库不是故障**：服务照常启动，工具会返回 `no_index`。

浏览器界面：<http://127.0.0.1:8765/ui>（可加 `?q=关键词` 直接检索）。

### 4.1 纯文本模式（不保留 PDF）

如果你已经彻底向量化、不打算保留 PDF，可以关掉页图渲染：

```powershell
$env:SOCRATIC_RENDER='off'     # auto（默认）/ on / off
```

| 模式 | 行为 |
|---|---|
| `auto` | 有书库目录且装了 pypdfium2 → 开；否则关 |
| `on` | 强制开；缺依赖会尽早暴露 |
| `off` | `/v1/pages` 返回 501 `{"code": "page_rendering_disabled"}`，citation 的 `page_image` 为 `null` |

关掉渲染后，引用核验仍然可用——改用**页内文本比对**：

```bash
GET /v1/verify?book=<书名>&page=73&quote=随机过程
# {"verified": true, "method": "text", "page": 73, "chunks": 4}
```

它检查"这句话是否真的出现在该页的索引文本里"，能抓住编造与错页，但看不到原页影像。

## 5. 接入 Agent

### 5.1 DSH 插件

```powershell
dsh plugin add dsh-socratic
```

或在市场里加索引后安装：

```
https://raw.githubusercontent.com/Icefox12138/socratic-tutor/main/market/index.json
```

插件默认连 `http://127.0.0.1:8765`；要改就设 `SOCRATIC_SIDECAR_URL`，
需要鉴权再设 `SOCRATIC_TOKEN`。

### 5.2 MCP（任意 host）

```bash
pip install socratic-mcp
```

```json
{
  "mcpServers": {
    "socratic": {
      "command": "python",
      "args": ["-m", "socratic_mcp.server"],
      "env": { "SOCRATIC_SIDECAR_URL": "http://127.0.0.1:8765" }
    }
  }
}
```

### 5.3 12 个工具

| 工具 | 用途 |
|---|---|
| `kb_search` | 检索并返回 citation + 页图 URL；可带 `book` / `chapter` 收窄 |
| `kb_read` | 按 chunk id 读原文 |
| `chapter_lookup` | 「卷3」「第7回」或标题片段 → 页码范围；给 page 则反查章回 |
| `cite_verify` | 校验引用：给 `quote` 走页内文本比对（纯文本模式可用）；不给则取页图 |
| `compute_math` | SymPy 校验（不是口算） |
| `ptc_calc` | 沙箱里执行计算代码 |
| `review_session` | 冻结会话并复盘：结论判定、错误分类、练习 |
| `socratic_critic` | 输出前自检（多问句、越级提示等） |
| `socratic_health` | sidecar 是否可达、索引统计 |
| `socratic_init` / `socratic_state` / `socratic_step` | 教学状态机：初始化 / 读状态 / 推进一步 |

## 6. 典型用法

**查一件事并回页**

> 用 kb_search 搜「微分」，把第一条 citation 的 locator 报出来

**按章回限定**

> 在《史记》「卷2 夏本纪」里查「禹」是怎么被描述的

**核对一句引文**

> 用 cite_verify 看看「民为贵」是否真的出现在这本书第 12 页

**学完之后复盘**

> 用 review_session 复盘这次对话，指出我哪一步是猜的

## 7. 环境变量速查

| 变量 | 默认 | 作用 |
|---|---|---|
| `SOCRATIC_DATA` | `<repo>/data` | 数据根 |
| `SOCRATIC_DB` | `$DATA/indexes/search.db` | RAG 库 |
| `SOCRATIC_BGE_VECTORS` / `_IDS` | `$DATA/vectors/*.npy` | 向量 |
| `SOCRATIC_LIBRARY` | `D:\Guo-Code/library` | 书库根（页图用） |
| `SOCRATIC_TOC_IN` | `state` | 章回索引来源：`state` 或 `search` |
| `SOCRATIC_BGE` | `1` | `0` 关掉向量检索，只走 FTS |
| `SOCRATIC_BGE_MODEL` / `_RERANK_MODEL` | `<root>/models/...` | 模型目录 |
| `SOCRATIC_CACHE` | `sidecar/cache/pages` | 页图缓存 |
| `SOCRATIC_TOKEN` / `_REQUIRE_AUTH` | 空 / `0` | 鉴权（两种头都收：`Authorization: Bearer` 与 `X-Sidecar-Token`） |
| `SOCRATIC_STATE_DB` | `sidecar/state.db` | 会话/复盘/章回状态 |
| `SOCRATIC_RENDER` | `auto` | `auto` / `on` / `off`：是否渲染页图，见 §4.1 |

## 8. 排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `{"ok": false, "reason": "no_index"}` | 库不存在或路径不对 | `python scripts/ragdb_check.py` 看它读的是哪个文件 |
| `bge: "missing: ..."` | 向量文件不在 | 指对 `SOCRATIC_BGE_VECTORS`，或 `SOCRATIC_BGE=0` |
| 检索 0 结果但库里明明有字 | 中文没做二元组分词 | 见 schema `2；`chunks_fts` 必须存分词后的文本 |
| 页图 404 | `book` 键不是书库相对路径，或 `source` 不在 `pages.ROOTS` | 键形如 `物理\朗道…pdf` |
| 401 | 服务端设了 `SOCRATIC_TOKEN` | 客户端带同样的 token |
| 引用指到别处 | 向量与 `chunks.id` 行序错位 | `ragdb_check` 会报 `aligned=False` |
| sidecar 起不来 | 端口占用 / 依赖缺失 | 换 `--port`；`pip install fastapi uvicorn pypdfium2 pillow sympy` |

## 9. 升级与卸载

```powershell
pip install --upgrade classics-index socratic-mcp
dsh plugin add dsh-socratic          # 重装即升级
pip uninstall classics-index socratic-mcp
dsh plugin remove dsh-socratic
```

数据不随包走，升级不影响你的库。

## 10. 许可

代码 MIT（见 [LICENSE](../LICENSE)）。**书库、OCR 文本、向量不随仓库分发**，
其版权状态由使用者自行负责。第三方模型权重（BGE-M3、bge-reranker）同样不重分发。
