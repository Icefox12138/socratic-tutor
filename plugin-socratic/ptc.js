import vm from "node:vm";

const MAX_CODE = 4000;
const MAX_OUT = 4000;
const BANNED = [
  /\brequire\s*\(/,
  /\bprocess\b/,
  /\bfetch\s*\(/,
  /\bimport\s*\(/,
  /\bWebAssembly\b/,
  /\bglobalThis\b/,
  /\bFunction\s*\(/,
  /\beval\s*\(/,
  /\bthis\s*\.\s*constructor\b/,
  /Math\s*\.\s*random/,
  /Date\s*\.\s*now/,
  /new\s+Date\b/,
];

function safeString(v) {
  try {
    return typeof v === "string" ? v : JSON.stringify(v);
  } catch {
    return String(v);
  }
}

async function post(config, path, body, signal) {
  const base = (config && config.baseUrl) || process.env.SOCRATIC_SIDECAR_URL || "http://127.0.0.1:8765";
  const token = (config && config.token) || process.env.SOCRATIC_TOKEN || "";
  const headers = { "Content-Type": "application/json" };
  if (token) headers["X-Sidecar-Token"] = token;
  const res = await fetch(base.replace(/\/$/, "") + path, {
    method: "POST", headers, body: JSON.stringify(body), signal,
  });
  let data;
  try { data = await res.json(); } catch { data = { raw: "non-json" }; }
  if (!res.ok) throw new Error(`sidecar ${res.status}: ${safeString(data).slice(0, 300)}`);
  return data;
}

export async function runCode(code, opts = {}) {
  const src = String(code || "");
  if (!src.trim()) return { ok: false, error: "empty code" };
  if (src.length > MAX_CODE) return { ok: false, error: "code too long" };
  const bad = BANNED.find((r) => r.test(src));
  if (bad) return { ok: false, error: "banned construct: " + String(bad) };

  const calls = [];
  const logs = [];
  const compute = async (expression, operation = "simplify", variable = "x", point = "0") => {
    calls.push({ op: operation, expression: String(expression).slice(0, 120) });
    return post(opts.config, "/v1/compute", {
      expression: String(expression), operation: String(operation),
      variable: String(variable || "x"), point: String(point || "0"),
    }, opts.signal);
  };
  const sandbox = {
    compute_symbolic: compute,
    compute_numeric: (expression, variable = "x") => compute(expression, "value", variable),
    unit_check: async () => ({ ok: false, error: "unit_check not configured" }),
    cite_verify: async () => ({ ok: false, error: "cite_verify is not available in PTC" }),
    console: { log: (...a) => logs.push(a.map(safeString).join(" ")) },
    JSON,
    Math: Object.create(Math),
    Number,
    String,
    Boolean,
    Array,
    Object,
    Promise,
  };
  let result;
  try {
    const wrapped = `(async () => { ${src}\n })()`;
    const fn = vm.runInNewContext(wrapped, sandbox, {
      timeout: 8000,
      codeGeneration: { strings: false, wasm: false },
    });
    result = await fn;
  } catch (e) {
    return { ok: false, error: String(e && e.message || e), calls, logs };
  }
  const text = safeString(result);
  return {
    ok: true,
    result: text.length > MAX_OUT ? text.slice(0, MAX_OUT) + "...[truncated]" : text,
    calls,
    logs: logs.slice(0, 20),
  };
}
