// Contract tests: the plugin must degrade, not crash, when no sidecar is up.
import assert from "node:assert/strict";
import { test, beforeEach } from "node:test";

import { apply, charterText, makePreStepHandler, makeStreamHandler } from "../index.js";
import { reset } from "../lib/transport.js";
import { rewrites, streamMode } from "../lib/stream-mode.js";

function harness(baseUrl, config = {}) {
  const tools = [];
  const listeners = [];
  const sections = [];
  const ctx = {
    on(event) { listeners.push(event); },
    systemPrompt: { section(section) { sections.push(section && section.name); } },
    tools: { register(t) { tools.push(t); } },
  };
  apply(ctx, { baseUrl, ...config });
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

test("stream switch defaults to buffered rewriting", () => {
  assert.equal(streamMode({}), "buffer");
  assert.equal(rewrites({}), true);
});

test("stream switch opts into passthrough", () => {
  assert.equal(streamMode({ SOCRATIC_STREAM: "stream" }), "stream");
  assert.equal(rewrites({ SOCRATIC_STREAM: "stream" }), false);
});

test("unknown stream values fall back to buffer", () => {
  assert.equal(streamMode({ SOCRATIC_STREAM: "whatever" }), "buffer");
  assert.equal(streamMode({ SOCRATIC_STREAM: "STREAM" }), "stream");
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

test("the teaching persona is on by default", () => {
  const { listeners, sections } = harness("http://127.0.0.1:8765");
  assert.deepEqual(sections, ["socratic:charter"]);
  assert.ok(listeners.includes("agent/pre-step"), listeners.join(","));
  assert.ok(listeners.includes("llm/stream"), listeners.join(","));
});

test("persona:false keeps the tools and drops every teaching behaviour", () => {
  const { tools, listeners, sections } = harness("http://127.0.0.1:8765", { persona: false });
  assert.equal(tools.length, 13);
  assert.deepEqual(sections, []);
  assert.deepEqual(listeners, []);
});

test("persona:true behaves like the default", () => {
  const { listeners, sections } = harness("http://127.0.0.1:8765", { persona: true });
  assert.deepEqual(sections, ["socratic:charter"]);
  assert.ok(listeners.includes("agent/pre-step"));
});

test("persona:false still answers tool calls", async () => {
  upFetch({ "/v1/search": { ok: true, mode: "fts", results: [] } });
  const { byName } = harness("http://127.0.0.1:8765", { persona: false });
  const out = JSON.parse(await byName.kb_search.execute({ query: "x" }, {}));
  assert.equal(out.mode, "fts");
});

// ── the three handlers, testable without a live session ──────────────────────

test("the charter keeps ten rules and the locator requirement", () => {
  const lines = charterText().split("\n");
  assert.equal(lines.length, 12, "intro + 规则： + 10 rules");
  for (let i = 1; i <= 10; i += 1) {
    assert.ok(lines.some((l) => l.startsWith(i + ") ")), "missing rule " + i);
  }
  const all = charterText();
  for (const needle of ["L4", "kb_search", "answer_key", "locator", "socratic_init"]) {
    assert.ok(all.includes(needle), "charter lost " + needle);
  }
});

test("the stream handler forwards streams with no teaching tool", () => {
  const handler = makeStreamHandler(() => true);
  const sentinel = { untouched: true };
  assert.equal(handler({ tools: [{ name: "read" }] }, () => sentinel), sentinel);
  assert.equal(handler({}, () => sentinel), sentinel);
});

test("the stream handler softens an uncited factual sentence", async () => {
  const handler = makeStreamHandler(() => true);
  const sentence = "牛顿第二定律表明力等于质量乘以加速度。";
  const src = (async function* () {
    yield { type: "text-delta", index: 0, text: sentence };
    yield { type: "block-end", index: 0, block: { type: "text", text: sentence } };
  })();
  const chunks = [];
  for await (const c of handler({ tools: [{ name: "kb_search" }] }, () => src)) {
    chunks.push(c);
  }
  const joined = chunks.filter((c) => c.type === "text-delta").map((c) => c.text).join("");
  assert.ok(!joined.includes("等于质量"), joined);
  assert.ok(joined.includes("尚未核验"), joined);
});

test("the stream handler leaves a cited sentence alone", async () => {
  const handler = makeStreamHandler(() => true);
  const sentence = "极限的定义见 p.12。";
  const src = (async function* () {
    yield { type: "text-delta", index: 0, text: sentence };
  })();
  const chunks = [];
  for await (const c of handler({ tools: [{ name: "kb_search" }] }, () => src)) {
    chunks.push(c);
  }
  assert.equal(chunks[0].text, sentence);
});

test("the stream handler passes through when rewriting is off", async () => {
  const handler = makeStreamHandler(() => false);
  const src = (async function* () { yield { type: "text-delta", index: 0, text: "无引用断言。" }; })();
  const chunks = [];
  for await (const c of handler({ tools: [{ name: "kb_search" }] }, () => src)) {
    chunks.push(c);
  }
  assert.equal(chunks[0].text, "无引用断言。");
});

test("the pre-step handler falls back to a local summary when the sidecar is down", async () => {
  downFetch();
  const handler = makePreStepHandler({ baseUrl: "http://127.0.0.1:8765" });
  const res = await handler({ agent: { session: { id: "s-1" } } },
    async () => ({ kind: "enter", messages: [{ role: "assistant", content: [] }] }));
  assert.equal(res.messages.length, 2);
  const injected = res.messages[0];
  assert.equal(injected.source.kind, "runtime-context");
  assert.match(injected.content[0].text, /阶段=ALIGN/);
});

test("the pre-step handler uses the sidecar summary when it answers", async () => {
  upFetch({ "/v1/state/s-2": { summary: "【状态摘要】阶段=DIAGNOSE；" } });
  const handler = makePreStepHandler({ baseUrl: "http://127.0.0.1:8765" });
  const res = await handler({ agent: { session: { id: "s-2" } } },
    async () => ({ kind: "enter", messages: [] }));
  assert.equal(res.messages[0].content[0].text, "【状态摘要】阶段=DIAGNOSE；");
});

test("the pre-step handler ignores a call without a next function", async () => {
  const handler = makePreStepHandler({});
  assert.equal(await handler({ agent: { session: { id: "s-3" } } }), undefined);
});
