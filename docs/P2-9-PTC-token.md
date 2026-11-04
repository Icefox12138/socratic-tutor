# P2-9 原生 PTC token 对比（收口）

| 项 | 值 |
|---|---|
| 日期 | **2026-11-03** |
| 环境 | DSH 0.2.1-rc.5（node 24.21）；profile `tutor`（dsh-socratic）；sidecar :8765 预热 |
| 方法 | 同 10 题，native / PTC 各跑一遍，每题独立 session |
| 脚本 | `eval/p2/ptc/token_compare.mjs`；原始数据 `eval/p2/ptc/token-results.json` |
| 结论 | **PTC 不省 token，不默认化**；token 项**闭合**（结果为负） |

---

## 1. 结论

`run_code` 原生可用（见 §2），但**在 socratic 的 9 工具规模上，PTC 是净亏**：

| 指标 | native | PTC | 差 |
|---|---:|---:|---:|
| 未缓存输入 token | 45,043 | 42,813 | −4.9% |
| 输出 token | 21,336 | 22,115 | +3.6% |
| **输入+输出合计** | **66,379** | **64,928** | **−2.2%** |
| 缓存读 token | 538,496 | 639,616 | **+18.8%** |
| 计费加权（in + 0.1×cache + 2.5×out） | 152,233 | 162,062 | **+6.5%** |
| 模型回合（step） | 54 | 56 | +2 |
| 工具调用次数 | 57 | 46 | −11 |
| 墙钟总时长 | 191.6 s | 236.7 s | **+23.6%** |
| 成功 | 10/10 | 9/10 | −1 |

**P2-8 的验收线是"token 节省 ≥30%"，实测 −2.2%（计费加权 +6.5%），不达标。**
逐题方差 ±60%（见 §3），−2.2% 落在噪声内，不能解释为"基本持平"——它是"没有节省"。

## 2. 阻塞项 1 已失效（原文档写"原生 run_code 未注入"）

- 安装盘已是 **0.2.1-rc.5**（P2-8 报告写的是 rc.3）；
- `dsh-base` 的 bundle 组合了 `@deepseek-ai/dsh-ptc-runtime-node`（`cordis.patch.yml` 里 `id: ptc-runtime`）；
- 随包出货 `web-app/presets/ptc.patch.yml`，其中一行：

  ```
  - name: '@deepseek-ai/dsh-agent-tool-presentation'
    config: { mode: ptc }
  ```

- headless 不选 preset，改用部署级开关：`dsh-headless/cordis.patch.yml` 里 `tools.mode: !!js process.env.DSH_TOOLS_MODE`。所以 `$env:DSH_TOOLS_MODE='ptc'` 就是 tutor 侧的"PTC preset"。
- 实测该开关下 9 个 socratic 工具全部变成 `run_code` 的绑定，模型 10 题共发起 46 次 `run_code`（内含子调用），无一处"未知绑定"。

**结论：不需要再配 preset，也不存在"runtime 包没有 dsh.bundle"的阻塞。**

## 3. 逐题结果（输入+输出 token）

| # | 类型 | native | PTC | 差 | 工具调用(n/p) |
|---:|---|---:|---:|---:|---|
| t01 | kb | 12,606 | 16,735 | +32.8% | 5/10 |
| t02 | kb | 10,122 | 9,654 | −4.6% | 5/5 |
| t03 | compute | 5,535 | 4,694 | −15.2% | 3/4（PTC 运行失败） |
| t04 | compute | 6,155 | 4,809 | −21.9% | 5/4 |
| t05 | compute | 3,359 | 4,940 | +47.1% | 5/3 |
| t06 | compute | 5,207 | 4,670 | −10.3% | 4/4 |
| t07 | compute | 8,288 | 3,212 | −61.2% | 11/3 |
| t08 | kb | 7,804 | 6,077 | −22.1% | 9/4 |
| t09 | compute | 4,216 | 2,592 | −38.5% | 7/3 |
| t10 | kb | 3,087 | 7,545 | +144.4% | 3/6 |

单题最大节省 t07（−61%）：native 绕了 11 次工具调用，PTC 用 3 次 `run_code` 一次算完。
单题最大亏损 t10（+144%）：PTC 侧多起 3 次 `run_code`，每次都要重读更大的前缀。

## 4. 固定开销：PTC 的 SDK 比 9 个 schema 更贵

同一 agent 的请求前缀（`contextBreakdown`）：

| 模式 | systemTokens | toolsTokens | 前缀合计 |
|---|---:|---:|---:|
| native（9 个 schema） | 819 | 5,955 | **6,774** |
| PTC（run_code + 生成 SDK） | 7,769 | 628 | **8,397** |

工具 schema 从 5,955 压到 628，但生成的 SDK 文本把 system 抬到 7,769 —— **每请求 +1,623 token（+24%）**。
这个前缀在每一步都要重读一次，所以 `cacheRead` 涨 18.8%，而 step 数没降。

## 5. 为什么没省

PTC 压的是**工具调用次数**（57→46），不是**模型回合数**（54→56）。
这 10 题平均 5.4 步，每步都是独立的一次模型请求；只要模型还在"每步调一次工具"，前缀差价就直接变成成本。
真正能赚的是"一次 `run_code` 包住多步子调用"，而 tutor 的状态机每步都被 `socratic_step` 切开，天然做不到。

## 6. 风险与副作用

- **1/10 失败**：t03 的 PTC 运行 `exit=1`（同一题 native 正常）。headless 下 PTC 的错误面更大，教学场景不可接受静默失败。
- **+23.6% 墙钟**：每题多 4.5 s，学生端可感知。
- 图片仍可用：`dsh-tools` 在 PTC 下把含 image 的工具结果转成 `deferredContext` 注入（`index.js:1453`），K5 页图链路不被 PTC 打断——这是唯一一条 PTC 的好消息。

## 7. 决策

| 项 | 决定 |
|---|---|
| `ptc_calc` 默认化 | **不默认**；保持试点工具 |
| tutor profile 开 PTC | **不开**；`DSH_TOOLS_MODE` 留空 |
| PTC 适用面 | 仅"一次程序包住多步计算"的场景，而且要看单题实测 |
| 下一步 | 转 B（ODL 表格 TEDS 金标） |

## 8. 复现

```powershell
cd D:\Guo-Code\socratic-tutor
# sidecar（另开窗口）
cd sidecar; ..\.venv-bge\Scripts\python.exe -m uvicorn app.main:app --port 8765
# 回仓库根：全部 10 题 × 2 模式
$env:ELECTRON_RUN_AS_NODE='1'
& 'D:\Program Files\dsh\DeepSeek Harness.exe' 'D:\Guo-Code\socratic-tutor\eval\p2\ptc\token_compare.mjs'
# 冒烟：前 2 题
$env:LIMIT='2'; & 'D:\Program Files\dsh\DeepSeek Harness.exe' '...\token_compare.mjs'
```

脚本从 `~/.dsh/.credentials.yaml` 取 `DEEPSEEK_API_KEY`，每题一个新 session，只统计 `status/step_end.usage`。
