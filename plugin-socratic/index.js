import { appendFileSync } from "node:fs";
import { runCode } from "./ptc.js";
import { call, callBinary, degraded, probe, settings } from "./lib/transport.js";

const DEFAULT_BASE = "http://127.0.0.1:8765";
const LOG = "D:/Guo-Code/socratic-tutor/plugin-socratic/pre-step.log";
const DEBUG = process.env.SOCRATIC_DEBUG === "1";

function log(event, data) {
  if (!DEBUG) return;
  try {
    appendFileSync(LOG, JSON.stringify({ t: new Date().toISOString(), event, ...data }) + "\n");
  } catch { /* ignore */ }
}

export const name = "socratic-teacher";
export const inject = ["tools"];

function sessionId(obj) {
  const a = obj && obj.agent;
  return String(a?.session?.id || a?.id || obj?.turn?.sessionId || "default");
}

function text(value) {
  return [{ type: "text", text: typeof value === "string" ? value : JSON.stringify(value) }];
}

let activeConfig = null;

function tool(name, description, parameters, run, opts = {}) {
  return {
    name,
    description,
    parameters,
    output: { schema: { type: "string" }, render: (_args, value) => text(value) },
    async execute(args, exec) {
      try {
        // Decoupling seam: every tool that speaks to the sidecar checks the
        // contract's /health first, so a missing service yields one structured
        // error instead of a stack trace per tool.
        if (opts.needsSidecar !== false && activeConfig !== null) {
          const health = await probe(activeConfig);
          if (!health.up) return degraded(name, health);
        }
        return await run(args || {}, exec);
      } catch (e) {
        return JSON.stringify({ ok: false, error: String(e && e.message || e) });
      }
    },
  };
}

