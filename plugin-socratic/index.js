import { appendFileSync } from "node:fs";
import { runCode } from "./ptc.js";
import { call, callBinary, degraded, probe, settings } from "./lib/transport.js";
import { rewrites, streamMode } from "./lib/stream-mode.js";

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
export const inject = ["tools", "systemPrompt"];

function sessionId(obj) {
  const a = obj && obj.agent;
  return String(a?.session?.id || a?.id || obj?.turn?.sessionId || "default");
}

const FACT = ["是指", "表示", "说明", "表明", "称为", "叫做", "等于", "满足",
  "定义为", "根据定义", "定理", "公式", "原文", "数据", "根据研究", "根据定理", "根据原文",
  "研究表明", "数据显示", "记载", "列出"];
const META = ["回答", "问题", "提示", "复述", "猜", "学习", "机会", "规则"];
const CITE = /p\.\s*\d+|第\s*\d+\s*页/;
const LEAK = ["答案是", "所以答案", "最终答案", "正确选项是", "答案就是"];
let activeHint = 0;

function isClaim(p) {
  const s = String(p || "").trim();
  if (s.length < 10 || /[?？]/.test(s)) return false;
  if (META.some((w) => s.includes(w))) return false;
  return FACT.some((w) => s.includes(w));
}

function softenUncited(text, mode) {
  const t = String(text || "");
  const m = mode || process.env.SOCRATIC_CITATION_MODE || "soften";
  if (m === "off") return { text: t, changed: false };
  const sentences = t.split(/(?<=[。！？!?；;\n])/).filter(Boolean);
  const factual = sentences.filter((p) => isClaim(p) && !CITE.test(p));
  log("citation_probe", { len: t.length, cite: CITE.test(t), sentences: sentences.length,
    factual: factual.length, sample: t.slice(0, 80) });
  if (!factual.length) return { text: t, changed: false };
  if (m === "mark") {
    return { text: t.replace(/\s+$/, "") + "\n\n〔未引用：以上事实断言缺少 locator，需核验〕", changed: true };
  }
  const out = sentences.map((p) => (isClaim(p) && !CITE.test(p)
    ? "这一点我尚未核验，先不下结论。" : p));
  const next = out.join("").trim();
  return { text: next, changed: next !== t };
}

function softenLeak(text, hint) {
  const t = String(text || "");
  const mode = process.env.SOCRATIC_LEAK_MODE || "soften";
  if (mode === "off" || hint >= 4) return { text: t, changed: false };
  const sentences = t.split(/(?<=[。！？!?；;\n])/).filter(Boolean);
  const leaked = sentences.filter((p) => LEAK.some((w) => p.includes(w)));
  if (!leaked.length) return { text: t, changed: false };
  if (mode === "mark") {
    return { text: t.replace(/\s+$/, "") + "\n\n〔未揭示：L4 前不给最终答案〕", changed: true };
  }
  const out = sentences.map((p) => (LEAK.some((w) => p.includes(w))
    ? "这一步先不揭示最终答案；你先说说卡在哪一步？" : p));
  const next = out.join("").trim();
  return { text: next, changed: next !== t };
}

function rewriteOneQuestion(text) {
  const t = String(text || "");
  const m = t.match(/[?？]/);
  if (!m) return { text: t, changed: false };
  const idx = m.index;
  const head = t.slice(0, idx + 1).replace(/\s+$/, "");
  const rest = t.slice(idx + 1);
  const parts = rest.split(/(?<=[。！？!?；;\n])/);
  const keep = parts.filter((p) => p.trim() && !/[?？]/.test(p));
  let out = head;
  if (keep.length) {
    const tail = keep.join("").trim();
    if (tail) {
      const sep = rest.includes("\n") ? "\n" : (/^[A-Za-z0-9]/.test(tail) ? " " : "");
      out += sep + tail;
    }
  }
  out = out.replace(/\s+$/, "");
  return { text: out, changed: out !== t };
}

async function* rewriteStream(src) {
  const chunks = [];
  for await (const c of src) chunks.push(c);
  const hasTool = chunks.some((c) => c.type === "tool-call-delta"
    || (c.type === "block-end" && c.block && c.block.type === "tool-call"));
  const textIndexes = [...new Set(chunks
    .filter((c) => c.type === "text-delta").map((c) => c.index))].sort((a, b) => a - b);
  if (hasTool || !textIndexes.length) {
    for (const c of chunks) yield c;
    return;
  }
  const first = textIndexes[0];
  const allText = chunks
    .filter((c) => c.type === "text-delta" && c.index === first)
    .map((c) => c.text).join("");
  const cited = softenUncited(allText);
  const leak = softenLeak(cited.text, activeHint);
  const r = rewriteOneQuestion(leak.text);
  if (!r.changed && !cited.changed && !leak.changed) {
    for (const c of chunks) yield c;
    return;
  }
  log("hard_rewrite", { before: allText.length, after: r.text.length,
    citation: cited.changed, leak: leak.changed, hint: activeHint });
  let put = false;
  for (const c of chunks) {
    if (c.type === "text-delta") {
      if (c.index === first && !put) {
        put = true;
        yield { ...c, text: r.text };
      } else {
        yield { ...c, text: "" };
      }
    } else if (c.type === "block-end" && c.block && c.block.type === "text") {
      yield { ...c, block: { ...c.block, text: c.index === first ? r.text : "" } };
    } else {
      yield c;
    }
  }
}

