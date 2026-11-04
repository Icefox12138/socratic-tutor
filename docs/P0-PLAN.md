# P0 执行记录与结果（16 个工作日 → 收窄 GO）

> **历史文档（2026-10-30）**：保留 P0 原始结论；后续 P1/P2 结果见 `STATUS.md`。安全 7/7、教学闭环、UI 等已不在本文范围。

| 项 | 值 |
|---|---|
| 版本 | v3.0（2026-10-30，执行后回填；替代 v2.0 计划） |
| 执行期 | 2026-10-29 ~ 2026-10-30 |
| 投入 | 16 个工作日 × 3.5 h ≈ 56 h（下载不计） |
| 判定 | **收窄 GO**（`eval/p0/go-no-go.md`） |
| 一句话 | 检索层与古典/理工可用；中文/竖排降级为“页图 + OCR 检索” |

---

## 1. 逐日执行记录

| 计划 | 状态 | 实际结果 | 产物 |
|---|---|---|---|
| D0 preflight | **PASS** | 801 本/27.46 GB；哈希 801/800 唯一（1 组重复）；D: 468.7 GB；20 本全命中 | `preflight.md`、`hash-manifest.jsonl` |
| D1–D2 capability-probe | **部分通过** | `tools.register`（原始 schema）、`pre-execute`、`post-execute` 可用；`context`/jobs/storage 部分；node/token/出站未验证 | `capability/api-matrix.md` |
| D3 catalog + manifest | **PASS** | 905 条/904 唯一；20 本全命中；K5–K8 对齐正文起点 | `catalog/sample-manifest.json`、`catalog.jsonl` |
| D4 检索对照 | **PASS，A 分支** | 109,229 chunks；recall@10 0.95；p95 38.7 ms；canary 0/0 | `retrieval-compare.md`、`ADR-012` |
| D5–D7 分支 A | **降级通过** | A1 964 字/页但公式结构丢失（代理 55.4%）；A2/A4 OCR 公式不可用；A3 代码可读；SymPy 10/10 | `bench/A/*` |
| D8–D10 分支 B | **FAIL（CER）** | B1 1,508 字/页、224 行注未分离；合成 OCR CER 12.1%/10.5%；B2/B3 523/665 字/页 | `bench/B/*` |
| D11–D13 分支 C | **FAIL（注文/OCR）** | C1 18/18 列序正确；注文未分离；竖排 OCR 0–46 字/列 | `bench/C/*` |
| D14–D15 分支 D | **条件通过** | 拉丁 0.64%、希腊 6.07%、Conte 1.9%、身份 4/4；K2/K4 无原文；三流未验证 | `bench/D/*`、`identity/loeb-teubner.csv` |
| D16 go/no-go | **收窄 GO** | 2 支通过（A 降级、D 条件）→ 收窄 | `go-no-go.md` |

**偏差**：D5–D7、D8–D10、D11–D13 各压成一轮执行；OCR 用 `rapidocr-onnxruntime`（非 PP-StructureV3）；LLM 30 轮延后 P1-0；表格 TEDS 未测。

---

## 2. 关键实测数字

| 项 | 数值 |
|---|---:|
| 馆藏 | 801 本 / 27.46 GB / 361,862 页 |
| 哈希唯一 | 800 / 801 |
| 检索 chunks | 109,229（5 本） |
| recall@10 | 0.95 |
| p95 检索延迟 | 38.7 ms |
| canary（student/tutor） | 0 / 0 |
| 中文 OCR CER | 12.1%（200dpi）/ 10.5%（300dpi） |
| 拉丁行级 CER | 0.64%（覆盖 96.4%） |
| 希腊句级 CER | 6.07%（覆盖 88.4%） |
| Teubner Conte 行级 CER | 1.9%（覆盖 100%） |
| 文字层公式代理可编译 | 55.4% |
| 竖排列序 | 18/18 |
| SymPy 计算题 | 10/10 |

---

## 3. 分支 Gate 结果

| 分支 | 标准 | 实测 | 判定 |
|---|---|---|---|
| A 理工 | 公式可编译 ≥90%；OCR CDM ≥0.75；TEDS ≥0.85；SymPy 10 题 | 55.4%；不可用；未测；10/10 | **降级** |
| B 现代汉语 | CER ≤2%；结构 F1 ≥0.90；脚注不混 | 12.1%；未测；混排 | **FAIL** |
| C 竖排 | 列序 ≥95%；注文 ≤10%；CER ≤5% | 列序 100%；注文未分离；OCR 不可用 | **FAIL** |
| D 古典 | 三流 ≥95%；变音符 ≥99%；行号 ≥90%；Loeb ≤2%/8%；Teubner ≤2.5%；身份 100% | 三流未验证；未测；96.4%；0.64%/6.07%；1.9%；4/4 | **条件通过** |

---

## 4. 横向 Gate 结果

| Gate | 结果 |
|---|---|
| API | 4 可用/部分、4 未验证；有 fallback |
| 检索 | PASS（0.95 / 38.7 ms / 0 泄漏） |
| 隔离 | PASS（student 0 / tutor 0 / answer_key 1 / 无过滤 1） |
| 引用 | PASS（机制）；页图核验 100% 为发布门 |
| 安全 | **未测** |
| 卷身份 | PASS（4/4） |
| 版权 | PASS（Conte/West 标 `personal`） |
| 依赖 | PASS（`dsh-knowledge` 不在关键路径） |

---

## 5. 收窄后的 MVP

**保留**：古典（Steadman 含原文卷 + Loeb/Teubner）、理工正文/代码、中文 OCR 检索 + 页图引用、自建 `socratic-search`、书/卷/页引用 + 页图。

**砍掉**：竖排逐字 OCR、中文逐字引用、公式自动 LaTeX、全库预处理。

**P1 入口**：P1-0 LLM 准入；Steadman 逐卷 `text_share`；Conte/West `personal`；BGE-M3 复跑 D4；首批只排古典 + 理工正文。

---

## 6. 执行中发现的硬约束（写给 P1）

1. 插件必须声明 `inject`；开发用 `link:`；profile `package.json` 无 BOM；headless 需 `@deepseek-ai/dsh-headless` + `DEEPSEEK_API_KEY`。
2. `tools/post-execute` 签名 `(exec, result)`，返回 `{content}`，不能同时返回 `value`。
3. `2% CER` 对扫描中文不现实；改“检索级 ≤10% + 引用级页图”。
4. 竖排 PP-OCR 不可用；注文必须在版面阶段分离，否则只做页图。
5. 文字层公式 ≠ 可计算；`text-layer conf=0`，只认 VLM 高置信 LaTeX。
6. Steadman 不是每本都有原文；逐卷 `text_share` 是排期前置条件。

---

## 7. 未完成项

| 项 | 归属 |
|---|---|
| LLM 50 轮 × 3 模型 | P1-0 |
| 6 类安全攻击 | P1 |
| 三流 100 条金标 | P1 |
| 中文/竖排 VLM OCR | P1.5 |
| 对话层 canary | P2 |
| 表格 TEDS | P1 |