export function apply(ctx, config) {
  activeConfig = config || {};
  ctx.tools.register(tool(
    "kb_search",
    "检索馆藏/Steadman/公开语料片段，返回 citation（页图或原文 URL）；事实断言前必须调用。",
    {
      type: "object",
      properties: {
        query: { type: "string" },
        view: { type: "string", enum: ["student", "tutor"] },
        limit: { type: "integer", minimum: 1, maximum: 12 },
        source: { type: "string" },
        lang: { type: "string" },
        book: { type: "string", description: "限定书目（侧栏书键，如 library 下相对路径；v2 也接受 document_id）" },
        chapter: { type: "string", description: "限定章回：'卷3' / '第7回' / 标题片段" },
        document_id: { type: "string", description: "v2：限定文档，如 wikisource:zh:史記/卷001" },
        section: { type: "string", description: "v2：限定章节标题" },
        scope: { type: "string", enum: ["auto", "all", "routed"], description: "all = 同时检索 v1+v2；routed = 按语言/覆盖路由到一个库" },
      },
      required: ["query"],
    },
    async (args, exec) => {
      const q = new URLSearchParams({
        q: String(args.query || ""),
        view: String(args.view || "student"),
        limit: String(args.limit || 8),
      });
      if (args.source) q.set("source", String(args.source));
      if (args.lang) q.set("lang", String(args.lang));
      if (args.book) q.set("book", String(args.book));
      if (args.scope === "all" || args.scope === "routed") q.set("scope", args.scope);
      if (args.chapter) q.set("chapter", String(args.chapter));
      if (args.document_id) q.set("document_id", String(args.document_id));
      if (args.section) q.set("section", String(args.section));
      const sid = sessionId(exec);
      if (sid) q.set("session_id", sid);
      const phase = exec && exec.agent && exec.agent.phase;
      if (phase && phase.turn != null) q.set("turn", String(phase.turn));
      if (phase && phase.step != null) q.set("step", String(phase.step));
      if (exec && exec.callId) q.set("call_id", String(exec.callId));
      const r = await call(config, "/v1/search?" + q.toString(), { signal: exec?.signal });
      return JSON.stringify(r.body);
    },
  ));

  ctx.tools.register(tool(
    "chapter_lookup",
    "按 '卷3' / '第7回' / 标题片段查章回页码范围与页图；给 page 则返回该页所在章回。",
    {
      type: "object",
      properties: {
        book: { type: "string" },
        chapter: { type: "string" },
        page: { type: "integer", minimum: 1 },
        source: { type: "string" },
      },
      required: ["book"],
    },
    async (args, exec) => {
      const q = new URLSearchParams({ book: String(args.book) });
      if (args.source) q.set("source", String(args.source));
      if (args.chapter) q.set("q", String(args.chapter));
      if (args.page) q.set("page", String(args.page));
      const r = await call(config, "/v1/chapter?" + q.toString(), { signal: exec?.signal });
      return JSON.stringify(r.body);
    },
  ));

  ctx.tools.register(tool(
    "kb_read",
    "按 chunk_id 读取单个片段（含 citation）。",
    {
      type: "object",
      properties: {
        chunk_id: { type: "integer" },
        view: { type: "string", enum: ["student", "tutor"] },
      },
      required: ["chunk_id"],
    },
    async (args, exec) => {
      const view = String(args.view || "student");
      const r = await call(config, `/v1/chunks/${Number(args.chunk_id)}?view=${encodeURIComponent(view)}`,
        { signal: exec?.signal });
      return JSON.stringify(r.body);
    },
  ));

  ctx.tools.register(tool(
    "lexical_search",
    "精确串（grep）或词形归并（lemma）检索；用于引文、人名、公式、代码标识符的精确核验。" +
      "grep 支持 v1/v2；lemma 只支持 v2 干净文本。",
    {
      type: "object",
      properties: {
        query: { type: "string" },
        mode: { type: "string", enum: ["grep", "lemma"] },
        view: { type: "string", enum: ["student", "tutor"] },
        limit: { type: "integer", minimum: 1, maximum: 50 },
        source: { type: "string" },
        lang: { type: "string" },
        book: { type: "string" },
        document_id: { type: "string" },
        section: { type: "string" },
      },
      required: ["query"],
    },
    async (args, exec) => {
      const mode = args.mode === "lemma" ? "lemma" : "grep";
      const q = new URLSearchParams({
        q: String(args.query || ""),
        view: String(args.view || "student"),
        limit: String(args.limit || 20),
      });
      for (const key of ["source", "lang", "book", "document_id", "section"]) {
        if (args[key]) q.set(key, String(args[key]));
      }
      const r = await call(config, `/v1/${mode}?` + q.toString(),
        { signal: exec?.signal });
      return JSON.stringify(r.body);
    },
  ));

  ctx.tools.register(tool(
    "cite_verify",
    "核验引用。v1：book+page+quote 按页内文本比对，或不给 quote 取页图；" +
      "v2：document_id+quote（可加 section/revision）按文档文本比对。",
    {
      type: "object",
      properties: {
        quote: { type: "string", maxLength: 400 },
        source: { type: "string" },
        book: { type: "string" },
        page: { type: "integer", minimum: 1 },
        document_id: { type: "string" },
        section: { type: "string" },
        revision: { type: "string" },
        dpi: { type: "integer", minimum: 72, maximum: 300 },
      },
      required: [],
    },
    async (args, exec) => {
      if (args.quote) {
        const q = new URLSearchParams({ quote: String(args.quote) });
        if (args.document_id) {
          q.set("document_id", String(args.document_id));
          if (args.section) q.set("section", String(args.section));
          if (args.revision) q.set("revision", String(args.revision));
        } else if (args.book && args.page) {
          q.set("book", String(args.book));
          q.set("page", String(args.page));
          if (args.source) q.set("source", String(args.source));
        } else {
          return JSON.stringify({ ok: false, error: "bad_request",
            hint: "quote 需要配 document_id，或配 book+page" });
        }
        return JSON.stringify(await call(config, "/v1/verify?" + q.toString(),
          { signal: exec?.signal }));
      }
      if (!(args.book && args.page)) {
        return JSON.stringify({ ok: false, error: "bad_request",
          hint: "不给 quote 时按页图核对，需要 book+page" });
      }
      const q = new URLSearchParams({
        source: String(args.source || ""),
        book: String(args.book),
        page: String(args.page),
        dpi: String(args.dpi || 150),
      });
      const r = await callBinary(config, "/v1/pages?" + q.toString(), { signal: exec?.signal });
      return JSON.stringify(r);
    },
  ));

  ctx.tools.register(tool(
    "compute_math",
    "计算：SymPy 符号 / SciPy 数值 / pint 单位 / control / 可选 Wolfram/Lean；" +
      "不可用后端返回 503，不伪造结果。",
    {
      type: "object",
      properties: {
        expression: { type: "string" },
        operation: { type: "string", enum: ["simplify", "diff", "integrate", "solve", "limit", "value", "latex", "factor", "expand", "quad", "minimize", "root", "convert", "step", "eval", "check"] },
        variable: { type: "string" },
        point: { type: "string" },
        backend: { type: "string", enum: ["auto", "sympy", "scipy", "pint", "control", "wolfram", "lean"] },
        target: { type: "string", description: "SciPy 上界 / pint 目标单位" },
        data: { type: "object", description: "control: {num,den}" },
      },
      required: ["expression", "operation"],
    },
    async (args, exec) => {
      const r = await call(config, "/v1/compute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expression: String(args.expression || ""),
          operation: String(args.operation || "simplify"),
          variable: String(args.variable || "x"),
          point: String(args.point || "0"),
          backend: String(args.backend || "auto"),
          target: args.target ? String(args.target) : null,
          data: args.data || null,
        }),
        signal: exec?.signal,
      });
      return JSON.stringify(r.body);
    },
  ));

  ctx.tools.register(tool(
    "ptc_calc",
    "PTC 计算：写 JavaScript 程序化调用 compute_symbolic/compute_numeric，适合多步推导；禁止文件/网络/DB。",
    {
      type: "object",
      properties: {
        code: { type: "string", description: "async 函数体；可 await compute_symbolic(...)" },
      },
      required: ["code"],
    },
    async (args, exec) => {
      const r = await runCode(args.code, { config, signal: exec?.signal });
      log("ptc_run", { ok: r.ok, calls: r.calls?.length || 0,
        error: r.error || "", code_len: String(args.code || "").length });
      return JSON.stringify(r);
    },
  ));

  ctx.tools.register(tool(
    "review_session",
    "复盘当前会话（P3）：冻结状态，逐条判定学生陈述、给 8 类错误与归因，产出复练卡。",
    {
      type: "object",
      properties: {
        session_id: { type: "string", description: "默认当前会话" },
        answers: { type: "array", items: { type: "string" }, description: "可选：显式给出学生原话" },
      },
      required: [],
    },
    async (args, exec) => {
      const sid = String(args.session_id || sessionId(exec));
      const body = { session_id: sid };
      if (Array.isArray(args.answers)) body.answers = args.answers.map(String);
      const r = await call(config, "/v1/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: exec?.signal,
      });
      return JSON.stringify(r.body);
    },
  ));

  ctx.tools.register(tool(
    "socratic_critic",
    "检查多问/泄漏/无引用；若 flags 含 multi_question，用 rewrite.text 作为最终回复。",
    {
      type: "object",
      properties: {
        text: { type: "string" },
        hint_level: { type: "integer", minimum: 0, maximum: 5 },
        has_citation: { type: "boolean" },
      },
      required: ["text"],
    },
    async (args, exec) => {
      const r = await call(config, "/v1/critic", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: String(args.text || ""),
          hint_level: Number(args.hint_level || 0),
          has_citation: Boolean(args.has_citation),
        }),
        signal: exec?.signal,
      });
      return JSON.stringify(r.body);
    },
  ));

  ctx.tools.register(tool(
    "socratic_health",
    "检查 sidecar 是否在线、索引统计。",
    { type: "object", properties: {}, additionalProperties: false },
    async (_args, exec) => {
      // Always runs: this is the tool that reports the failure itself.
      const health = await probe(config);
      const r = await call(config, "/health", { signal: exec?.signal }).catch((e) => ({
        ok: false, status: 0, body: { error: String(e && e.message || e) },
      }));
      return JSON.stringify({ ...r.body, reachable: health.up, base: health.base });
    },
    { needsSidecar: false },
  ));

  ctx.tools.register(tool(
    "socratic_init",
    "初始化本会话教学状态机（ALIGN）。概念/目标确定后调用。",
    {
      type: "object",
      properties: {
        goal: { type: "string" },
        concept: { type: "string" },
        lang: { type: "string" },
      },
    },
    async (args, exec) => {
      const key = sessionId(exec);
      const r = await call(config, "/v1/state/init", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: key, goal: String(args.goal || ""),
          concept: String(args.concept || ""), lang: String(args.lang || "zh") }),
        signal: exec?.signal,
      });
      return JSON.stringify(r.body);
    },
  ));

  ctx.tools.register(tool(
    "socratic_step",
    "推进教学状态机。event 必须是 allowed_events 之一；answer 时把学生原话放 text，由 sidecar 判定；不要自己填 result（除非人工测试）。",
    {
      type: "object",
      properties: {
        event: { type: "string", enum: ["confirm_goal", "diagnosed", "plan_ready", "asked",
          "answer", "hint_request", "next", "transfer_done", "stop"] },
        result: { type: "string", enum: ["correct", "partial", "wrong"] },
        text: { type: "string", description: "学生原话；event=asked 时是问题，event=answer 时是回答" },
        rubric: { type: "string", description: "期望命中的关键点，逗号分隔" },
      },
      required: ["event"],
    },
    async (args, exec) => {
      const key = sessionId(exec);
      const r = await call(config, "/v1/state/step", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: key, event: String(args.event),
          result: args.result ? String(args.result) : null,
          text: args.text ? String(args.text) : null,
          rubric: args.rubric ? String(args.rubric) : null }),
        signal: exec?.signal,
      });
      if (!r.ok) return JSON.stringify({ ok: false, status: r.status, body: r.body,
        hint: "404 时先调用 socratic_init" });
      return JSON.stringify(r.body);
    },
  ));

  ctx.tools.register(tool(
    "socratic_state",
    "读取本会话教学状态机状态与摘要。",
    { type: "object", properties: {}, additionalProperties: false },
    async (_args, exec) => {
      const key = sessionId(exec);
      const r = await call(config, `/v1/state/${encodeURIComponent(key)}`, { signal: exec?.signal });
      return JSON.stringify(r.body);
    },
  ));

  console.error("[dsh-socratic] registered kb_search/kb_read/chapter_lookup/cite_verify/"
    + "compute_math/ptc_calc/review_session/socratic_critic/socratic_health/"
    + "socratic_init/socratic_state/socratic_step");
}
