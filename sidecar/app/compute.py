"""Safe-ish symbolic computation endpoint (expression only, no arbitrary code)."""
import re
from concurrent.futures import ThreadPoolExecutor

import sympy as sp

_POOL = ThreadPoolExecutor(max_workers=2)
_BAD = ("__", "import", "open(", "eval(", "exec(", "lambda", "os.", "sys.", "subprocess")
_ALLOWED = {"simplify", "diff", "integrate", "solve", "limit", "value", "latex", "factor", "expand"}


class ComputeError(ValueError):
    pass


def _locals(var: str):
    return {
        var: sp.Symbol(var),
        "x": sp.Symbol("x"),
        "y": sp.Symbol("y"),
        "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
        "exp": sp.exp, "log": sp.log, "sqrt": sp.sqrt,
        "pi": sp.pi, "E": sp.E, "oo": sp.oo, "I": sp.I,
    }


def _run(expr: str, op: str, var: str, point: str):
    local = _locals(var)
    e = sp.sympify(expr.replace("^", "**"), locals=local)
    sym = local[var]
    if op == "simplify":
        r = sp.simplify(e)
    elif op == "diff":
        r = sp.diff(e, sym)
    elif op == "integrate":
        r = sp.integrate(e, sym)
    elif op == "solve":
        r = sp.solve(e, sym)
    elif op == "limit":
        r = sp.limit(e, sym, sp.sympify(point, locals=local))
    elif op == "value":
        r = sp.N(e)
    elif op == "latex":
        r = e
    elif op == "factor":
        r = sp.factor(e)
    elif op == "expand":
        r = sp.expand(e)
    else:
        raise ComputeError(f"unknown operation {op}")
    return r


def compute(expression: str, operation: str = "simplify",
            variable: str = "x", point: str = "0", timeout: float = 8.0):
    expression = (expression or "").strip()
    if not expression or len(expression) > 300:
        raise ComputeError("expression must be 1..300 chars")
    low = expression.lower()
    if any(b in low for b in _BAD):
        raise ComputeError("expression contains a forbidden token")
    if operation not in _ALLOWED:
        raise ComputeError(f"operation must be one of {sorted(_ALLOWED)}")
    if not re.fullmatch(r"[A-Za-z]", variable or ""):
        raise ComputeError("variable must be one letter")
    fut = _POOL.submit(_run, expression, operation, variable, point)
    try:
        result = fut.result(timeout=timeout)
    except TimeoutError:
        raise ComputeError("computation timed out")
    except Exception as e:
        raise ComputeError(str(e))
    try:
        latex = sp.latex(result)
    except Exception:
        latex = ""
    return {
        "ok": True,
        "operation": operation,
        "input": expression,
        "variable": variable,
        "result": str(result),
        "latex": latex,
    }
