// Contract tests for the course layer: tools, lesson block, pre-step injection.
import assert from "node:assert/strict";
import { test, beforeEach } from "node:test";

import { apply, lessonText, makePreStepHandler } from "../index.js";

const BASE = "http://127.0.0.1:8765";

const LESSON = {
  schema: 1,
  lesson_id: "demo-public-01",
  line: "demo",
  title: "公版样张第一课",
  unit: 1,
  lesson: 1,
  passage: { source: "demo-public", book: "public-demo.pdf", page_start: 1, page_end: 2 },
  background: "这一课演示课程包的形状。",
  worked_example: "先讲一个例子，再请学习者回讲。",
  vocab: [{ headword: "arma", lang: "latin", gloss: "武器" },
    { headword: "μῆνιν", lang: "greek", gloss: "愤怒" }],
  grammar: [{ scheme: "grammar", section: "§419", note: "独立夺格" }],
  questions: [{ q: "第 1 页的标题是什么？" }, { q: "举例说明引用如何核实。" }],
  review_cards: [{ term: "arma", definition: "武器" }],
};

function stub(map) {
  const calls = [];
  globalThis.fetch = async (url, opts = {}) => {
    const path = String(url).replace(/^https?:\/\/[^/]+/, "");
    calls.push({ path, opts });
    for (const [prefix, value] of Object.entries(map)) {
      if (path.startsWith(prefix)) {
        const status = value.__status || 200;
        return {
          ok: status < 400,
          status,
          text: async () => JSON.stringify(value),
          json: async () => value,
        };
      }
    }
    return { ok: false, status: 404, text: async () => "{}", json: async () => ({}) };
  };
  return calls;
}

function down() {
  globalThis.fetch = async () => { throw new Error("ECONNREFUSED 127.0.0.1:8765"); };
}

beforeEach(() => { down(); });

function makeCtx() {
  const tools = [];
  const events = {};
  return {
    tools,
    events,
    ctx: {
      tools: { register(definition) { tools.push(definition); } },
      on(event, handler) { events[event] = handler; },
    },
  };
}

// ── registration ─────────────────────────────────────────────────────────────

test("apply registers three tools and the pre-step hook", () => {
  const { tools, events, ctx } = makeCtx();
  apply(ctx, { baseUrl: BASE });
  assert.deepEqual(tools.map((t) => t.name).sort(),
    ["curriculum_lesson", "curriculum_list", "curriculum_start"]);
  assert.equal(typeof events["agent/pre-step"], "function");
  for (const t of tools) {
    assert.equal(t.output.schema.type, "string");
    assert.equal(typeof t.execute, "function");
  }
});

// ── tools ────────────────────────────────────────────────────────────────────

test("curriculum_list returns the catalogue and sends the token", async () => {
  const { tools, ctx } = makeCtx();
  const calls = stub({ "/v1/curriculum": { schema: 1, lessons: [{ lesson_id: "a" }] } });
  apply(ctx, { baseUrl: BASE, token: "secret" });
  const out = JSON.parse(await tools[0].execute({}, {}));
  assert.equal(out.ok, true);
  assert.deepEqual(out.lessons, [{ lesson_id: "a" }]);
  assert.equal(calls[0].opts.headers["X-Sidecar-Token"], "secret");
});

test("curriculum_lesson reports a missing lesson without throwing", async () => {
  const { tools, ctx } = makeCtx();
  stub({ "/v1/curriculum/absent": { __status: 404 } });
  apply(ctx, { baseUrl: BASE });
  const lesson = tools.find((t) => t.name === "curriculum_lesson");
  const out = JSON.parse(await lesson.execute({ lesson_id: "absent" }, {}));
  assert.equal(out.ok, false);
  assert.equal(out.error, "lesson_not_found");
});

