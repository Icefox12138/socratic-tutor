// dsh-socratic-curriculum — the course layer of the Socratic tutor.
//
// The engine ships the curriculum *contract* (/v1/curriculum, docs/CURRICULUM-
// SCHEMA.md); this bundle is the thin host adapter that lets an agent see and
// follow it:
//
//   install tools + persona + curriculum -> course mode
//   install tools only                   -> free-form Q&A
//
// It contributes three tools and one hook:
//   curriculum_list     — the lesson catalogue in SOCRATIC_CURRICULUM
//   curriculum_lesson   — one lesson, vocabulary resolved against lexicon.db
//   curriculum_start    — bind a lesson to this session's state machine
//                         (/v1/state/init with learn=true, lesson=<id>)
//   agent/pre-step      — at the first step of each turn, inject the active
//                         lesson block so the model teaches the lesson, not the
//                         whole library
//
// "Active" means: bundle config `lesson`, or the lesson the sidecar state
// already carries (state.lesson, set by curriculum_start/socratic_init).
// With neither, the hook injects nothing and the bundle stays out of the way.

import { appendFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { degraded, get, post } from "./lib/transport.js";

const DEBUG = process.env.SOCRATIC_DEBUG === "1";
let LOG = null;
try {
  LOG = fileURLToPath(new URL("./curriculum.log", import.meta.url));
} catch { /* unreadable install path: logging simply stays off */ }

function log(event, data) {
  if (!DEBUG || !LOG) return;
  try {
    appendFileSync(LOG, JSON.stringify({ t: new Date().toISOString(), event, ...data }) + "\n");
  } catch { /* ignore */ }
}

export const name = "socratic-curriculum";
export const inject = ["tools"];

function sessionId(value) {
  const agent = value && value.agent;
  return String(agent?.session?.id || agent?.id || value?.turn?.sessionId || "default");
}

function text(value) {
  return [{ type: "text", text: typeof value === "string" ? value : JSON.stringify(value) }];
}

function clip(value, max) {
  const t = String(value || "").replace(/\s+/g, " ").trim();
  return t.length > max ? t.slice(0, max - 1) + "…" : t;
}

/** The lesson block injected into the step (exported for the tests). */
export function lessonText(lesson) {
  if (!lesson || !lesson.lesson_id) return "";
  const p = lesson.passage || {};
  const lines = [
    "【当前课】" + (lesson.title || lesson.lesson_id)
      + "（line=" + (lesson.line || "?") + "，unit " + (lesson.unit ?? "?")
      + " / lesson " + (lesson.lesson ?? "?") + "）",
    "选文：" + (p.source || "?") + " · " + (p.book || "?")
      + " · p." + (p.page_start ?? "?") + "–" + (p.page_end ?? "?"),
  ];
  if (lesson.background) lines.push("讲解：" + clip(lesson.background, 700));
  if (lesson.worked_example) lines.push("示例：" + clip(lesson.worked_example, 500));
  const vocab = (lesson.vocab || []).slice(0, 8)
    .map((v) => (v && v.gloss ? v.headword + "（" + v.gloss + "）" : v && v.headword))
    .filter(Boolean);
  if (vocab.length) lines.push("词表：" + vocab.join("、"));
  const grammar = (lesson.grammar || []).slice(0, 5)
    .map((g) => (g && g.section ? g.section + (g.note ? "（" + g.note + "）" : "") : ""))
    .filter(Boolean);
  if (grammar.length) lines.push("语法：" + grammar.join("；"));
  const questions = (lesson.questions || []).slice(0, 5)
    .map((q, i) => (q && q.q ? (i + 1) + ". " + q.q : "")).filter(Boolean);
  if (questions.length) lines.push("问题：\n" + questions.join("\n"));
  lines.push("用 curriculum_lesson 可重读本课；状态推进走 socratic_step；事实断言必须带页图 locator。");
  return lines.join("\n");
}

async function activeLesson(config, key) {
  const fixed = config && config.lesson;
  if (fixed) return String(fixed);
  try {
    const st = await get(config, "/v1/state/" + encodeURIComponent(key));
    if (st.ok && st.body && st.body.state && st.body.state.lesson) {
      return String(st.body.state.lesson);
    }
  } catch { /* sidecar down: no lesson, no injection */ }
  return "";
}

/**
 * The `agent/pre-step` listener: inject the active lesson at the first step of
 * each turn (later steps already have it in the transcript). Never mutates the
 * decision returned by `next()`.
 */
export function makePreStepHandler(config) {
  return async function curriculumPreStep(...args) {
    const payload = args[0] || {};
    const next = [...args].reverse().find((a) => typeof a === "function");
    if (typeof next !== "function") return undefined;
    // step > 1 means the lesson block is already in this turn's transcript
    if (payload.step != null && Number(payload.step) > 1) return next();

    let block = "";
    try {
      const key = sessionId(payload);
      const lessonId = await activeLesson(config, key);
      if (lessonId) {
        const res = await get(config, "/v1/curriculum/" + encodeURIComponent(lessonId),
          payload.signal);
        if (res.ok) block = lessonText(res.body);
      }
    } catch (e) {
      log("probe_error", { error: String(e && e.message || e) });
      block = "";
    }

    const decision = await next();
    if (!block || !decision || decision.kind !== "enter") return decision;
    const injected = {
      id: "curriculum-" + Date.now().toString(36) + "-"
        + Math.random().toString(36).slice(2, 8),
      role: "user",
      content: [{ type: "text", text: block }],
      source: {
        kind: "runtime-context",
        form: "snapshot",
        sections: [{ name: "socratic-curriculum", text: block }],
      },
    };
    log("inject", { key: sessionId(payload), step: payload.step, chars: block.length });
    return { ...decision, messages: [injected, ...decision.messages] };
  };
}

function tool(name, description, parameters, run) {
  return {
    name,
    description,
    parameters,
    output: { schema: { type: "string" }, render: (_args, value) => text(value) },
    async execute(args, exec) {
      try {
        return await run(args || {}, exec || {});
      } catch (e) {
        return degraded(name, e);
      }
    },
  };
}

export function apply(ctx, config) {
  const cfg = config || {};

  ctx.tools.register(tool(
    "curriculum_list",
    "列出课程包目录（line/unit/lesson 排序）；课程来自 sidecar 的 SOCRATIC_CURRICULUM 目录。",
    { type: "object", properties: {}, additionalProperties: false },
    async (_args, exec) => {
      const r = await get(cfg, "/v1/curriculum", exec.signal);
      if (!r.ok) return JSON.stringify({ ok: false, status: r.status, body: r.body });
      return JSON.stringify({ ok: true, ...r.body });
    },
  ));

  ctx.tools.register(tool(
    "curriculum_lesson",
    "读取一课：选文页范围、词表（已解析 lexicon 词条）、语法引用、讲解、示例、问题、复习卡。",
    {
      type: "object",
      properties: { lesson_id: { type: "string", description: "课程包里的 lesson_id" } },
      required: ["lesson_id"],
    },
    async (args, exec) => {
      const id = String(args.lesson_id || "").trim();
      if (!id) return JSON.stringify({ ok: false, error: "lesson_id_required" });
      const r = await get(cfg, "/v1/curriculum/" + encodeURIComponent(id), exec.signal);
      if (!r.ok) {
        return JSON.stringify({ ok: false, error: "lesson_not_found", lesson_id: id,
          status: r.status });
      }
      return JSON.stringify({ ok: true, lesson: r.body });
    },
  ));

  ctx.tools.register(tool(
    "curriculum_start",
    "把一课绑定到本会话：初始化状态机时带上 lesson 与 learn=true（预习阶段）；复习日传 review=true（REVIEW 开场）。"
      + "引擎会同步把该课 review_cards 导入 FSRS 复习队列（按 term 去重），结果见返回的 cards。",
    {
      type: "object",
      properties: {
        lesson_id: { type: "string" },
        goal: { type: "string", description: "本课目标（默认取课程标题）" },
        review: { type: "boolean", description: "是否从 REVIEW 阶段开场（到期复习卡）" },
      },
      required: ["lesson_id"],
    },
    async (args, exec) => {
      const id = String(args.lesson_id || "").trim();
      if (!id) return JSON.stringify({ ok: false, error: "lesson_id_required" });
      const lessonRes = await get(cfg, "/v1/curriculum/" + encodeURIComponent(id), exec.signal);
      if (!lessonRes.ok) {
        return JSON.stringify({ ok: false, error: "lesson_not_found", lesson_id: id,
          status: lessonRes.status });
      }
      const lesson = lessonRes.body;
      const key = sessionId(exec);
      const init = await post(cfg, "/v1/state/init", {
        session_id: key,
        goal: String(args.goal || lesson.title || id),
        concept: String(lesson.title || id),
        lang: String(args.lang || cfg.lang || "zh"),
        lesson: id,
        learn: true,
        review: Boolean(args.review),
      }, exec.signal);
      if (!init.ok) {
        return JSON.stringify({ ok: false, status: init.status, body: init.body,
          lesson_id: id });
      }
      return JSON.stringify({
        ok: true,
        session_id: key,
        lesson_id: id,
        state: init.body.state || null,
        summary: init.body.summary || "",
        // the engine imports the pack's review_cards; pass its report through
        cards: init.body.cards || null,
        lesson,
      });
    },
  ));

  ctx.on("agent/pre-step", makePreStepHandler(cfg));
  console.error("[dsh-socratic-curriculum] registered curriculum_list/curriculum_lesson/"
    + "curriculum_start + first-step lesson injection"
    + (cfg.lesson ? " (fixed lesson: " + cfg.lesson + ")" : ""));
}