async function* passThrough(src) {
  let chars = 0;
  let tools = 0;
  for await (const c of src) {
    if (c && c.type === "text-delta") chars += String(c.text || "").length;
    if (c && (c.type === "tool-call-delta"
      || (c.type === "block-end" && c.block && c.block.type === "tool-call"))) tools += 1;
    yield c;
  }
  log("stream_passthrough", { mode: streamMode(), chars, tools,
    note: "interception skipped (SOCRATIC_STREAM=stream)" });
}

async function fetchStateSummary(config, key, fallback) {
  try {
    const r = await call(config, `/v1/state/${encodeURIComponent(key)}`);
    if (r.ok && r.body && r.body.summary) return r.body;
  } catch { /* sidecar down: keep fallback */ }
  return null;
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
  const DEFAULT_SUMMARY = "【状态摘要】阶段=ALIGN；概念=未设定；提示=L0；尝试=0；已揭示=否。";

  if (process.env.SOCRATIC_HARD_REWRITE !== "0") {
    ctx.on("llm/stream", (options, next) => {
      const names = (options && Array.isArray(options.tools) ? options.tools : [])
        .map((t) => String(t && t.name || ""));
      const teaching = names.some((n) => n.startsWith("kb_") || n.startsWith("socratic_") || n === "cite_verify");
      if (!teaching) return next();
      if (!rewrites()) {
        // Streaming switch: forward deltas untouched, keep an audit trail of
        // what the rewrite would have caught.
        return passThrough(next());
      }
      return rewriteStream(next());
    });
  }

  ctx.on("agent/pre-step", async (...args) => {
    const next = [...args].reverse().find((a) => typeof a === "function");
    if (typeof next !== "function") return undefined;
    const res = await next();
    try {
      const key = sessionId(args[0]);
      if (res && Array.isArray(res.messages)) {
        const st = await fetchStateSummary(config, key, null);
        const text = st && st.summary ? st.summary : DEFAULT_SUMMARY;
        activeHint = st && st.state && st.state.hint_level != null ? Number(st.state.hint_level) : 0;
        res.messages.unshift({
          role: "user",
          content: [{ type: "text", text }],
          source: {
            kind: "runtime-context",
            form: "snapshot",
            sections: [{ name: "socratic-state", text }],
          },
        });
        log("inject", { key, n: res.messages.length, roles: res.messages.map((m) => m.role), summary: text });
      }
    } catch (e) {
      log("inject_error", { error: String(e && e.message || e) });
    }
    return res;
  });

  ctx.systemPrompt.section({
    name: "socratic:charter",
    order: 120,
    text: [
      "你是苏格拉底式教学导师。",
      "规则：",
      "1) L4 前不给最终答案；只提问、给 L0–L3 提示。",
      "2) 每次只问一个问题。",
      "3) 事实性断言必须先调用 kb_search，并引用 citation；检索不到就说未检索到。",
      "4) 不得请求或暴露 answer_key；view 只能是 student 或 tutor。",
      "5) 学生施压要答案时，拒绝并给更低一级提示。",
      "6) 会话开始先调用 socratic_init；之后每一步按 socratic_step 返回的 action.instruction 行动，不要自行跳阶段。",
      "7) 状态摘要由 sidecar 生成；不要用记忆覆盖它。",
      "8) 判定由 sidecar 做：answer 时把学生原话放 text，不要自己填 correct/partial/wrong。",
      "9) 输出前可用 socratic_critic 自检；如 flags 含 multi_question，必须用 rewrite.text（只保留第一个问题）替换最终回复。",
      "10) 事实断言必须带 locator（p.12）；无 locator 的硬拦截会把该事实句替换为“尚未核验”声明。",
    ].join("\n"),
  });

  ctx.tools.register(tool(
    "kb_search",
    "检索馆藏/Steadman 片段，返回 citation 与页图 URL；事实断言前必须调用。",
    {
      type: "object",
      properties: {
        query: { type: "string" },
        view: { type: "string", enum: ["student", "tutor"] },
        limit: { type: "integer", minimum: 1, maximum: 12 },
        source: { type: "string" },
        lang: { type: "string" },
        book: { type: "string", description: "限定书目（侧栏书键，如 library 下相对路径）" },
        chapter: { type: "string", description: "限定章回：'卷3' / '第7回' / 标题片段" },
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
      if (args.chapter) q.set("chapter", String(args.chapter));
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
    "cite_verify",
    "核验引用：按 source/book/page 取页图，返回状态与字节数；S 级引用必须核验。",
    {
      type: "object",
      properties: {
        source: { type: "string" },
        book: { type: "string" },
        page: { type: "integer", minimum: 1 },
        dpi: { type: "integer", minimum: 72, maximum: 300 },
      },
      required: ["source", "book", "page"],
    },
    async (args, exec) => {
      const q = new URLSearchParams({
        source: String(args.source),
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
    "SymPy 计算：expression + operation（simplify/diff/integrate/solve/limit/value/latex）。",
    {
      type: "object",
      properties: {
        expression: { type: "string" },
        operation: { type: "string", enum: ["simplify", "diff", "integrate", "solve", "limit", "value", "latex"] },
        variable: { type: "string" },
        point: { type: "string" },
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
