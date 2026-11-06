"""Computation backends: SymPy (symbolic), SciPy (numeric), optional
pint/control/Wolfram/Lean.

The endpoint is intentionally expression/data oriented; it never executes
arbitrary Python. External backends (Wolfram/Lean) are disabled unless
``SOCRATIC_COMPUTE_EXTERNAL=1`` and are reported as unavailable otherwise.
"""
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

import sympy as sp

_POOL = ThreadPoolExecutor(max_workers=2)
_BAD = ("__", "import", "open(", "eval(", "exec(", "lambda", "os.", "sys.",
        "subprocess", "socket", "ctypes")
_SYMPY_OPS = {"simplify", "diff", "integrate", "solve", "limit", "value",
              "latex", "factor", "expand"}
_SCIPY_OPS = {"quad", "minimize", "root"}
_PINT_OPS = {"convert"}
_CONTROL_OPS = {"step"}
_EXTERNAL_OPS = {"eval", "check"}


class ComputeError(ValueError):
    pass


class BackendUnavailable(ComputeError):
    pass


def _module(name):
    if name == "control":
        # matplotlib (a control dependency) defaults to a non-writable
        # AppData cache under the sandbox; point it at the workspace.
        os.environ.setdefault("MPLBACKEND", "Agg")
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        cache = os.path.join(root, ".tmp-mpl")
        try:
            os.makedirs(cache, exist_ok=True)
            os.environ.setdefault("MPLCONFIGDIR", cache)
        except OSError:
            pass
    if importlib.util.find_spec(name) is None:
        return None
    try:
        return __import__(name)
    except Exception:
        return None


def _version(module):
    return str(getattr(module, "__version__", "?")) if module else None


def _external_enabled():
    return str(os.environ.get("SOCRATIC_COMPUTE_EXTERNAL", "0")).lower() in (
        "1", "true", "yes")


def _which(names):
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def backend_status():
    scipy = _module("scipy")
    pint = _module("pint")
    control = _module("control")
    wolfram = _which(("wolframscript", "WolframKernel"))
    lean = _which(("lean", "lake"))
    external = _external_enabled()
    return {
        "sympy": {"available": True, "version": _version(sp),
                  "operations": sorted(_SYMPY_OPS)},
        "scipy": {"available": bool(scipy), "version": _version(scipy),
                  "operations": sorted(_SCIPY_OPS)},
        "pint": {"available": bool(pint), "version": _version(pint),
                 "operations": sorted(_PINT_OPS),
                 "install": "pip install pint"},
        "control": {"available": bool(control), "version": _version(control),
                    "operations": sorted(_CONTROL_OPS),
                    "install": "pip install control"},
        "wolfram": {"available": bool(wolfram and external),
                    "path": wolfram, "version": None,
                    "external_enabled": external,
                    "operations": ["eval"],
                    "install": "Wolfram Engine + wolframscript"},
        "lean": {"available": bool(lean and external),
                 "path": lean, "version": None,
                 "external_enabled": external,
                 "operations": ["check"],
                 "install": "Lean 4 + lake"},
    }


def _validate(expression, length=300):
    expression = (expression or "").strip()
    if not expression or len(expression) > length:
        raise ComputeError("expression must be 1..%d chars" % length)
    low = expression.lower()
    if any(b in low for b in _BAD):
        raise ComputeError("expression contains a forbidden token")
    return expression


def _locals(var):
    return {
        var: sp.Symbol(var),
        "x": sp.Symbol("x"),
        "y": sp.Symbol("y"),
        "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
        "exp": sp.exp, "log": sp.log, "sqrt": sp.sqrt,
        "pi": sp.pi, "E": sp.E, "oo": sp.oo, "I": sp.I,
    }


def _sympy_run(expr, op, var, point):
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
        raise ComputeError("unknown operation %s" % op)
    return r


def _sympy(expr, op, var, point, timeout):
    if op not in _SYMPY_OPS:
        raise ComputeError("sympy operation must be one of %s" % sorted(_SYMPY_OPS))
    fut = _POOL.submit(_sympy_run, expr, op, var, point)
    try:
        result = fut.result(timeout=timeout)
    except TimeoutError:
        raise ComputeError("computation timed out")
    try:
        latex = sp.latex(result)
    except Exception:
        latex = ""
    return {"result": str(result), "latex": latex, "numeric": None}


