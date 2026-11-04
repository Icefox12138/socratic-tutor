# P1-3c K5 页图策略落地

| 项 | 值 |
|---|---|
| 日期 | **2026-11-03** |
| 范围 | 希腊文（K5 / Steadman）在服务端的引用形态 |
| 结论 | **希腊命中只出 citation + 页图**，`text` 在服务端置空；OCR 不进服务链路 |
| 测试 | sidecar **59/59**（新增 8 条策略测试） |

---

## 1. 为什么是"只出页图"

两个独立证据：

- 本地三引擎在 K5 上的 CER 是 **70.9%–94.0%**（P1-3c-local-report），OCR 文本不可用；
- 馆藏里 K5 的文本层本身是"希腊文 + 英文对页注释"的混合：200 条抽样里希腊字母占比只有 **14%–32%**，其余是拉丁注释与词表。

也就是说，把 K5 的 `text` 交给模型，模型会拿"英文注释 + 噪声希腊文"当原文引用——这比不给文本更糟。

## 2. 强制点（三层，全在服务端）

| 位置 | 行为 |
|---|---|
| `GET /v1/search` 的每条结果 | `text` 置空，加 `image_only: true` 与 `text_omitted`，`citation.page_image` 必填 |
| `GET /v1/chunks/{id}` | 同上（`kb_read` 走这条） |
| `citations` 表 | `snippet` 写空串，只留 locator + 页图 |
| `GET /health` | 暴露 `image_only_langs`，便于运维核对 |

判定逻辑在 `sidecar/app/policy.py`：

```python
DEFAULT_LANGS = ("greek", "grc")          # 目录里是 greek；grc 是 ISO 639-3 别名
LANGS = _configured()                      # SOCRATIC_IMAGE_ONLY_LANGS 可覆盖
def redact(result): ...                    # 非破坏性：缓存里的原文不动
```

**检索不受影响**：FTS / BGE / rerank 仍用存储文本（这是召回的基础），只有"返回给调用方"的那一层被替换。缓存的 payload 同样是脱敏后的版本，避免二次泄漏。

## 3. 验证（端到端，真实 sidecar + BGE）

```
GET /health          -> image_only_langs ["grc","greek"], chunks 167192
GET /v1/search?q=Socrates on courage&limit=8
   mode=bge+rerank, 8 results, 7 greek / 1 latin
   greek p8  text_empty=True  image_only=True  /v1/pages -> 200, 220031 bytes
   greek p9  text_empty=True  image_only=True  /v1/pages -> 200, 225233 bytes
   greek p21 text_empty=True  image_only=True  /v1/pages -> 200, 274321 bytes
   latin p83 text_len=310 （不受影响）
GET /v1/chunks/22881 -> text='' image_only=True locator=phaedo__phaedo-25june15w p.8
VIOLATIONS: 0
```

复现：`python eval/p2/k5/check_policy.py`（需 sidecar 在 :8765）。

## 4. 测试

```
cd sidecar
..\.venv-bge\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
Ran 59 tests ... OK
```

新增 `tests/test_policy.py`（8 条）：默认语言集、`grc` 别名、env 覆盖与清空、`redact` 非破坏性、拉丁不受影响、`_row_result` 走策略、citations 不落 snippet。

## 5. 回退与影响面

- **回退**：`SOCRATIC_IMAGE_ONLY_LANGS=""` 恢复默认；设成别的语言（如 `latin`）即可把策略挪到另一门语言，不用改代码。
- **模型侧变化**：tutor 现在只能拿到 `locator` + 页图 URL，不能引用希腊文本；"事实断言必须带 locator"的硬拦截因此更容易满足。
- **前端**：composer 引用卡本来对 `lang=greek` 只显示页图（client.js:142），现在与服务端行为一致，不再有"UI 隐藏、模型仍可引用"的错位。

## 6. 留下的一件事

FTS 的 tokenizer 只覆盖 CJK 与 `[a-z]{2,}`，**希腊词查不进去**——`/v1/search?q=ψυχή` 在 FTS 分支为空，希腊语查询实际上完全依赖 BGE。本轮没有改 tokenizer（会动到索引与 0.82 的 recall 基线），记为后续项：

- 若要做"希腊语原词检索"：给 FTS 加希腊字母 run 的分词，重建 `chunks_fts`，再复测 recall；
- 在此之前，K5 的正确用法是"英文/中文提问 → BGE 命中 → 页图引用"，与当前 UI 流程一致。
