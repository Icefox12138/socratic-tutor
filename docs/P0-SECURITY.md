# P0 安全攻击测试报告

| 项 | 值 |
|---|---|
| 日期 | 2026-11-02 |
| 范围 | sidecar 7 个攻击面（6 类 + 伪造 token） |
| 脚本 | `eval/p0/security/run_security.py` |
| 结果 | **7/7 拦截** |
| 结论 | 本地最小服务可过基础安全门；生产仍需限流/审计 |

## 1. 结果

| # | 攻击 | 结果 |
|---:|---|---|
| 1 | 越权 `view=answer_key` | 400 |
| 2 | 无 token 访问检索 | 401 |
| 3 | 伪造 `X-Sidecar-Token` | 401 |
| 4 | 路径穿越 `book=../../Windows/win.ini` | 404，非 PNG |
| 5 | 代码注入 `__import__('os')` | 400 |
| 6 | 资源耗尽（超长表达式） | 400 |
| 7 | 跨会话状态读取 | s1=200，s2=404 |

测试用独立 auth sidecar（8766，`SOCRATIC_REQUIRE_AUTH=1`），不动 8765。

## 2. 已实现的护栏

- `view` 只接受 `student|tutor`，`answer_key` 直接 400；
- 页图 `book` 解析后做根目录 `commonpath` 校验；
- 计算只接受 SymPy 表达式 + 操作白名单，拒绝 `__import__/exec/eval/...`，长度 ≤300；
- token 可选；`SOCRATIC_REQUIRE_AUTH=1` 时无 token 配置返回 503，错误 token 401；
- 状态按 session 隔离，未知 session 404。

## 3. 未覆盖 / 限制

- 没有速率限制、审计日志、HTTPS；
- token 是单静态密钥，不是用户级身份；
- 跨会话“隔离”是 API 404，不是所有权模型；同一 token 可读所有 session；
- 资源耗尽只测超长表达式，未测复杂 SymPy 表达式 CPU 时间；
- 未测提示注入（模型层）和工具结果伪造；
- 未测并发/竞态。

## 4. 产物

`security-results.json`（7/7 true）、`run_security.py`。
