# P3-1 复盘 v1

| 项 | 值 |
|---|---|
| 日期 | **2026-11-03** |
| 范围 | 会话复盘：逐条判定、8 类错误、归因、复练 |
| 验收 | 复盘 ≥80%、`undetermined <20%` |
| 结果 | **留出集 error-class 86.7%、判定 100%、undetermined 0%**；门通过 |
| 测试 | sidecar **82/82**（新增 23 条复盘测试） |

---

## 1. 结论

v1 是**确定性复盘**：同一份会话快照，任何人重跑都得到同一份报告。不调 LLM、不猜判。

| 指标（留出集 23 条） | 值 | 门 |
|---|---:|---|
| 判定准确率（correct/incorrect） | **100%** | — |
| 错误分类准确率（7 个可测类） | **86.7%** | ≥80% ✅ |
| undetermined 比例 | **0%** | <20% ✅ |

调参集（30 条）上是 100%，但那组规则是照着它改出来的，**不作为验收数**；验收看留出集。

## 2. 管线（DESIGN `10 的五步）

| 步 | 实现 |
|---|---|
| 1 冻结快照 | 取 `state`（question/expected/concept/lang/history），算 `digest` 写 `reviews` 表 |
| 2 只抽学生陈述 | `extract_claims`：问句、转述（"也就是说/换句话说"）标 `not_a_claim`，不进分母 |
| 3 判定 | `judge`：数学答案用 SymPy 精确比较（`simplify(c-e)==0`、解集按集合比）；无 `expected` 或非数学文本 → `undetermined`，**永不判错** |
| 4 分类 + 归因 | `classify` 7 条结构规则 + `attribute` 4 类 |
| 5 报告 + 复练 | `summary/errors/practice`；掌握度仍由 `state_step` 的 BKT 更新，复盘**不重复计分** |

## 3. 错误分类（8 类，DESIGN `10.4）

| 类 | 触发条件（claim vs expected） |
|---|---|
| `sign` | `c + e == 0` |
| `incomplete` | claim 的加性项是 expected 项的真子集（丢项） |
| `misread` | claim 含 expected 没有的符号（答错量/变量） |
| `condition` | 解集真子集（漏根） |
| `unit` | 量级差 ≥1000×，或 claim 带单位而 expected 不带 |
| `arithmetic` | 同结构不同系数、数值差、或比值是数值 |
| `formula` | 次数/函数形式不同，或解集真超集（多根） |
| `concept` | 兜底：以上都不命中 |

归因顺序：缺 `expected` → `question`；题干 <8 字 → `question`；`lang` 是希腊 → `material`（K5 页图策略）；BKT <0.35 且连续错 ≥2 → `curriculum`；否则 `student`。

## 4. 评测方法（以及它的诚实边界）

没有人工评分者，所以金标是**变异标注**：给 8 个正确答案，按每个错误类注入一次"学生最可能犯的错"，复盘只能看到 `(claim, expected)`，要把类和判定都还原出来。

- **调参集** `eval/p3/review_eval.py`：30 条，规则在这里调；
- **留出集** 同文件 `--split holdout`：23 条，用不同表达式/记号写，**只跑一次**，两条 miss 原样保留：

| miss | 真值 | 判定 | 原因 |
|---|---|---|---|
| `x` vs `2*x` | incomplete | arithmetic | 丢的是因子不是项；项集测试抓不到 |
| `1` vs `100`（100 cm = 1 m） | unit | arithmetic | 单位量级阈值是 1000×，100× 的换算漏掉 |

这两条**没有回头改规则**——改了就是拿留出集调参。它们是 v1 的已知边界。

边界还要写清楚：金标是"注入错误"，不是"教师认定的错误"，所以 86.7% 说明**规则能还原注入的错误类型**，不等于教学判断力；真实课堂里的复合错误（一步错两处）会落到 `concept` 或 `undetermined`。

## 5. 端到端

```
POST /v1/state/init   {session_id:"p3-demo", goal:"导数", concept:"derivative"}
POST /v1/state/step   confirm_goal -> diagnosed -> plan_ready
POST /v1/state/step   asked  {text:"求 x^3 的导数", expected:"3*x**2"}
POST /v1/state/step   answer {result:"wrong", text:"我算的是 4x^2。"}
POST /v1/review       {session_id:"p3-demo"}
-> claim "我算的是 4x**2"  verdict=incorrect  error=arithmetic  attribution=student
   summary {n_claims:1, incorrect:1, undetermined:0, errors:{arithmetic:1}}
   practice [{term:"derivative", definition:"3*x**2", error:"arithmetic"}]
   digest 53b11d71534ce694
```

复现：`python eval/p3/review_demo.py`（sidecar 在 :8765）。

## 6. 接口

- `POST /v1/review` `{session_id, state?, answers?, record=true}`；
- 插件工具 `review_session`（默认当前会话，可显式传 `answers`）；
- 会话里学生原话随 `answer` 事件入 `history[].text`（本轮新增，旧快照无此字段时回落为"无学生原话"）。

## 7. 局限

- 规则是确定性的，复合错误归到 `concept`；文本型答案（非数学）只认完全一致，否则 `undetermined`；
- 没有掌握度回写：`state_step` 已经按每题更新 BKT，复盘再写会双计；复练卡只**建议**、不自动入库；
- 金标是变异标注，不含教师判断；
- 只测数学 + 少量中文，未覆盖希腊/拉丁的文字型答案（K5 按策略本来就只出页图）。
