# P2-8 PTC 试点

> **2026-11-03 注**：本文 §0 的"原生 `run_code` 未注入"已过期——DSH 已升到 0.2.1-rc.5，`ptc` preset 与 `ptc-runtime` 随包出货，headless 用 `DSH_TOOLS_MODE=ptc` 即可。token 结论见 `P2-9-PTC-token.md`（不达标，不默认）。

| 项 | 值 |
|---|---|
| 日期 | 2026-11-02 |
| PTC 实现 | `plugin-socratic/ptc.js` + `ptc_calc` 工具 |
| 试点 | 10 道理工题，直接调用 vs PTC |
| 结果 | 正确 **10/10**；逃逸 **0**；PTC 平均 5 ms，直接 21 ms |
| 结论 | 可用；但 token 节省未达标验证；**不是 DSH 原生 `run_code`** |

## 0. DSH 原生 PTC 探针

- DSH 0.2.1-rc.3 **保留了 `run_code`**，注册同名工具会报：
  `tool name "run_code" is reserved for the PTC mode presentation transport`；
- 包里存在 `@deepseek-ai/dsh-ptc-runtime` / `dsh-ptc-runtime-node`，但它们**没有 `dsh.bundle`**，直接加到 profile 的 bundles 会被跳过；
- 当前 profile 没有 PTC preset/runtime，`ctx.tools.presentAs("ptc")` 不会让模型看到 `run_code`；
- 因此本试点用 **`ptc_calc`** 作为自建 PTC 门面（模型写代码、程序化调工具），不是原生 transport；
- headless 已验证：模型调用 `ptc_calc`，日志 `ptc_run ok=true calls=1`；
- 用户切换 PTC 模式后，`dsh --profile tutor headless` 仍只列出 `ptc_calc`，没有 `run_code`；原生 token 对比仍无法在 CLI 完成（可能只在 GUI preset 生效）。

## 1. 实现

`ptc_calc(code)` 用 Node `vm` 创建沙箱，只暴露：

```js
compute_symbolic(expression, operation, variable, point)
compute_numeric(expression, variable)
unit_check(...)   // 占位，未接 pint
cite_verify(...)  // 占位，PTC 不开放
console.log(...)
```

护栏：

- 代码长度 ≤ 4000；
- 禁止 `require/process/fetch/import()/WebAssembly/globalThis/Function/eval`；
- 禁止 `Math.random`/`Date.now`/`new Date`（可复现）；
- `vm` timeout 8 s；
- 输出上限 4000 字符；
- 子调用写 `pre-step.log` 的 `ptc_run` 事件（仅 `SOCRATIC_DEBUG=1`）。

工具在插件中注册为 `ptc_calc`；模型可直接调用，也可由多步任务使用。

## 2. 10 题结果

| # | 任务 | 直接 | PTC | 一致 |
|---:|---|---|---|---|
| 1 | diff x³ | 3*x**2 | 3*x**2 | ✅ |
| 2 | integrate x² | x**3/3 | x**3/3 | ✅ |
| 3 | solve x²-4 | [-2, 2] | [-2, 2] | ✅ |
| 4 | limit sin(x)/x | 1 | 1 | ✅ |
| 5 | simplify (x²-1)/(x-1) | x+1 | x+1 | ✅ |
| 6 | diff+value | 2.0*x | 2.0*x | ✅ |
| 7 | integrate+diff | 2*x | 2*x | ✅ |
| 8 | solve 2x+3=7 | [2] | [2] | ✅ |
| 9 | identity | 1 | 1 | ✅ |
| 10 | latex | x**2+1 | x**2+1 | ✅ |

正确率 **10/10**，`ptc-results.json` 可复现。

## 3. 沙箱逃逸测试

| 攻击 | 结果 |
|---|---|
| `process.exit(1)` | 拒绝（banned） |
| `require('fs')` | 拒绝 |
| `await fetch(...)` | 拒绝 |
| `globalThis.process` | 拒绝 |
| `Function('return process')()` | 拒绝 |
| `while(true){}` | 8 s 超时 |

逃逸 **0**。`answer_key` 不在 PTC 门面中，泄漏 **0**。

## 4. 延迟

| 方式 | 平均 |
|---|---:|
| 直接工具调用 | 21 ms |
| PTC | 5 ms |

PTC 更快是因为连接复用/暖缓存，不是通用结论；真实模型调用还要加代码生成 token。

## 5. 未达标/限制

- **token 节省 ≥30% 未验证**：单步题 PTC 代码比直接调用更长；只有多步题才可能省；
- **不是 DSH 原生 `run_code`**，是本插件自建 `ptc_calc`；原生 PTC 需要 PTC runtime/preset；
- `unit_check`/`cite_verify` 是占位，未接 pint/页图；
- 无 artifact 落盘，大结果只截断；
- 审计只在 debug 日志，未写独立 `tool/ptc-dispatch` 表；
- 没有随机种子接口（直接禁止随机）。

## 6. 结论

P2-8 **条件通过**：

- 正确性、逃逸、answer_key 达标；
- 延迟达标；
- 可复现达标；
- **token 节省未达标验证**；
- 建议保留 `run_code` 作为“多步计算”可选工具，默认仍直接调用；等 DSH 原生 PTC 再评估 token。
