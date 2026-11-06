# 计算后端交接（2026-11-06）

| 项 | 值 |
|---|---|
| 范围 | SymPy / SciPy / pint / control / Wolfram / Lean 的统一后端 |
| 状态 | **SymPy + SciPy + pint + control 可用；Wolfram/Lean 未安装** |
| 测试 | sidecar **264/264**（新增 17 个计算/沙箱测试） |
| 安全 | 本地后端在可 kill 子进程；**仅 audit 策略沙箱**（禁 socket/子进程，只写 temp） |
| 凭证 | `credentials` + `verification` + `cross_check` + `disputed` + `sandbox` |

---

## 1. 可用性（本机实测）

| backend | 可用 | 版本/路径 | 操作 |
|---|---|---|---|
| sympy | ✅ | 1.13.1 | simplify/diff/integrate/solve/limit/value/latex/factor/expand |
| scipy | ✅ | 1.18.1 | quad/minimize/root |
| pint | ✅ | 0.26.2 | convert |
| control | ✅ | 0.10.2 | step |
| wolfram | ❌ | 无 `wolframscript` | eval |
| lean | ❌ | 无 `lean`/`lake` | check |

`GET /v1/compute/backends` 返回完整状态与安装提示。

## 2. API

```http
POST /v1/compute
{"expression":"x^2","operation":"quad","point":"0","target":"1","backend":"scipy"}
-> {"ok":true,"backend":"scipy","engine_version":"1.18.1",
    "result":0.333...,"latex":"x^{2}","numeric":0.333...,
    "verification":{"method":"quad_error","ok":true,"error":...},
    "cross_check":{"backend":"sympy","value":0.333...,"difference":...},
    "disputed":false,
    "sandbox":"audit",
    "credentials":{"backend":"scipy","input_sha256":"...","assumptions":{...},
                   "verification":{...},"sandbox":"audit","generated_at":"..."}}
```

- `backend=auto` 按 operation 推断；
- `pint`：`expression="3 m"`, `operation="convert"`, `target="ft"`；
- `control`：`operation="step"`, `data={"num":[1],"den":[1,2,1]}`；
- `wolfram`：`operation="eval"`，需 `wolframscript` + `SOCRATIC_COMPUTE_EXTERNAL=1`；
- `lean`：`operation="check"`，需 `lean`/`lake` + 同一开关。

错误：
- 400：未知 operation/backend、表达式非法、计算失败；
- 503：`{"code":"backend_unavailable","detail":...,"backends":...}`。

## 3. 实现

- `compute.py`：
  - SymPy 保留原 9 个操作；
  - SciPy `quad`/`minimize`/`root`，用 SymPy 解析 + lambdify；
  - pint 单位换算；
  - control 一阶/二阶传函 step_info；
  - Wolfram/Lean 子进程 adapter，超时与输出截断；
  - 表达式黑名单 + 长度限制；`point/target` 也校验。
- **子进程 worker**（`compute_worker.py`）：
  - SymPy/SciPy/pint/control 全部在子进程执行；
  - 父进程 `Popen` + 临时文件通信（不走 pipe），超时 `kill()`；
  - worker 崩溃/超时不会拖垮 sidecar；
  - **不是 OS 沙箱**：仍有文件/网络权限，只保证可 kill。
- **沙箱（仅 audit）**：
  - `sandbox_policy.py` 在 worker 里安装审计钩子；
  - 拒绝 socket/子进程，只允许写 per-run 临时目录；
  - 这是 Python 层拦截，不是 OS 网络命名空间/只读挂载；
  - 已移除 Windows AppContainer 代码；`credentials.sandbox` 固定为 `audit`
    （Wolfram/Lean 走外部进程时标 `external`）。
- **计算凭证**：
  - `credentials.input_sha256`、`assumptions`、`verification`、`generated_at`；
  - SciPy `quad` 会用 SymPy 积分做 cross-check，超差标 `disputed=true`；
  - 其它后端目前只做自检（符号/优化器收敛/单位注册/step_info）。
- `main.py`：`/v1/compute/backends` + `ComputeIn.backend/target/data`。
- 插件 `compute_math`：新增 backend/target/data，operation 枚举扩展。
- `pyproject.toml`：主依赖加 `scipy`；可选 `compute = [pint, control]`。

## 4. 安全边界

1. audit 策略沙箱是 Python 层拦截，不是 OS 网络命名空间/只读挂载。
2. SymPy/SciPy/pint 仍是表达式黑名单，不是形式化安全边界。
3. Wolfram/Lean 执行外部代码，默认关闭；打开后仍是本机权限。
4. Lean adapter 假设 `lean file.lean`；若用 `lake env lean` 需要再适配。
5. SciPy `root` 需要 bracket 内变号；失败会返回 400。
6. `disputed` 目前只在 SciPy quad 的 SymPy cross-check 上生效。
7. 子进程每次启动约 0.3–1.2 s（control 导入 matplotlib 较慢）。

## 5. 复现

```powershell
cd sidecar
python -m unittest tests.test_compute tests.test_sandbox_policy -v
```

## 6. 下一步

1. 安装 `pint`/`control` 并跑真实单位换算、step 响应。
2. 若要 Wolfram/Lean：装 Engine/Lean 4 + Mathlib，做 20 题基准与超时/并发测试。
3. 把 SymPy/SciPy 移到子进程沙箱（可 kill），解决线程超时问题。
4. 计算凭证字段（`assumptions/verification`）与“SymPy vs Wolfram 不一致标 disputed”。
