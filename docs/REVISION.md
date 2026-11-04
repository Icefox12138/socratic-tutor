# 文档修订记录

## 2026-11-03：全面回填

### 新增

- `STATUS.md`：唯一当前状态快照（阶段、数字、阻塞、环境、新 PTC 会话建议）。
- `REVISION.md`：本文件。
- `NEW-PTC-SESSION.md`：新 PTC 会话开场模板。

### 重写

- `README.md`：索引改为 STATUS → HANDOFF → DESIGN，报告按 P1/P2 分组。
- `HANDOFF.md`：完全重写；删除“P2-1 骨架/P2-8 未做/6 类攻击未测”等旧状态。
- `REMAINING.md`：按 P0/P1/P2/P3 重排；阻塞改为 PTC 原生、K5、TEDS、人工评分。
- `GAPS.md`：从“工程 30%”改为当前可运行状态；区分评测债与工程。

### 回填/修订

- `DESIGN.md`：lite v1.2→v1.3；摘要、未闭合、critic、安全状态。
- `DESIGN-full.md`：v2.14→v2.15；顶部状态改为 P0–P2 完成；保留设计论证。
- `FEASIBILITY-REVIEW.md`：新增 §9 P2 后补记。
- `HARDWARE-CLOUD.md`：新增 §8 GPU 4060/Paddle/ODL 实测。
- `CLEANUP.md`：新增 §9 D 盘 venv/缓存现状。
- `P0-PLAN.md`：加“历史文档”提示。
- `P2-1/2/3/4/7` 报告：修正“骨架/UI 未做/测试数”旧结论。
- `P1-3c-local-report.md`：补公式 GPU 交叉引用。
- `C-DRIVE-MIGRATION.md`：C 盘可用更新到约 24 GB，补 Paddle GPU venv。

### 统一口径

- 日期统一绝对日期（2026-11-02/03），不写“今天”。
- 人工评分统一写 **跳过（无 2 名评分者）**，不写“人类验证通过”。
- `ptc_calc` 统一写 **自建、非原生**；原生 `run_code` 统一写 **未注入**。
- K6 金标统一写 **Perseus**；K5 统一写 **希腊 OCR 不可用、页图优先**。
- 公式统一写 **p114 GPU 5.8 s；p118 76.9 s 仍页图 fallback**。
- ODL 统一写 **bbox 覆盖有优势，TEDS 未算**。

### 未改动

- 历史报告正文的原始实验数据与结论保留；只在头部加“后续状态”注记。
- `architecture-analysis.md` 保留为历史评审，不重写。