def _scipy_func(expr, var):
    local = _locals(var)
    e = sp.sympify(expr.replace("^", "**"), locals=local)
    return sp.lambdify(local[var], e, "numpy"), e, local[var]


def _scipy(expr, op, var, point, target, timeout):
    scipy = _module("scipy")
    if scipy is None:
        raise BackendUnavailable("scipy is not installed")
    if op not in _SCIPY_OPS:
        raise ComputeError("scipy operation must be one of %s" % sorted(_SCIPY_OPS))
    f, e, sym = _scipy_func(expr, var)
    try:
        if op == "quad":
            from scipy.integrate import quad
            lo = float(sp.sympify(point).evalf())
            hi = float(sp.sympify(target or "1").evalf())
            value, err = quad(lambda x: float(f(x)), lo, hi)
            cross = None
            try:
                exact = float(sp.N(sp.integrate(e, (sym, lo, hi))))
                cross = {"backend": "sympy", "value": exact,
                         "difference": abs(exact - value)}
            except Exception:
                cross = None
            disputed = bool(cross and cross["difference"] > max(
                1e-6, 1e-6 * abs(cross["value"])))
            return {"result": value, "latex": sp.latex(e), "numeric": value,
                    "details": {"lower": lo, "upper": hi, "error": err},
                    "cross_check": cross, "disputed": disputed}
        if op == "minimize":
            from scipy.optimize import minimize
            x0 = float(sp.sympify(point or "0").evalf())
            res = minimize(lambda x: float(f(x[0])), [x0])
            return {"result": float(res.x[0]), "latex": sp.latex(e),
                    "numeric": float(res.fun),
                    "details": {"success": bool(res.success),
                                "iterations": int(res.nit)}}
        if op == "root":
            from scipy.optimize import root_scalar
            lo = float(sp.sympify(point or "0").evalf())
            hi = float(sp.sympify(target or "1").evalf())
            res = root_scalar(lambda x: float(f(x)), bracket=(lo, hi))
            return {"result": float(res.root), "latex": sp.latex(e),
                    "numeric": 0.0,
                    "details": {"converged": bool(res.converged),
                                "bracket": [lo, hi]}}
    except ComputeError:
        raise
    except Exception as e:
        raise ComputeError(str(e))
    raise ComputeError("unknown scipy operation")


def _pint(expr, op, target, timeout):
    pint = _module("pint")
    if pint is None:
        raise BackendUnavailable("pint is not installed; pip install pint")
    if op != "convert":
        raise ComputeError("pint operation must be convert")
    if not target:
        raise ComputeError("target unit is required for convert")
    if not re.fullmatch(r"[0-9A-Za-z .,*/^()_+-]+", expr):
        raise ComputeError("unit expression contains invalid characters")
    try:
        ureg = pint.UnitRegistry()
        value = ureg(expr)
        out = value.to(target)
        return {"result": str(out), "latex": "",
                "numeric": float(out.magnitude),
                "details": {"magnitude": float(out.magnitude),
                            "units": str(out.units)}}
    except Exception as e:
        raise ComputeError(str(e))


def _control(data, op, timeout):
    control = _module("control")
    if control is None:
        raise BackendUnavailable("control is not installed; pip install control")
    if op != "step":
        raise ComputeError("control operation must be step")
    data = data or {}
    num, den = data.get("num"), data.get("den")
    if (not isinstance(num, list) or not isinstance(den, list)
            or not num or not den
            or not all(isinstance(x, (int, float)) for x in num + den)):
        raise ComputeError("control step needs data.num and data.den number lists")
    try:
        sys = control.TransferFunction(num, den)
        tf = control.step_info(sys)
        return {"result": str(sys), "latex": "",
                "numeric": float(tf.get("SteadyStateValue", 0.0)),
                "details": {k: (float(v) if isinstance(v, (int, float)) else v)
                            for k, v in tf.items()}}
    except Exception as e:
        raise ComputeError(str(e))


