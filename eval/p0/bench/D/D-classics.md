# D14–D15 分支 D（古典语言）：三流、身份、CER、canary

| 项 | 值 |
|---|---|
| 日期 | 2026-10-30 |
| 样本 | K1 申辩、K2 College Vergil、K3 希罗多德 1、K4 李维 1；Loeb L036/L063N；Teubner Conte/West |
| 结论 | **条件通过（conditional_pass）**：可量化项全过；三流准确率与 LLM 压力未完成 |

## 1. Steadman 三流（抽样 5 页/本）

| 样本 | text | gloss | note | lineno |
|---|---:|---:|---:|---:|
| K1 申辩 | 47.5% | 42.5% | 8.8% | 1.2% |
| K2 College Vergil | **0.0%** | 76.2% | 22.7% | 1.0% |
| K3 希罗多德 1 | 48.4% | 37.7% | 13.3% | 0.6% |
| K4 李维 1 | **0.0%** | 66.3% | 32.7% | 1.0% |

**关键发现**：K2/K4 抽样页**没有原文**，是注释/词表型卷；K1/K3 约一半是原文。**Steadman 不能按“每本都有原文”排期**，入库前必须逐卷检查 `text_share`。

三流分类器按字体 + Unicode（希腊字母/变音符号）判定，机械上可用；但没有人工金标，**分离准确率未验证**，P1 需 100 条金标。

## 2. 卷身份（identity）

| ID | L 编号 | 标题 | 年份 | 判定 |
|---|---|---|---|---|
| L036 | L036 | Plato: Euthyphro, Apology, Crito, Phaedo, Phaedrus | 1914 | identity_ok |
| L063N | L063N | Virgil: Aeneid I–VI (revised) | 1916（MCMXVI） | identity_ok |
| K7 | Teubner | P. Vergili Maronis Aeneis (Conte) | 2009 | identity_ok |
| K8 | Teubner | Homerus: Ilias (West), vol. I | 1998 | identity_ok |

CSV：`identity/loeb-teubner.csv`（含 sha256、页数）。

## 3. CER 复现

| 基准 | 覆盖 | 加权 CER | p90 | 门槛 | 判定 |
|---|---:|---:|---:|---:|---|
| Loeb 拉丁行级（Aeneid I vs Perseus） | 96.4% | **0.64%** | 2.7% | ≤2% | PASS |
| Loeb 希腊句级（Apology vs Perseus） | 88.4% | **6.07%** | 12.9% | ≤8% | PASS |
| Loeb 拉丁句级（Aeneid vs Perseus） | 45.8% | 1.36% | — | — | 参考 |
| Teubner Conte 行级（vs Perseus） | 100% | **1.9%** | 5.4% | ≤2.5% | PASS |

数值与 D0 前测一致，可复现。

## 4. canary（检索层）

| 测试 | 命中 | 期望 |
|---|---:|---:|
| `view=student` 查 `CANARY-7F3A` | **0** | 0 |
| `view=tutor` 查 `CANARY-7F3A` | **0** | 0 |
| `view=answer_key` 查 | 1 | 1（证明过滤生效而非数据缺失） |
| 无过滤 SQL | 1 | 1（对照） |

结论：`answer_key` 在检索层被 SQL 强制隔离；不是“查不到”，是“被挡掉”。

## 5. LLM 30 轮

**未执行**，原因：§24 的 50 轮 × 3 模型准入归 P1-0；D14 不重复跑。标记 `deferred`，D16 不把它当阻塞项。

## 6. Gate D

| 标准 | 结果 |
|---|---|
| 三流分离 ≥95% | **未验证**（启发式，无金标） |
| 变音符号保真 ≥99% | **未验证**（文字层保留 polytonic，未量化） |
| 行号对齐 ≥90% | **PASS**（96.4%） |
| Loeb 拉丁 ≤2% | **PASS**（0.64%） |
| Loeb 希腊 ≤8% | **PASS**（6.07%） |
| Teubner 零 OCR ≤2.5% | **PASS**（1.9%） |
| 卷身份 100% | **PASS**（4/4） |

**判定：conditional_pass**。阻塞项不是质量，而是**未验证项**：三流准确率、变音符号保真、LLM 压力。P1 补金标与压力测试；D 分支可进入 P0 汇总。

## 7. 对 DESIGN 的回灌

- §10.4：Steadman 入库前加 `text_share` 检查；`text_share < 10%` 的卷只做注释/词表，不排原文。
- §10.2：Loeb 希腊 6.07% 作为 S3 阅读文本可接受，但引用必须页级；拉丁 0.64% 可做行级对齐。
- §20：Teubner Conte 1.9% 作为 S1 基线；West 待补 Perseus Iliad 对照。
- §16.3：canary 四测在检索层已过；对话层留待 P2。

## 产物

`D-report.json`、`D-streams.json`、`D-canary.json`、`D-identity-raw.json`、`identity/loeb-teubner.csv`。
