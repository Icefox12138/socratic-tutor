import { writeFileSync } from "node:fs";
import { runCode } from "../../../plugin-socratic/ptc.js";

const BASE = "http://127.0.0.1:8765";

async function compute(expression, operation, variable = "x", point = "0") {
  const res = await fetch(BASE + "/v1/compute", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ expression, operation, variable, point }),
  });
  return { status: res.status, body: await res.json() };
}

const tasks = [
  ["diff", "x**3", "diff", "x", "0"],
  ["integrate", "x**2", "integrate", "x", "0"],
  ["solve", "x**2-4", "solve", "x", "0"],
  ["limit", "sin(x)/x", "limit", "x", "0"],
  ["simplify", "(x**2-1)/(x-1)", "simplify", "x", "0"],
  ["diff+value", "x**2", "diff+value", "x", "2"],
  ["integrate+diff", "2*x", "integrate+diff", "x", "0"],
  ["solve-linear", "2*x+3-7", "solve", "x", "0"],
  ["identity", "sin(x)**2+cos(x)**2", "simplify", "x", "0"],
  ["latex", "x**2+1", "latex", "x", "0"],
];

const ptc = {
  "diff": "return (await compute_symbolic('x**3','diff','x')).result;",
  "integrate": "return (await compute_symbolic('x**2','integrate','x')).result;",
  "solve": "return (await compute_symbolic('x**2-4','solve','x')).result;",
  "limit": "return (await compute_symbolic('sin(x)/x','limit','x','0')).result;",
  "simplify": "return (await compute_symbolic('(x**2-1)/(x-1)','simplify','x')).result;",
  "diff+value": "const d=await compute_symbolic('x**2','diff','x'); return (await compute_symbolic(d.result,'value','x','2')).result;",
  "integrate+diff": "const i=await compute_symbolic('2*x','integrate','x'); return (await compute_symbolic(i.result,'diff','x')).result;",
  "solve-linear": "return (await compute_symbolic('2*x+3-7','solve','x')).result;",
  "identity": "return (await compute_symbolic('sin(x)**2+cos(x)**2','simplify','x')).result;",
  "latex": "return (await compute_symbolic('x**2+1','latex','x')).result;",
};

async function direct(task) {
  const [, expr, op, v, p] = task;
  if (op === "diff+value") {
    const d = await compute(expr, "diff", v, p);
    const val = await compute(d.body.result, "value", v, p);
    return { result: val.body.result, calls: [d, val] };
  }
  if (op === "integrate+diff") {
    const i = await compute(expr, "integrate", v, p);
    const d = await compute(i.body.result, "diff", v, p);
    return { result: d.body.result, calls: [i, d] };
  }
  const r = await compute(expr, op, v, p);
  return { result: r.body.result, calls: [r] };
}

const rows = [];
for (const t of tasks) {
  const name = t[0];
  const t0 = performance.now();
  const d = await direct(t);
  const t1 = performance.now();
  const p = await runCode(ptc[name], { config: {} });
  const t2 = performance.now();
  const pv = p.ok ? p.result : p.error;
  const same = p.ok && String(pv).replace(/\s/g, "") === String(d.result).replace(/\s/g, "");
  rows.push({ name, direct: d.result, ptc: pv,
    same, direct_ms: Math.round(t1 - t0), ptc_ms: Math.round(t2 - t1),
    ptc_calls: p.calls?.length || 0 });
  console.log(name, same, d.result, "|", pv);
}

const escapes = [];
for (const code of ["process.exit(1)", "require('fs')", "await fetch('http://example.com')",
  "globalThis.process", "Function('return process')()", "while(true){}"]) {
  const r = await runCode(code, { config: {} });
  escapes.push({ code: code.slice(0, 40), ok: r.ok, error: r.error || "" });
}

const summary = {
  tasks: rows.length,
  correct: rows.filter((r) => r.same).length,
  avg_direct_ms: Math.round(rows.reduce((s, r) => s + r.direct_ms, 0) / rows.length),
  avg_ptc_ms: Math.round(rows.reduce((s, r) => s + r.ptc_ms, 0) / rows.length),
  escapes,
  escape_ok: escapes.filter((e) => e.ok).length,
  rows,
};
writeFileSync(new URL("./ptc-results.json", import.meta.url), JSON.stringify(summary, null, 1));
console.log(JSON.stringify({ correct: summary.correct, n: summary.tasks,
  avg_direct_ms: summary.avg_direct_ms, avg_ptc_ms: summary.avg_ptc_ms,
  escape_ok: summary.escape_ok }, null, 1));
