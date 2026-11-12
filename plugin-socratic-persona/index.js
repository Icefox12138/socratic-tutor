// dsh-socratic-persona — the teaching layer of the Socratic tutor.
//
// Everything here changes how an agent *answers*: the charter in the system
// prompt, the per-step state summary, and the streaming rewrite that enforces
// citations, keeps answers back before L4, and limits a reply to one question.
// It is a separate bundle on purpose — all three act at Host level and apply to
// every session in the profile, so a development session must be able to
// install the tools bundle (dsh-socratic) without this one.
//
//   install both      -> teaching mode
//   install tools only -> tools, ordinary assistant
//
// The rewrite engine and the stream switch live here; the sidecar connection
// for the state summary is a single GET, so this package has no dependency on
// the tools bundle.

import { appendFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { rewrites, streamMode } from "./lib/stream-mode.js";

const DEFAULT_BASE = "http://127.0.0.1:8765";
const DEBUG = process.env.SOCRATIC_DEBUG === "1";
let LOG = null;
try {
  LOG = fileURLToPath(new URL("./persona.log", import.meta.url));
} catch { /* unreadable install path: logging simply stays off */ }

function log(event, data) {
  if (!DEBUG || !LOG) return;
  try {
    appendFileSync(LOG, JSON.stringify({ t: new Date().toISOString(), event, ...data }) + "\n");
  } catch { /* ignore */ }
}

export const name = "socratic-persona";
export const inject = ["systemPrompt"];

export const DEFAULT_SUMMARY =
  "【状态摘要】阶段=ALIGN；概念=未设定；提示=L0；尝试=0；已揭示=否。";

function sessionId(obj) {
  const a = obj && obj.agent;
  return String(a?.session?.id || a?.id || obj?.turn?.sessionId || "default");
}

function settings(config) {
  const env = process.env;
  const base = String((config && config.baseUrl) || env.SOCRATIC_SIDECAR_URL || DEFAULT_BASE)
    .replace(/\/+$/, "");
  const token = String((config && config.token) || env.SOCRATIC_TOKEN || "");
  return { base, token };
}

/** One GET against the sidecar; the persona only ever reads the state summary. */
async function sidecarGet(config, path, signal) {
  const { base, token } = settings(config);
  const res = await fetch(base + path, {
    headers: token ? { "X-Sidecar-Token": token } : {},
    signal,
  });
  if (!res.ok) throw new Error("HTTP " + res.status);
  return res.json();
}

async function fetchStateSummary(config, key) {
  try {
    const body = await sidecarGet(config, "/v1/state/" + encodeURIComponent(key));
    if (body && body.summary) return body;
  } catch { /* sidecar down: the caller falls back to DEFAULT_SUMMARY */ }
  return null;
}

// ── rewrite engine ───────────────────────────────────────────────────────────

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

// ── the three hooks ──────────────────────────────────────────────────────────

/** The teaching charter, as text — exported so its wording is unit-testable. */
export function charterText() {
  return [
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
    "10) 事实断言必须带 locator（p.12 / CTS URN / Wikisource rev）；无 locator 的硬拦截会把该事实句替换为“尚未核验”声明。",
  ].join("\n");
}

/**
 * The `llm/stream` listener. Only streams that expose a teaching tool are
 * rewritten; everything else is forwarded untouched.
 */
export function makeStreamHandler(isRewriting = rewrites) {
  return function socraticStream(options, next) {
    const names = (options && Array.isArray(options.tools) ? options.tools : [])
      .map((t) => String(t && t.name || ""));
    const teaching = names.some((n) => n.startsWith("kb_") || n.startsWith("socratic_") || n === "cite_verify");
    if (!teaching) return next();
    if (!isRewriting()) {
      // Streaming switch: forward deltas untouched, keep an audit trail of
      // what the rewrite would have caught.
      return passThrough(next());
    }
    return rewriteStream(next());
  };
}

/**
 * The `agent/pre-step` listener: prepend the sidecar-generated state summary so
 * the model never has to remember the state machine's position.
 */
export function makePreStepHandler(config) {
  return async function socraticPreStep(...args) {
    const next = [...args].reverse().find((a) => typeof a === "function");
    if (typeof next !== "function") return undefined;
    const res = await next();
    try {
      const key = sessionId(args[0]);
      if (res && Array.isArray(res.messages)) {
        const st = await fetchStateSummary(config, key);
        const summary = st && st.summary ? st.summary : DEFAULT_SUMMARY;
        activeHint = st && st.state && st.state.hint_level != null ? Number(st.state.hint_level) : 0;
        const injected = {
          role: "user",
          content: [{ type: "text", text: summary }],
          source: {
            kind: "runtime-context",
            form: "snapshot",
            sections: [{ name: "socratic-state", text: summary }],
          },
        };
        log("inject", { key, n: res.messages.length + 1,
          roles: [injected.role, ...res.messages.map((m) => m.role)], summary });
        // Return a NEW decision: next() may hand back a frozen object (DSH 0.2.2
        // already deep-freezes llm/stream options), so never mutate it in place.
        return { ...res, messages: [injected, ...res.messages] };
      }
    } catch (e) {
      log("inject_error", { error: String(e && e.message || e) });
    }
    return res;
  };
}

export function apply(ctx, config) {
  const cfg = config || {};
  if (process.env.SOCRATIC_HARD_REWRITE !== "0") {
    ctx.on("llm/stream", makeStreamHandler());
  }
  ctx.on("agent/pre-step", makePreStepHandler(cfg));
  ctx.systemPrompt.section({
    name: "socratic:charter",
    order: 120,
    text: charterText(),
  });
  console.error("[dsh-socratic-persona] charter + pre-step summary + stream rewrite");
}
