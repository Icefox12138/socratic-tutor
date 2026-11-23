# Curriculum schema v1（课程包契约）

> 引擎**不发布课程**。它发布这份契约与 `GET /v1/curriculum` 端点：任何人把课程写成 JSON 放进 `SOCRATIC_CURRICULUM` 指向的目录，引擎即可消费。发布者只维护契约与引擎。

## 1. 存储位置

- 环境变量 `SOCRATIC_CURRICULUM`（默认 `<repo>/curriculum`），目录下每个 **`*.json` = 一课**。
- 一篇课程 = `line（语种线）→ course → unit → lesson`；MVP 不做 course 层文件，用 `line + unit + lesson` 字段表达顺序。

## 2. 一课的最小形状

```json
{
  "schema": 1,
  "lesson_id": "latin-vergil-1-01",
  "line": "latin",
  "title": "Aeneid I.1–11",
  "unit": 1,
  "lesson": 1,
  "passage": {"source": "demo", "book": "synthetic-book.pdf",
              "page_start": 1, "page_end": 2},
  "background": "本课目标与背景（可空字符串）",
  "worked_example": "预习阶段用的例子/示范（可选）",
  "vocab": [{"headword": "arma", "lang": "latin", "gloss": "武器"}],
  "grammar": [{"scheme": "grammar", "section": "§419", "note": "独立夺格"}],
  "questions": [{"q": "…", "rubric": "…",
                 "answer_loc": {"source": "demo", "book": "synthetic-book.pdf", "page": 2}}],
  "review_cards": [{"term": "arma", "definition": "武器"}]
}
```

### 字段规则（`app/curriculum.py:validate`）

| 字段 | 必填 | 规则 |
|---|---|---|
| `schema` | 是 | 必须为 `1` |
| `lesson_id` | 是 | `[a-z0-9][a-z0-9._-]{0,63}`，全局唯一 |
| `line` / `title` | 是 | 非空字符串 |
| `unit` / `lesson` | 是 | 整数 ≥ 1（用于排序与目录展示） |
| `passage` | 是 | `source`、`book` 非空；`page_start` ≥ 1 且 ≤ `page_end` |
| `background` | 是（可空串） | 字符串；预习阶段的讲解文案 |
| `worked_example` | 否 | 字符串；预习阶段的一个示范 |
| `vocab[]` | 否 | 每项 `headword` 非空；`lang` 可选；带 lexicon.db 时解析出词条 |
| `grammar[]` | 否 | `{scheme, section}`；数据入库后由 `/v1/lexicon?area=grammar` 解析 |
| `questions[]` | 是 | 至少 1 条，每条 `q` 非空；`answer_loc` 用于引用锚点 |
| `review_cards[]` | 是 | 至少 1 条，每条 `term` 非空；SUMMARY 时写入 FSRS 卡片 |

## 3. 引擎如何使用

1. `GET /v1/curriculum` → 目录（按 `line/unit/lesson` 排序）；
2. `GET /v1/curriculum/{lesson_id}` → 完整一课（`vocab` 已解析出 lexicon 词条，缺库时 `entry: null`）；
3. 会话：`POST /v1/state/init` 带 `lesson`、`learn`（预习）、`review`（复习）；
   - `learn=true`：DIAGNOSE 后插入 **LEARN** 阶段（讲解 + worked example + 让学习者回讲），`learn_done` 后进 PLAN；
   - `review=true`：从 **REVIEW** 阶段开场（宿主从 `/v1/cards/due` 取到期卡），`review_done` 后进 DIAGNOSE；
4. 校验：`python scripts/curriculum_check.py --dir <目录>`。

## 4. 版权边界

课程引用的 `passage` 是**书库相对路径**：课程包本身可自由分发（JSON + 文案），但被引的页图/文本是否可分发取决于书源。公开课程请只用公版或合成样张（见 `samples/curriculum/demo-five-page-types.json`）。
