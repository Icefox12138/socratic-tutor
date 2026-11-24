# 项目当前状态（canonical）

> 快照日期 **2026-11-23**（PyPI 发布已自动化：`publish-pypi.yml`；`classics-index` 0.1.4 / `socratic-mcp` 0.2.1 已发布）。**最后核对：2026-11-23，`ci` 绿。** 历史报告保留原始结论；与旧文档冲突时，以本文件 + [USER-GUIDE.md](USER-GUIDE.md) 为准。

| 项 | 值 |
|---|---|
| 仓库位置 | **`D:\Guo-Code\classics\socratic-tutor`**（2026-11-23 与 library/models/rag-build/calcbox 一并归入 `classics\`；历史文档里的旧路径为当时快照） |
| 范围 | **教学运行时**：sidecar + 两个 DSH 插件（工具 / 人格）+ MCP + 章回索引器 + 发布工作流 |
| 不含 | OCR / 解析 / 切块 / 向量化 / RAG 库构建 → 私有工程 `rag-build`（见 [SPLIT-PLAN.md](SPLIT-PLAN.md)） |
| 数据 | 外部：符合 [RAG-DB-SCHEMA.md](RAG-DB-SCHEMA.md)（私有 PDF）或 [RAG-DB-SCHEMA-V2.md](RAG-DB-SCHEMA-V2.md)（公开语料，**v2.1**：`documents.kind` / 扩 stream / `lexicon_headwords`）的库；`book_meta.json` 可选 |
| 发布 | npm **`dsh-socratic` 0.5.1**、**`dsh-socratic-persona` 0.1.1**（OIDC trusted publishing，带 SLSA provenance）；PyPI **`classics-index` 0.1.4**、**`socratic-mcp` 0.2.1**（tag 驱动 `publish-pypi.yml`，OIDC trusted publishing，带 attestations）；`calcbox` 0.4.0（独立仓库，2026-11-23 发布，mcp extra 收紧到 `mcp>=2`；sidecar 依赖 `calcbox>=0.3,<0.5`）；sidecar **0.3.0**（engine 已提供 PyPI 打包：`socratic-sidecar` + `[project.scripts]` 入口，`publish-pypi.yml`（tag `sidecar-v*`）就绪；PyPI 项目首发布后即可 `uvx` 安装） |
| 插件形态 | **拆成两个 bundle**：工具包（13 工具 + 卡片）与人脑包（章程 / 每步摘要 / 流改写）。desktop 只装工具，`tutor` / `web` 两个都装 |
| DSH 兼容 | 实测 **0.2.2-rc.2 / rc.5**（rc.5 由插件审计核对）；`engines.dsh` = `>=0.2.1-rc.2 <0.3.0-0 \|\| >=0.2.2-rc.2 <0.3.0-0`（严格 semver 也接受 0.2.2-rc.2） |
| 引用策略 | **M0–M5 消费端全部落地** + **词典/语法规则**：`/v1/policy`、`/v1/channels`、`/v1/policy/reload`；页图根由通道表派生；`tier`/`tier_estimated` 查表；`scope=all` 支持 `rrf`/`weighted`/`tiered`；`book_meta` → `doc_kind`/`subject`；`doc_kind=dictionary|grammar` 选 `dict-lsj` / `grammar-*`（tier A，`catalogue: lexicon`）。**默认路径与改前逐位相同** |
| 词目查表 | **数据已建（M1，2026-11-23）**：`lexicon.db` 219,738 条目 / 381,392 义项（LSJ 1940 版 + L&S；释义已 beta→Unicode，v2.1 列齐全）；`/v1/lexicon` 按 `chunks.entry_id` 读回整条词目，长词条按字符窗口分页（`entry_offset`/`entry_limit`，λόγος 24 KB）；**A&G 语法 § 已入库（M3，2026-11-24：615/642 节，源版缺 §607–629、§639–642）**；Smyth 决策见 [review/M2-M3.md](../review/M2-M3.md)；缺库显式降级 `no_lexicon` |
| 课程契约 | **框架化（schema v1，2026-11-23）**：`/v1/curriculum` 与 `/v1/curriculum/{lesson_id}` 消费 `SOCRATIC_CURRICULUM` 目录里的课程包；`LEARN`/`REVIEW` 阶段按需开启（`/v1/state/init` 的 `learn`/`review`）；引擎不发布课程，内容由第三方按契约提供（见 [CURRICULUM-SCHEMA.md](CURRICULUM-SCHEMA.md)） |
| 测试 | sidecar **383**、plugin **6 + 13**（工具 / 人格）、classics-index **20**、socratic-mcp **6** |
| CI | 全绿：`ci.yml` 四组 job + `publish-npm.yml`（tag 触发，OIDC）+ `publish-pypi.yml`（tag 触发，OIDC） |
| 人工评分 | **延后**（用户决定）；仍不能声称人类验证 |

---

## 1. 运行时能力

| 模块 | 状态 | 说明 |
|---|---|---|
| 检索 | 完成 | FTS5（中文二元组）+ BGE-M3 + reranker；v1 0.80–0.82、v2 R@5 0.977；`scope=all` 联邦 |
| 页图 | 完成（可选） | pypdfium2 按需渲染（加锁串行，防 PDFium 线程崩溃）；`SOCRATIC_RENDER=off` 为纯文本模式 |
| 引用核验 | 完成 | 页图（`/v1/pages`）或页内文本比对（`/v1/verify`） |
| 章回 | 完成 | `classics-index` 产出的 卷/篇/回；`toc` 可存 `state.db` 或 RAG 库 |
| 状态机 | 完成 | 初始化 / 推进 / 判定 / critic |
| 学习者模型 | 完成 | BKT + FSRS（`fsrs` 缺省时跳过） |
| 复盘 | 完成 | 判定 100%、错误分类 **86.7%**（留出集）、undetermined 0% |
| 内嵌 UI | 完成 | 引用卡（含 tier / 锚点角色）、引用策略卡、页图、提示级别 |
| 计算后端 | 完成 | 实现已迁到独立包 **calcbox 0.4.0**（PyPI, MIT）；`sidecar/app/compute.py` 只是适配层 |
| DSH 插件 | 完成（已拆包） | `dsh-socratic` 13 工具 + `client.js` 卡片；`dsh-socratic-persona` 章程 + `agent/pre-step` + `llm/stream` |
| PTC | 条件通过 | 原生 `run_code` 可用；token −2.2%，**不默认** |
| 公开语料 | 完成（首版） | schema v2 + Wikisource/CTS + BGE + OOV 闸门；130 人工题 R@5 0.977 / R@1 0.862 |
| 词法通道 | 完成（含融合） | `/v1/grep`、`/v1/lemma`；已作为 v2 检索的 RRF 列表 |
| 词目查表 | **完成（M1 数据 + M2 分页/提速 + M3 语法数据）** | `/v1/lexicon`（词形→词元→词条；`§N` 小节；`entry_offset`/`entry_limit` 分页）；`lexicon_headwords` 精确索引、不建向量；单次查表 ~0.2–0.3 ms（索引命中）；缺库 → `no_lexicon` |
| 统一检索 | 完成（首版） | `scope=all` 合并、`scope=routed` 路由 |
| 打包 | 完成 | `Dockerfile` / `docker-compose.yml`；跨平台路径见 [PORTABILITY.md](PORTABILITY.md) |

## 2. 关键数字（运行时侧）

| 项 | 值 |
|---|---|
| RAG 库 | chunks **167,192**（tutor 148,261 / answer_key 18,931） |
| 向量 | 148,261 × 1024 fp16，与 ids 对齐 |
| 书目标注 | `book_meta.json` **800 条**；其中 **61 本**有 chunk（14 本 unknown 属正常） |
| 检索质量 | 单语 **0.80–0.82**（< 0.85）、跨语言 **0.667**（< 0.70） |
| 引用泄漏 | L4 0 / 266 |
| 性能 | 检索毫秒级；页图 ~0.2 s/页（150 dpi） |

> 26 本书的 OCR/解析类结论（K5 希腊文 0.709、K6 拉丁 CER 0.128、表格 TEDS 等）随管线迁往 `rag-build`，不在本仓库维护。

## 3. 明确的限制

1. **检索门未过**：单语 0.82、跨语言 0.667，均低于自设门槛；
2. **人工验证为 0**：任何"人类评分"表述都不成立；
3. **数据质量不由本仓库保证**：引用是否准确取决于使用者自建的库；
4. **`answer_key` 过滤器不等同于防泄漏审计**：它只保证学生视图不返回答案键；
5. **公开语料评估仍是小集**：130 人工题 / 7 书 / 331 chunks 的 R@5 0.977，不等于 P1 的 100 问口径；
6. **LLM 只在 OOV 时启用**（默认 `auto`）：已知词表/中国史问题不调；无 key 自动退化为纯词表；
7. **lemma 只支持 v2 干净文本**；v1 仍只有独立 grep；
8. **希腊专项未稳定提升**：lemma/注释页索引均默认关闭；v1 希腊 0.417–0.583；
9. **`book_meta` 只覆盖 `library` 语料**：Steadman/Teubner 的 `book` 是 slug 不是书库路径，查不到就整体不输出 `doc_kind`/`subject`；800 条里 739 本没有 chunk 是正常现象，不是缺漏；
10. **人格包是 profile 级**：`dsh-socratic-persona` 的章程、每步摘要、流改写对**该 profile 的所有会话**生效，**不能按会话切换**。开发用只装工具包的 profile，教学用另装人格包的 profile；
11. **npm 发布走 OIDC**：`publish-npm.yml` 需要与 npm 上 Trusted Publisher 配置的文件名逐字一致；手工 `npm publish` 在启用 "disallow tokens" 后不再可用；
12. **DSH 0.2.2 会深冻结 `llm/stream` 的 options**，`agent/pre-step` 的 decision 也已改为**返回新对象**而不是原地 `unshift`；
13. **DSH 沙箱与本地跑测试**：`tempfile.mkdtemp()` 建的目录带 owner-only DACL，`workspace-write` 下不可写 → 用 `sidecar/tests/_tmp.py`；`node --test` 需 `--test-isolation=none`（默认 spawn 子进程会 `EPERM`）；`git push` 走 SSH 时 git 会 spawn `sh` 建管道，沙箱内失败，需放宽一次权限；
14. **词典数据与语法 § 均可用**：`lexicon.db`（M1，2026-11-23）219,738 词条；`/v1/lexicon` 按 `chunks.entry_id` 读回整条词目，长词条按字符窗口分页（M2，2026-11-24：λόγος 24 KB，`entry_offset`/`entry_limit` + `next_offset`；索引命中后单次 ~0.3 ms）；**A&G 语法 § 已入库（M3，2026-11-24）**：615/642 节（§1–§638，源版缺 §607–629、§639–642），`area=grammar` 可查 `§419`；Smyth 全量导入待定（见 review/M2-M3.md）；插件侧词条卡 UI 未做。
15. **`smythp` 与 `§N` 是两套编号**：语法 locator 的 `section`（§N）与 Perseus `smythp=NNNN` 不互相推导，查 `smythp=` 只按精确键匹配；
16. **按类型定流会改变学生可见内容**：`documents.kind` 一旦填上 `dictionary/grammar/textbook/edition`，学生视图会比只给 `text` 时多出定义/表格/注释等；这是有意的，但部署方必须知道自己开了什么（`/v1/policy` 的 `education` 段可核对）；
17. **项目整体不是生产级**：v1 recall 0.80–0.82 未过门槛、计算后端为 SymPy/SciPy/pint/control（Wolfram/Lean 未装）、人工评分为 0。

## 4. 与旧快照的差异

| 旧（2026-11-06） | 新（2026-11-23） |
|---|---|
| npm `dsh-socratic` 0.4.0（单包，含人格） | 0.5.1 工具包 + `dsh-socratic-persona` 0.1.1，**拆包**；OIDC 发布带 provenance |
| 引用策略 M0–M4 | M0–**M5 消费端** + **dict/grammar 规则**（`doc_kind` 选源，tier A，`catalogue: lexicon`） |
| schema v2（`documents` 无 `kind`；stream 四种） | **schema v2.1**：`documents.kind`、stream 扩到十种、`lexicon_headwords` |
| 学生视图只有 `stream='text'` | 按文档 `kind` 定档（字典含 definition/example；教材含 formula/table/code…），`SOCRATIC_STUDENT_STREAMS` 仍可整表覆盖 |
| 测试 264 / 8 | sidecar **383** / plugin **6 + 13** |
| 计算在 `sidecar/app/compute.py` | 迁到 **calcbox 0.4.0**，此处只剩适配层 |
| 未验证 DSH 升级 | 实测 **0.2.2-rc.2 / rc.5**，`engines` 放宽为并集 |
| 无 npm 发布流水线 | `publish-npm.yml`：打 tag 即发布，无长期 token |
| 测试用 `tempfile.mkdtemp()` | `_tmp.py`；插件测试 `--test-isolation=none` |
| 无词目查表 | `/v1/lexicon`（M1 数据 + M2 分页 + M3 A&G 语法 §；`area=grammar` 已可用） |
