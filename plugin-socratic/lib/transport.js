// Transport + health for a Socratic sidecar.
//
// Everything here is contract, not domain: base URL, token, session id, and a
// cached reachability probe. The domain plugin (tools, charter, streaming
// hooks) imports these so the wire format lives in one file - see
// docs/SIDECAR-CONTRACT.md.

export function settings(config) {
  return {
    base: (config && config.baseUrl) || process.env.SOCRATIC_SIDECAR_URL || "http://127.0.0.1:8765",
    token: (config && config.token) || process.env.SOCRATIC_TOKEN || "",
  };
}

function headers(config, extra) {
  const { token } = settings(config);
  const h = { ...(extra || {}) };
  if (token) h["X-Sidecar-Token"] = token;
  return h;
}

function url(config, path) {
  return settings(config).base.replace(/\/$/, "") + path;
}

export async function call(config, path, options = {}) {
  const res = await fetch(url(config, path), {
    ...options,
    headers: headers(config, options.headers),
  });
  const text = await res.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    body = { raw: text.slice(0, 2000) };
  }
  return { ok: res.ok, status: res.status, body };
}

export async function callBinary(config, path, options = {}) {
  const res = await fetch(url(config, path), {
    ...options,
    headers: headers(config, options.headers),
  });
  if (!res.ok) return { ok: false, status: res.status, bytes: 0 };
  const buf = await res.arrayBuffer();
  return { ok: true, status: res.status, bytes: buf.byteLength };
}

let cache = { at: 0, up: false, base: "", detail: "" };

export function reset() {
  cache = { at: 0, up: false, base: "", detail: "" };
}

/** Cached reachability probe: one /health per TTL, not one per tool call. */
export async function probe(config, opts = {}) {
  const ttl = opts.ttlMs == null ? 5000 : opts.ttlMs;
  const timeout = opts.timeoutMs == null ? 1500 : opts.timeoutMs;
  const now = Date.now();
  const { base } = settings(config);
  if (cache.base === base && now - cache.at < ttl) return { ...cache };
  let up = false;
  let detail = "";
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    const res = await fetch(base.replace(/\/$/, "") + "/health", { signal: ctrl.signal });
    clearTimeout(timer);
    up = res.ok;
    detail = "HTTP " + res.status;
  } catch (e) {
    detail = String((e && e.message) || e).slice(0, 160);
  }
  cache = { at: now, up, base, detail };
  return { ...cache };
}

/** Structured "can't run without the sidecar" result (never a thrown error). */
export function degraded(toolName, health) {
  return JSON.stringify({
    ok: false,
    error: "sidecar_unreachable",
    tool: toolName,
    base: health.base,
    detail: health.detail,
    hint: "启动 sidecar（python -m uvicorn app.main:app --port 8765 --timeout-keep-alive 75），或把 baseUrl/SOCRATIC_SIDECAR_URL 指到已运行的实例。",
  });
}
