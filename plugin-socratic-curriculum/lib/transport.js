// Wire helpers for the curriculum bundle: base URL, token, GET/POST.
//
// Deliberately tiny and dependency-free: the curriculum layer only talks to
// /v1/state/{id} and /v1/curriculum*, so it carries its own three functions
// instead of importing the tools bundle (a bundle must stay installable alone).

export function settings(config) {
  const env = process.env;
  return {
    base: String((config && config.baseUrl) || env.SOCRATIC_SIDECAR_URL
      || "http://127.0.0.1:8765").replace(/\/+$/, ""),
    token: String((config && config.token) || env.SOCRATIC_TOKEN || ""),
  };
}

function headers(config, extra) {
  const h = { ...(extra || {}) };
  const { token } = settings(config);
  if (token) h["X-Sidecar-Token"] = token;
  return h;
}

function url(config, path) {
  return settings(config).base + path;
}

async function parse(res) {
  const text = await res.text();
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    body = { raw: text.slice(0, 2000) };
  }
  return { ok: res.ok, status: res.status, body };
}

export async function get(config, path, signal) {
  return parse(await fetch(url(config, path), { headers: headers(config), signal }));
}

export async function post(config, path, payload, signal) {
  return parse(await fetch(url(config, path), {
    method: "POST",
    headers: headers(config, { "Content-Type": "application/json" }),
    body: JSON.stringify(payload || {}),
    signal,
  }));
}

/** Structured "can't run without the sidecar" result (never a thrown error). */
export function degraded(toolName, error) {
  const { base } = settings({});
  return JSON.stringify({
    ok: false,
    error: "sidecar_unreachable",
    tool: toolName,
    base,
    detail: String((error && error.message) || error).slice(0, 160),
    hint: "启动 sidecar（uvx --from socratic-sidecar socratic-sidecar --data <数据根>），"
      + "或把 baseUrl/SOCRATIC_SIDECAR_URL 指到已运行的实例。",
  });
}