def _wolfram(expr, op, timeout):
    if not _external_enabled():
        raise BackendUnavailable("external backends disabled; set SOCRATIC_COMPUTE_EXTERNAL=1")
    exe = _which(("wolframscript", "WolframKernel"))
    if not exe:
        raise BackendUnavailable("Wolfram Engine/wolframscript not found")
    if op != "eval":
        raise ComputeError("wolfram operation must be eval")
    if len(expr) > 2000:
        raise ComputeError("wolfram expression too long")
    try:
        proc = subprocess.run([exe, "-code", expr], capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ComputeError("wolfram computation timed out")
    except Exception as e:
        raise ComputeError(str(e))
    out = (proc.stdout or "").strip()
    if proc.returncode != 0 and not out:
        raise ComputeError((proc.stderr or "wolfram failed").strip()[:300])
    return {"result": out, "latex": "", "numeric": None,
            "details": {"returncode": proc.returncode}}


def _lean(code, op, timeout):
    if not _external_enabled():
        raise BackendUnavailable("external backends disabled; set SOCRATIC_COMPUTE_EXTERNAL=1")
    exe = _which(("lean", "lake"))
    if not exe:
        raise BackendUnavailable("Lean 4/lake not found")
    if op != "check":
        raise ComputeError("lean operation must be check")
    if len(code) > 5000:
        raise ComputeError("lean code too long")
    fd, path = tempfile.mkstemp(suffix=".lean")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(code)
        try:
            proc = subprocess.run([exe, path], capture_output=True, text=True,
                                  timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ComputeError("lean check timed out")
        return {"result": "ok" if proc.returncode == 0 else "failed",
                "latex": "", "numeric": None,
                "details": {"returncode": proc.returncode,
                            "stdout": (proc.stdout or "")[:1000],
                            "stderr": (proc.stderr or "")[:1000]}}
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _execute_local(backend, expression, operation, variable="x", point="0",
                   target=None, data=None, timeout=8.0):
    """Run a local backend in-process (used inside the killed worker)."""
    if backend in ("sympy", "scipy", "pint"):
        expression = _validate(expression)
    if backend in ("sympy", "scipy"):
        point = _validate(point, 100)
        if target:
            target = _validate(target, 100)
    if backend == "sympy":
        if not re.fullmatch(r"[A-Za-z]", variable or ""):
            raise ComputeError("variable must be one letter")
        return _sympy(expression, operation, variable, point, timeout)
    if backend == "scipy":
        if not re.fullmatch(r"[A-Za-z]", variable or ""):
            raise ComputeError("variable must be one letter")
        return _scipy(expression, operation, variable, point, target, timeout)
    if backend == "pint":
        return _pint(expression, operation, target, timeout)
    if backend == "control":
        return _control(data, operation, timeout)
    if backend == "wolfram":
        return _wolfram(expression, operation, timeout)
    if backend == "lean":
        return _lean(expression, operation, timeout)
    raise ComputeError("unknown backend %s" % backend)


_LAST_SANDBOX = "process"


def _sandbox_mode():
    return str(os.environ.get("SOCRATIC_COMPUTE_SANDBOX", "auto")).lower()


def _run_worker(payload, timeout):
    global _LAST_SANDBOX
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sandbox_root = os.path.join(root, ".tmp-sandbox")
    try:
        os.makedirs(sandbox_root, exist_ok=True)
    except OSError:
        sandbox_root = tempfile.gettempdir()
    td = os.path.join(sandbox_root, "run-%d-%d" % (os.getpid(), time.time_ns()))
    try:
        os.makedirs(td)
    except OSError:
        td = tempfile.mkdtemp(prefix="socratic-compute-")
    inp = os.path.join(td, "in.json")
    outp = os.path.join(td, "out.json")
    errp = os.path.join(td, "err.txt")
    try:
        with open(inp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        env = os.environ.copy()
        env["PYTHONPATH"] = root + os.pathsep + env.get("PYTHONPATH", "")
        env["SOCRATIC_SANDBOX_TEMP"] = td
        env["TMP"] = env["TEMP"] = env["TMPDIR"] = td
        env["MPLCONFIGDIR"] = os.path.join(td, "mpl")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        mode = _sandbox_mode()
        if mode in ("auto", "appcontainer"):
            try:
                from . import sandbox
                if sandbox.status().get("available"):
                    state, code = sandbox.run_worker(
                        sys.executable, "app.compute_worker", inp, outp,
                        root, timeout, td)
                    _LAST_SANDBOX = "appcontainer"
                    if state == "timeout":
                        raise ComputeError("computation timed out")
                    if code != 0:
                        raise ComputeError("AppContainer worker failed: %s" % code)
                else:
                    _LAST_SANDBOX = "audit"
            except ComputeError:
                raise
            except Exception:
                _LAST_SANDBOX = "audit"
        else:
            _LAST_SANDBOX = "audit"
        if _LAST_SANDBOX == "audit":
            with open(errp, "w", encoding="utf-8") as err:
                proc = subprocess.Popen(
                    [sys.executable, "-m", "app.compute_worker", inp, outp],
                    cwd=root, stdout=subprocess.DEVNULL, stderr=err, env=env)
                try:
                    proc.wait(timeout=max(0.5, float(timeout)))
                except subprocess.TimeoutExpired:
                    proc.kill()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        pass
                    raise ComputeError("computation timed out")
        if not os.path.exists(outp):
            with open(errp, encoding="utf-8") as fh:
                detail = fh.read().strip()[:300]
            raise ComputeError("compute worker failed: %s" % (detail or "no output"))
        with open(outp, encoding="utf-8") as fh:
            body = json.load(fh)
        if not body.get("ok"):
            if body.get("kind") == "unavailable":
                raise BackendUnavailable(body.get("error", "backend unavailable"))
            raise ComputeError(body.get("error", "computation failed"))
        return body["out"]
    finally:
        try:
            shutil.rmtree(td, ignore_errors=True)
        except Exception:
            pass


def _assumptions(backend, variable, point, target, data):
    if backend == "sympy":
        return {"variable": variable, "domain": "complex"}
    if backend == "scipy":
        return {"variable": variable, "lower": point, "upper": target}
    if backend == "pint":
        return {"target_unit": target}
    if backend == "control":
        return {"num": (data or {}).get("num"), "den": (data or {}).get("den")}
    return {"external": True}


def _verification(backend, out):
    details = out.get("details") or {}
    if backend == "sympy":
        return {"method": "symbolic", "ok": True}
    if backend == "scipy":
        if "error" in details:
            return {"method": "quad_error", "ok": details["error"] < 1e-6,
                    "error": details["error"]}
        if "success" in details:
            return {"method": "optimizer_success", "ok": bool(details["success"])}
        if "converged" in details:
            return {"method": "root_converged", "ok": bool(details["converged"])}
        return {"method": "scipy", "ok": True}
    if backend == "pint":
        return {"method": "unit_registry", "ok": True}
    if backend == "control":
        return {"method": "step_info", "ok": "SteadyStateValue" in details}
    if backend in ("wolfram", "lean"):
        return {"method": "%s_run" % backend,
                "ok": (details.get("returncode") == 0)}
    return {"method": backend, "ok": True}


def compute(expression: str, operation: str = "simplify",
            variable: str = "x", point: str = "0", timeout: float = 8.0,
            backend: str = "auto", target: str | None = None,
            data: dict | None = None):
    t0 = time.perf_counter()
    status = backend_status()
    backend = (backend or "auto").lower()
    if backend == "auto":
        if operation in _SYMPY_OPS:
            backend = "sympy"
        elif operation in _SCIPY_OPS:
            backend = "scipy"
        elif operation in _PINT_OPS:
            backend = "pint"
        elif operation in _CONTROL_OPS:
            backend = "control"
        elif operation in _EXTERNAL_OPS:
            backend = "wolfram" if operation == "eval" else "lean"
        else:
            raise ComputeError("cannot infer backend for operation %s" % operation)
    if backend not in status:
        raise ComputeError("unknown backend %s" % backend)
    timeout = min(max(float(timeout), 0.1), 60.0)
    payload = {"backend": backend, "expression": expression,
               "operation": operation, "variable": variable, "point": point,
               "target": target, "data": data, "timeout": timeout}
    if backend in ("sympy", "scipy", "pint", "control"):
        out = _run_worker(payload, timeout)
    else:
        out = _execute_local(**payload)
    disputed = bool(out.get("disputed"))
    credentials = {
        "backend": backend,
        "engine_version": status[backend].get("version"),
        "input_sha256": hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
        "operation": operation,
        "assumptions": _assumptions(backend, variable, point, target, data),
        "verification": _verification(backend, out),
        "cross_check": out.get("cross_check"),
        "disputed": disputed,
        "sandbox": "external" if backend in ("wolfram", "lean") else _LAST_SANDBOX,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return {
        "ok": True,
        "backend": backend,
        "engine_version": status[backend].get("version"),
        "operation": operation,
        "input": expression,
        "variable": variable,
        "result": out["result"],
        "latex": out.get("latex", ""),
        "numeric": out.get("numeric"),
        "details": out.get("details"),
        "verification": credentials["verification"],
        "assumptions": credentials["assumptions"],
        "cross_check": credentials["cross_check"],
        "disputed": disputed,
        "sandbox": credentials["sandbox"],
        "credentials": credentials,
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