test("curriculum_start binds the lesson with learn=true", async () => {
  const { tools, ctx } = makeCtx();
  const calls = stub({
    "/v1/curriculum/demo-public-01": LESSON,
    "/v1/state/init": { state: { phase: "ALIGN", lesson: "demo-public-01" },
      summary: "【状态摘要】阶段=ALIGN；课=demo-public-01；",
      cards: { added: [{ id: 1, term: "arma" }], skipped: 0 } },
  });
  apply(ctx, { baseUrl: BASE });
  const start = tools.find((t) => t.name === "curriculum_start");
  const out = JSON.parse(await start.execute({ lesson_id: "demo-public-01" }, {}));
  assert.equal(out.ok, true);
  assert.equal(out.state.phase, "ALIGN");
  assert.deepEqual(out.cards, { added: [{ id: 1, term: "arma" }], skipped: 0 });
  const initCall = calls.find((c) => c.path.startsWith("/v1/state/init"));
  const body = JSON.parse(initCall.opts.body);
  assert.equal(body.lesson, "demo-public-01");
  assert.equal(body.learn, true);
  assert.equal(body.session_id, "default");
  assert.equal(body.concept, LESSON.title);
});

test("a tool without a sidecar answers sidecar_unreachable", async () => {
  const { tools, ctx } = makeCtx();
  apply(ctx, { baseUrl: BASE });
  const list = tools.find((t) => t.name === "curriculum_list");
  const out = JSON.parse(await list.execute({}, {}));
  assert.equal(out.ok, false);
  assert.equal(out.error, "sidecar_unreachable");
});

// ── lesson block ─────────────────────────────────────────────────────────────

test("lessonText carries title, page range, vocab, grammar and questions", () => {
  const text = lessonText(LESSON);
  for (const needle of ["【当前课】", LESSON.title, "p.1–2", "arma（武器）",
    "§419（独立夺格）", "第 1 页的标题是什么？", "curriculum_lesson"]) {
    assert.ok(text.includes(needle), "lesson block lost " + needle);
  }
  assert.equal(lessonText(null), "");
});

// ── pre-step injection ───────────────────────────────────────────────────────

function preStepPayload(step) {
  return { agent: { id: "s1" }, messages: [], turn: 1, step, signal: undefined };
}

function enterDecision() {
  return { kind: "enter", messages: [{ role: "user", content: [{ type: "text", text: "hi" }] }] };
}

test("the first step of a turn injects the active lesson", async () => {
  const handler = makePreStepHandler({ baseUrl: BASE });
  stub({
    "/v1/state/s1": { state: { lesson: "demo-public-01" }, summary: "x" },
    "/v1/curriculum/demo-public-01": LESSON,
  });
  const out = await handler(preStepPayload(1), async () => enterDecision());
  assert.equal(out.messages.length, 2);
  const injected = out.messages[0];
  assert.ok(injected.id.startsWith("curriculum-"));
  assert.equal(injected.source.kind, "runtime-context");
  assert.equal(injected.source.sections[0].name, "socratic-curriculum");
  assert.ok(injected.content[0].text.includes(LESSON.title));
  assert.deepEqual(out.messages[1], enterDecision().messages[0]);
});

test("later steps and lessons-less sessions pass through untouched", async () => {
  const handler = makePreStepHandler({ baseUrl: BASE });
  let calls = stub({ "/v1/state/s1": { state: { lesson: "demo-public-01" },
    summary: "x" } });
  const step2 = await handler(preStepPayload(2), async () => enterDecision());
  assert.equal(step2.messages.length, 1);
  assert.equal(calls.length, 0, "step 2 must not call the sidecar");

  calls = stub({ "/v1/state/s1": { state: {}, summary: "x" } });
  const noLesson = await handler(preStepPayload(1), async () => enterDecision());
  assert.equal(noLesson.messages.length, 1);
});

test("config.lesson fixes the lesson without reading session state", async () => {
  const handler = makePreStepHandler({ baseUrl: BASE, lesson: "demo-public-01" });
  const calls = stub({ "/v1/curriculum/demo-public-01": LESSON });
  const out = await handler(preStepPayload(1), async () => enterDecision());
  assert.ok(out.messages[0].content[0].text.includes(LESSON.title));
  assert.equal(calls.some((c) => c.path.startsWith("/v1/state/")), false);
});

test("a rejected step is left rejected", async () => {
  const handler = makePreStepHandler({ baseUrl: BASE, lesson: "demo-public-01" });
  stub({ "/v1/curriculum/demo-public-01": LESSON });
  const out = await handler(preStepPayload(1), async () => ({ kind: "reject" }));
  assert.deepEqual(out, { kind: "reject" });
});
