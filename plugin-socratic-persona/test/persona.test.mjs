// Contract tests for the teaching layer: charter, stream rewrite, pre-step summary.
import assert from "node:assert/strict";
import { test, beforeEach } from "node:test";

import {
  apply, charterText, DEFAULT_SUMMARY, makePreStepHandler, makeStreamHandler,
} from "../index.js";
import { rewrites, streamMode } from "../lib/stream-mode.js";

function downFetch() {
  globalThis.fetch = async () => { throw new Error("ECONNREFUSED 127.0.0.1:8765"); };
}

function upFetch(bodies) {
  globalThis.fetch = async (url) => {
    const path = String(url).replace("http://127.0.0.1:8765", "");
    const body = bodies[path.split("?")[0]] || {};
    return { ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) };
  };
}

beforeEach(() => { downFetch(); });

// ── registration ─────────────────────────────────────────────────────────────

test("apply registers the charter, the pre-step hook and the stream hook", () => {
  const listeners = [];
  const sections = [];
  const ctx = {
    on(event) { listeners.push(event); },
    systemPrompt: { section(section) { sections.push(section); } },
    tools: { register() { throw new Error("persona must not register tools"); } },
  };
  apply(ctx, { baseUrl: "http://127.0.0.1:8765" });
  assert.deepEqual(listeners.sort(), ["agent/pre-step", "llm/stream"]);
  assert.equal(sections.length, 1);
  assert.equal(sections[0].name, "socratic:charter");
  assert.equal(sections[0].order, 120);
  assert.equal(sections[0].text, charterText());
});

// ── charter ──────────────────────────────────────────────────────────────────

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

// ── stream switch ────────────────────────────────────────────────────────────

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

// ── stream rewriting ─────────────────────────────────────────────────────────

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

// ── pre-step summary ─────────────────────────────────────────────────────────

test("the pre-step handler falls back to a local summary when the sidecar is down", async () => {
  downFetch();
  const handler = makePreStepHandler({ baseUrl: "http://127.0.0.1:8765" });
  const res = await handler({ agent: { session: { id: "s-1" } } },
    async () => ({ kind: "enter", messages: [{ role: "assistant", content: [] }] }));
  assert.equal(res.messages.length, 2);
  const injected = res.messages[0];
  assert.equal(injected.source.kind, "runtime-context");
  assert.equal(injected.content[0].text, DEFAULT_SUMMARY);
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

test("the pre-step handler returns a new decision and leaves a frozen one alone", async () => {
  downFetch();
  const handler = makePreStepHandler({ baseUrl: "http://127.0.0.1:8765" });
  const messages = Object.freeze([]);
  const decision = Object.freeze({ kind: "enter", messages, startsRequestSeries: true });
  // `agent.id` is the only identity DSH 0.2.2's Agent interface guarantees.
  const out = await handler({ agent: { id: "s-4" } }, async () => decision);
  assert.notEqual(out, decision, "must not reuse the decision object");
  assert.equal(out.kind, "enter");
  assert.equal(out.startsRequestSeries, true, "spread keeps the other fields");
  assert.equal(out.messages.length, 1);
  assert.equal(decision.messages.length, 0, "the input must not be mutated");
});
