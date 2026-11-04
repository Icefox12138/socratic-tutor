# 合成演示语料

一份**零版权**的小书库，用来演示 sidecar 的完整链路：检索 → 引用 → 页图。

```powershell
python eval/p3/make_demo_corpus.py
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
