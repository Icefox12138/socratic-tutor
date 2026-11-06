# 项目当前状态（canonical）

> 快照日期 **2026-11-06**（公开语料 v2 + 词法 + v1/统一检索，工作区）。历史报告保留原始结论；与旧文档冲突时，以本文件 + [USER-GUIDE.md](USER-GUIDE.md) 为准。

| 项 | 值 |
|---|---|
| 范围 | **只含教学运行时**：sidecar + DSH 插件 + MCP + 章回索引器 |
| 不含 | OCR / 解析 / 切块 / 向量化 / RAG 库构建 → 私有工程 `rag-build`（见 [SPLIT-PLAN.md](SPLIT-PLAN.md)） |
| 数据 | 外部：符合 [RAG-DB-SCHEMA.md](RAG-DB-SCHEMA.md)（私有 PDF）或 [RAG-DB-SCHEMA-V2.md](RAG-DB-SCHEMA-V2.md)（公开语料）的库 |
| 发布 | PyPI `classics-index` 0.1.3、`socratic-mcp` 0.1.2；npm `dsh-socratic` 0.2.4 |
| 测试 | sidecar **263**、classics-index **18**、socratic-mcp **6**、plugin **8** |
| CI | 全绿（四 job：sidecar / packages×2 / plugin） |
| 人工评分 | **延后**（用户决定）；仍不能声称人类验证 |

---

## 1. 运行时能力

| 模块 | 状态 | 说明 |
|---|---|---|
| 检索 | 完成 | FTS5（中文二元组）+ BGE-M3 + reranker；v1 0.82、v2 0.977；`scope=all` 联邦 |
| 页图 | 完成（可选） | pypdfium2 按需渲染；`SOCRATIC_RENDER=off` 时纯文本模式 |
| 引用核验 | 完成 | 页图（`/v1/pages`）或页内文本比对（`/v1/verify`） |
| 章回 | 完成 | `classics-index` 产出的 卷/篇/回；`toc` 可存 `state.db` 或 RAG 库 |
| 状态机 | 完成 | 初始化 / 推进 / 判定 / critic |
| 学习者模型 | 完成 | BKT + FSRS（`fsrs` 缺省时跳过） |
| 复盘 | 完成 | 判定 100%、错误分类 **86.7%**（留出集）、undetermined 0% |
| 内嵌 UI | 完成 | 引用卡 / 提示级别 / 页图 |
| PTC | 条件通过 | 原生 `run_code` 可用；token −2.2%，**不默认** |
| 公开语料 | 完成（首版） | schema v2 + Wikisource/CTS + BGE + OOV 闸门；130 人工题 R@5 **0.977** / R@1 0.862（含词法融合）；未知子集 1.000 |
| 词法通道 | 完成（含融合） | `/v1/grep`、`/v1/lemma`；已作为 v2 检索的 RRF 列表；变格 R@5 0.917–1.000 |
| 统一检索 | 完成（首版） | `scope=all` 合并、`scope=routed` 路由；真实两库冒烟；非学习路由 |

## 2. 关键数字（运行时侧）

| 项 | 值 |
|---|---|
| RAG 库 | chunks **167,192**（tutor 148,261 / answer_key 18,931） |
| 向量 | 148,261 × 1024 fp16，与 ids 对齐 |
| 检索质量 | 单语 **0.80–0.82**（< 0.85）、跨语言 **0.667**（< 0.70） |
| 引用泄漏 | L4 0 / 266 |
| 性能 | 检索毫秒级；页图 ~0.2 s/页（150 dpi） |

> 26 本书的 OCR/解析类结论（K5 希腊文 0.709、K6 拉丁 CER 0.128、表格 TEDS 等）随管线迁往 `rag-build`，不在本仓库维护。

## 3. 明确的限制

1. **检索门未过**：单语 0.82、跨语言 0.667，均低于自设门槛；
2. **人工验证为 0**：任何"人类评分"表述都不成立；
3. **数据质量不由本仓库保证**：引用是否准确取决于使用者自建的库；
4. **`answer_key` 过滤器不等同于防泄漏审计**：它只保证学生视图不返回答案键；
5. **公开语料评估仍是小集**：130 人工题/7 书/331 chunks 的 R@5 0.977，不等于 P1 的 100 问/167k chunks 口径；53 条中文语义题由一人撰写。
6. **LLM 只在 OOV 时启用**（默认 `auto`）：已知词表/中国史问题不调；无 key 自动退化为纯词表。
7. **lemma 只支持 v2 干净文本**；已融合进 v2 检索，但 v1 仍只有独立 grep。
8. **希腊专项未稳定提升**：lemma/注释页索引均默认关闭；v1 希腊 0.417–0.583。
9. **项目整体不是生产级**：v1 recall 0.80–0.82 未过门槛、计算后端有 SymPy/SciPy/pint/control（Wolfram/Lean 未装）、人工评分为 0；详见 `eval/public/RESULTS-project.md`。

## 4. 与旧快照的差异

| 旧（2026-11-03） | 新（2026-11-04） |
|---|---|
| 测试 106/106 | 263（sidecar） |
| 含 P1-3c OCR / P1-3d 解析器 / P3-2…P3-5 索引构建 | 迁出，见 `rag-build/HANDOFF.md` |
| 仓库自带 `data/`（1.2 GB） | 数据在 `D:\Guo-Code\rag-build\data` |
| 页面渲染是硬依赖 | `SOCRATIC_RENDER` 三档，可纯文本运行 |
