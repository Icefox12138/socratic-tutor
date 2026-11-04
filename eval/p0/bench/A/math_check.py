import json
import os

import sympy as sp

x = sp.symbols("x")
checks = [
    ("d sin(x)/x", sp.diff(sp.sin(x) / x, x), sp.cos(x)/x - sp.sin(x)/x**2),
    ("lim sin(x)/x", sp.limit(sp.sin(x)/x, x, 0), 1),
    ("d x^2", sp.diff(x**2, x), 2*x),
    ("int x^2", sp.integrate(x**2, x), x**3/3),
    ("lim x*sin(1/x)", sp.limit(x*sp.sin(1/x), x, sp.oo), 1),
    ("solve x^2-5x+6", set(sp.solve(x**2 - 5*x + 6, x)), {2, 3}),
    ("det 2x2", sp.Matrix([[1, 2], [3, 4]]).det(), -2),
    ("inverse 2x2", sp.Matrix([[1, 2], [3, 4]]).inv(), sp.Matrix([[-2, 1], [sp.Rational(3, 2), -sp.Rational(1, 2)]])),
    ("series sin", sp.series(sp.sin(x), x, 0, 6).removeO(), x - x**3/6 + x**5/120),
    ("d tan(x)", sp.diff(sp.tan(x), x), sp.sec(x)**2),
]

rows = []
ok = 0
for name, got, want in checks:
    try:
        good = sp.simplify(got - want) == 0 if not isinstance(want, (set, sp.Matrix)) else got == want
    except Exception:
        good = got == want
    ok += 1 if good else 0
    rows.append({"name": name, "ok": bool(good), "got": str(got)[:80]})

out = {"passed": ok, "total": len(checks), "rows": rows}
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "A-math.json")
json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("passed", ok, "/", len(checks))
