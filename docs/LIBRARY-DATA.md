# 书库与派生数据：目录约定

| 项 | 值 |
|---|---|
| 日期 | **2026-11-04**（归并整理） |
| 书库根 | `D:\Guo-Code\library`（27.4 + 0.75 + 0.70 + 0.01 ≈ **28.9 GB**） |
| 派生数据根 | `D:\Guo-Code\socratic-tutor\data`（约 **1.2 GB**，已 gitignore） |
| 配置 | `SOCRATIC_LIBRARY` / `SOCRATIC_DATA`，都有旧布局回退 |

---

## 1. 布局

```
D:\Guo-Code\
├── library\                    ← 书，只读，永不写
│   ├── PDF\                    27.4 GB · 800 PDF（主书库，6 大类）
│   ├── PDF-new\Steadman\        0.75 GB · 100 PDF（希腊/拉丁教学本）
│   ├── loeb\                    0.70 GB · 2 PDF + 页图 + 抽取文本
│   └── teubner\                 0.01 GB · 2 PDF + djvu 文本
│
├── models\                     ← BGE-M3 / reranker 权重（第三方，不重分发）
│
└── socratic-tutor\             ← 工作区（python 可写）
    └── data\                   ← 派生数据，全部可重建
        ├── indexes\            search.db / library.db / steadman.db（约 730 MB）
        ├── vectors\            bge-vectors.npy / bge-ids.npy（约 291 MB）
        └── experiments\        bakeoff-out / p0-retrieval（约 185 MB）
```

历史布局（已废弃）：`D:\Guo-Code\PDF`、`PDF-new`、`loeb`、`teubner` 平铺在根目录，
派生数据散落在 `socratic-tutor\eval\p1\{ingest,bge}` 与 `eval\p0\retrieval`。

## 2. 为什么派生数据不能放在 library 旁边

一开始我把 `data` 放在 `D:\Guo-Code\data`，sidecar 启动即 503：

```
sqlite3.OperationalError: unable to open database file
```

原因不是文件坏了（复制一份能正常读到 167,192 条），而是 **SQLite 需要在数据库同目录创建
journal/WAL**，而运行 sidecar 的 python 进程对工作区之外的目录没有写权限。
所以派生数据必须落在 `socratic-tutor\data`。

**这条约束顺带解释了书库的语义**：书是只读的，本来就不该由服务写入。

## 3. 配置与回退

```python
LIBRARY = SOCRATIC_LIBRARY or first_existing(ROOT/library, ROOT)
DATA    = SOCRATIC_DATA    or first_existing(ROOT/socratic-tutor/data, ROOT/socratic-tutor/eval)
```

- 新布局存在 → 直接用；不存在 → 回退到旧路径，所以老安装不会坏；
- `pages.ROOTS` 由 `LIBRARY` 派生，**book 键仍是书库相对路径**，索引无需重建：

```
library:        LIBRARY/PDF
steadman:       LIBRARY/PDF-new/Steadman
teubner_conte:  LIBRARY/teubner
```

## 4. 验证

移动后以默认配置启动 sidecar：

```
health: ok=True chunks=167192                 ← 索引在新路径可用
page:   HTTP 200 1318237 bytes                ← 真实书页可渲染（四大名著 p.10）
```

## 5. 还没跟上的脚本

有 7 个 eval 脚本硬编码了旧路径（`eval/p1/ingest/*.db`、`eval/p1/bge/*.npy`、
`eval/p0/retrieval`、`eval/p1/bakeoff/out`）。它们是研究脚本，不在发布物里：

- 需要重跑时，用 `SOCRATIC_DB` / `SOCRATIC_BGE_VECTORS` 指向 `data/`，或改脚本里那一行路径；
- 下次重构评测管线时统一改成读 `config`。

## 6. 可重建性

| 目录 | 重建方式 | 耗时 |
|---|---|---|
| `data/indexes` | `eval/p1/ingest/build_search.py`（需先跑 ingest） | 数小时 |
| `data/vectors` | `eval/p1/bge/embed_bge.py`（需 GPU） | 约 1 小时 |
| `data/experiments` | 各评测脚本 | 不定 |

**书库本体不可重建**（版权，且来源分散）——它是唯一需要备份的东西。
