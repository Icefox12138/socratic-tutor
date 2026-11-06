// Contract tests for the tools bundle: it must degrade, not crash, without a sidecar.
import assert from "node:assert/strict";
import { test, beforeEach } from "node:test";

import { apply } from "../index.js";
import { reset } from "../lib/transport.js";

function harness(baseUrl) {
  const tools = [];
  const listeners = [];
  const sections = [];
  const ctx = {
    on(event) { listeners.push(event); },
    systemPrompt: { section(section) { sections.push(section && section.name); } },
    tools: { register(t) { tools.push(t); } },
  };
  apply(ctx, { baseUrl });
  const byName = Object.fromEntries(tools.map((t) => [t.name, t]));
  return { tools, byName, listeners, sections };
}

function downFetch() {
  globalThis.fetch = async () => { throw new Error("ECONNREFUSED 127.0.0.1:8765"); };
}

function upFetch(bodies) {
  globalThis.fetch = async (url) => {
    const path = String(url).replace("http://127.0.0.1:8765", "");
    const body = bodies[path.split("?")[0]] || {};
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify(body),
      arrayBuffer: async () => new ArrayBuffer(3),
    };
  };
}

beforeEach(() => { reset(); });

test("registers the full tool surface", () => {
  const { tools } = harness("http://127.0.0.1:8765");
  const names = tools.map((t) => t.name).sort();
  for (const want of ["kb_search", "kb_read", "lexical_search", "chapter_lookup",
    "cite_verify", "compute_math", "ptc_calc", "review_session",
    "socratic_critic", "socratic_health", "socratic_init", "socratic_state",
    "socratic_step"]) {
    assert.ok(names.includes(want), "missing " + want);
  }
  assert.equal(tools.length, 13);
});

test("the tools bundle registers no teaching behaviour", () => {
  const { listeners, sections } = harness("http://127.0.0.1:8765");
  assert.deepEqual(listeners, [], "tools must not hook llm/stream or agent/pre-step");
  assert.deepEqual(sections, [], "tools must not add a system-prompt section");
});

test("a tool returns a structured error when the sidecar is down", async () => {
  downFetch();
  const { byName } = harness("http://127.0.0.1:8765");
  const out = JSON.parse(await byName.kb_search.execute({ query: "导数" }, {}));
  assert.equal(out.ok, false);
  assert.equal(out.error, "sidecar_unreachable");
  assert.equal(out.tool, "kb_search");
  assert.match(out.hint, /sidecar/);
});

test("socratic_health still answers when the sidecar is down", async () => {
  downFetch();
  const { byName } = harness("http://127.0.0.1:8765");
  const out = JSON.parse(await byName.socratic_health.execute({}, {}));
  assert.equal(out.reachable, false);
});

test("tools pass through when the sidecar is up", async () => {
  upFetch({ "/v1/search": { ok: true, mode: "fts", results: [{ chunk_id: 1 }] } });
  const { byName } = harness("http://127.0.0.1:8765");
  const out = JSON.parse(await byName.kb_search.execute({ query: "导数" }, {}));
  assert.equal(out.mode, "fts");
  assert.equal(out.results.length, 1);
});

test("baseUrl override is honoured", async () => {
  const seen = [];
  globalThis.fetch = async (url) => {
    seen.push(String(url));
    return { ok: true, status: 200, text: async () => "{}", arrayBuffer: async () => new ArrayBuffer(1) };
  };
  const { byName } = harness("http://example.test:9999");
  await byName.kb_search.execute({ query: "x" }, {});
  assert.ok(seen.some((u) => u.startsWith("http://example.test:9999/health")), seen.join(","));
  assert.ok(seen.some((u) => u.startsWith("http://example.test:9999/v1/search")), seen.join(","));
});
