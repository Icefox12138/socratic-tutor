# 新 PTC 会话开场（复制到新对话）

```text
项目：D:\Guo-Code\socratic-tutor
先读：docs/STATUS.md、docs/HANDOFF.md、docs/REMAINING.md
不要重跑 P0/P1；不要声称人工评分。

当前状态：
1) PTC 已收口：原生 run_code 可用但不省 token（−2.2%）→ 不默认；docs/P2-9-PTC-token.md
2) 表格 TEDS 已收口：ODL 0.437 / PyMuPDF 0.527 → 不换；docs/P1-3d-TEDS.md
3) K5 希腊 OCR 不可用，只能页图；
4) p118 公式 76.9 s，仍页图 fallback。

已收口：PTC、表格 TEDS、K5 页图策略、P3 复盘 v1（报告都在 docs/）。

已收口：PTC、表格 TEDS、K5 页图策略、复盘 v1、竖排卷级章回索引 + 页图浏览。

已收口：PTC、表格 TEDS、K5 页图策略、复盘 v1、竖排卷级/篇级索引 + 页图浏览。

技术线已全部收口：P0–P2 选型（PTC/解析器/K5 页图）、P3 复盘（86.7%）、
卷/篇索引 + 页图浏览、章回小说回目索引验证（132 段）。

当前唯一硬缺口：人工评分（已决定靠个人试用/开源/模型进步解决，不阻塞开发）。

已收口：检索已接章回（book+chapter，扫描本回页图）。

本轮可选目标：
A. 章回小说索引收尾（全 5291 页 + 书名识别 + 修过切）；
B. 把扫描本的页图纳入引用卡（turnTail 展示章回页图）。

约束：
- 单机/单学生；不接出版社 API；
- 4060 8 GB；sidecar 与 BGE 分时；
- 先读 docs/STATUS.md，再改代码；
- 若 pwsh 返回 0xC0000142，是会话沙箱挡住子进程创建，不是缺依赖：
  换 danger-full-access 或在自己的终端跑。
```
