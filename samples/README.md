# 合成演示语料

一份**零版权**的小书库，用来演示 sidecar 的完整链路：检索 → 引用 → 页图。

```powershell
python samples/generators/make_demo_corpus.py
$env:SOCRATIC_ROOT="$PWD\samples"
$env:SOCRATIC_DB="$PWD\samples\search.db"
$env:SOCRATIC_STATE_DB="$PWD\samples\state.db"
$env:SOCRATIC_BGE="0"
cd sidecar; uvicorn app.main:app --port 8766
```

打开 <http://127.0.0.1:8766/ui?q=极限>。

## 内容

| 文件 | 说明 |
|---|---|
| `PDF/synthetic-book.pdf` | 5 页，由 `docs/assets/public/samples/*.png` 合成（公式 / 横排中英 / 竖排繁体 / 拉丁 / 希腊） |
| `search.db` | 15 条 chunk + FTS5（中文二元组） |
| `state.db` | 一条 卷首 toc（1–5 页） |

`PDF/`、`*.db`、`cache/` 都是生成物，已 gitignore；仓库里只保留本文件与生成脚本。

## 用途

- README / 市场截图（全部自制，可 MIT 分发）；
- `scripts/contract_check.py --query 极限` 的独立验收靶；
- 新机器的冒烟测试：不碰真实书库即可验证插件、MCP、UI。

## 公开 demo 语料（public-demo/）

`samples/public-demo/` 是一份**全部公有领域**的三语页图语料 + 检索库 + 一课课程包，
给第一次接触项目的人演示完整的「检索 → 引用 → 页图 → 课程」链路。它与上面的合成
样张互补：

| | 合成样张（本目录） | 公开 demo（`public-demo/`） |
|---|---|---|
| 内容 | 自制短句 + 版式演示（公式 / 竖排 / 拉丁 / 希腊） | 真实公版原文：Vergil *Aeneid* I.1–7、Homer *Iliad* I.1–5、《论语·学而》、《老子》第一章 |
| 页数 / 检索块 | 5 页 / 15 块 | 5 页 / 39 块 |
| source | `library` | `demo-public` |
| 课程包 | 无 | curriculum schema v1：`curriculum/demo-public-01.json` |
| 适合 | 截图、版式与冒烟测试 | 给新用户讲“引用可核实”的完整故事 |

```powershell
# 生成（需要 Pillow，仓库自带的 .venv-bge 里有）
.venv-bge\Scripts\python.exe samples\generators\make_public_demo.py

# 启动（demo 启动器会注册 demo-public 页源；直接 uvicorn 时 /v1/pages 只认内置页源）
.venv-bge\Scripts\python.exe samples\public-demo\serve.py
```

详细步骤与验证命令见生成后的 [`samples/public-demo/README.md`](public-demo/README.md)。

**生成物**：`samples/public-demo/` 整个目录由脚本生成并已 gitignore
（目录内的 `.gitignore` 忽略一切），仓库里只提交 `samples/generators/make_public_demo.py`。

**版权**：四段原文（Vergil、Homer、《论语》、《老子》）均属公有领域；页图由 PIL 按
自制版式排版，**不是扫描书页**，不含任何受限数字版的排版、校勘或注释；字体只用本机
字体栅格化、不随仓库分发。生成脚本与课程包文本与仓库其余代码同为 MIT。

