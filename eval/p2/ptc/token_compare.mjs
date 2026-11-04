// Token comparison: native tools vs PTC run_code, same 10 socratic tasks.
//
//   node eval/p2/ptc/token_compare.mjs            # all 10 tasks, both modes
//   LIMIT=2 node eval/p2/ptc/token_compare.mjs    # smoke: first 2 tasks
//
// Each task runs through "dsh --profile tutor headless --json" in a fresh
// session, so the numbers are per-task rather than a growing conversation.
// The PTC arm sets DSH_TOOLS_MODE=ptc (the deployment switch the headless
// bundle reads); the native arm leaves it unset.
import { spawn } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

const EXE = "D:\\Program Files\\dsh\\DeepSeek Harness.exe";
const CLI = "D:\\Program Files\\dsh\\resources\\app.asar\\dsh\\node_modules\\@deepseek-ai\\dsh-desktop-host\\lib\\cli.js";
const HOME = "C:\\Users\\Administrator";
const CRED = HOME + "\\.dsh\\.credentials.yaml";
const REPO = "D:\\Guo-Code\\socratic-tutor";
const TIMEOUT_MS = 240000;

const TASKS = [
  { id: "t01", kind: "kb", text: "《几何原本》里欧几里得证明质数无穷的那段原文在第几页？" },
  { id: "t02", kind: "kb", text: "洛必达法则在教材里的原文表述在哪一页？" },
  { id: "t03", kind: "compute", text: "我算 x^3 的导数是 3x^2，对吗？" },
  { id: "t04", kind: "compute", text: "积分 x^2 得 x^3/3，我算对了吗？" },
  { id: "t05", kind: "compute", text: "x^2-4=0 的解是正负 2 吧？" },
  { id: "t06", kind: "compute", text: "sin(x)/x 当 x 趋于 0 时的极限是 1 吗？" },
  { id: "t07", kind: "compute", text: "化简 (x^2-1)/(x-1) 是不是 x+1？" },
  { id: "t08", kind: "kb", text: "牛顿第二定律的表述在书里第几页？" },
  { id: "t09", kind: "compute", text: "2x+3=7 解出来是 x=2 吗？" },
  { id: "t10", kind: "kb", text: "柏拉图《理想国》里 arete（德性）的用法，能给原文吗？" },
];

const MODES = [
  { name: "native", env: {} },
  { name: "ptc", env: { DSH_TOOLS_MODE: "ptc" } },
];

function apiKey() {
  const yaml = readFileSync(CRED, "utf8");
  const m = yaml.match(/DEEPSEEK_API_KEY:\s*(\S+)/);
  if (!m) throw new Error("no DEEPSEEK_API_KEY ref in credentials");
  return m[1];
}

function childEnv(extra) {
  return {
    SystemRoot: "C:\\Windows",
    windir: "C:\\Windows",
    ComSpec: "C:\\Windows\\System32\\cmd.exe",
    PATHEXT: ".COM;.EXE;.BAT;.CMD",
    PATH: "C:\\Windows\\System32;C:\\Windows;C:\\Windows\\System32\\Wbem",
    TEMP: "C:\\Windows\\Temp",
    TMP: "C:\\Windows\\Temp",
    USERPROFILE: HOME,
    APPDATA: HOME + "\\AppData\\Roaming",
    LOCALAPPDATA: HOME + "\\AppData\\Local",
    DSH_HOME: HOME + "\\.dsh",
    DEEPSEEK_API_KEY: apiKey(),
    ...extra,
  };
}

function runOnce(task, mode) {
  return new Promise((resolve) => {
    const t0 = Date.now();
    const args = ["--expose-internals", CLI, "--profile", "tutor", "headless", "--json", task.text];
    const child = spawn(EXE, args, {
      cwd: REPO,
      env: childEnv({ ...mode.env, ELECTRON_RUN_AS_NODE: "1" }),
      stdio: ["ignore", "pipe", "pipe"],
    });
    let out = "";
    let err = "";
    let killed = false;
    const timer = setTimeout(() => { killed = true; child.kill(); }, TIMEOUT_MS);
    child.stdout.on("data", (b) => { out += b.toString("utf8"); });
    child.stderr.on("data", (b) => { err += b.toString("utf8"); });
    child.on("close", (code) => {
      clearTimeout(timer);
      const events = out.split("\n").filter((l) => l.trim().startsWith("{"))
        .map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
      const steps = events.filter((e) => e.type === "status" && e.phase === "step_end");
      const calls = events.filter((e) => e.type === "tool_call");
      const final = events.filter((e) => e.type === "final").pop();
      const sum = (k) => steps.reduce((s, e) => s + (Number(e.usage && e.usage[k]) || 0), 0);
      resolve({
        task: task.id, kind: task.kind, mode: mode.name,
        ok: code === 0 && !!final, exit: code, killed,
        steps: steps.length,
        toolCalls: calls.length,
        tools: calls.map((c) => c.tool),
        inputTokens: sum("inputTokens"),
        outputTokens: sum("outputTokens"),
        cacheReadTokens: sum("cacheReadTokens"),
        finalChars: final ? String(final.text || "").length : 0,
        finalText: final ? String(final.text || "").slice(0, 200) : "",
        stderrTail: err.trim().split("\n").slice(-3).join(" | ").slice(0, 300),
        ms: Date.now() - t0,
      });
    });
  });
}

const limit = Number(process.env.LIMIT || 0);
const tasks = limit > 0 ? TASKS.slice(0, limit) : TASKS;
const rows = [];
for (const task of tasks) {
  for (const mode of MODES) {
    const r = await runOnce(task, mode);
    rows.push(r);
    const tag = r.ok ? "ok  " : "FAIL";
    console.log(tag + " " + r.task + " " + r.mode.padEnd(6) +
      " in=" + String(r.inputTokens).padStart(5) +
      " out=" + String(r.outputTokens).padStart(4) +
      " steps=" + r.steps + " calls=" + r.toolCalls + " (" + r.tools.join(",") + ")" +
      " " + r.ms + "ms" + (r.ok ? "" : " | " + r.stderrTail));
  }
}

const byMode = {};
for (const r of rows) {
  const b = (byMode[r.mode] ||= { n: 0, in: 0, out: 0, calls: 0, steps: 0, ok: 0 });
  b.n++; b.in += r.inputTokens; b.out += r.outputTokens;
  b.calls += r.toolCalls; b.steps += r.steps; b.ok += r.ok ? 1 : 0;
}
const paired = tasks.map((t) => {
  const a = rows.find((r) => r.task === t.id && r.mode === "native");
  const b = rows.find((r) => r.task === t.id && r.mode === "ptc");
  if (!a || !b) return null;
  const tot = (r) => r.inputTokens + r.outputTokens;
  return {
    task: t.id, kind: t.kind,
    native: tot(a), ptc: tot(b), delta: tot(b) - tot(a),
    pct: tot(a) ? Math.round(((tot(b) - tot(a)) / tot(a)) * 1000) / 10 : null,
    native_calls: a.toolCalls, ptc_calls: b.toolCalls,
    native_ok: a.ok, ptc_ok: b.ok,
  };
}).filter(Boolean);

const summary = {
  generatedAt: new Date().toISOString(),
  config: { profile: "tutor", exe: EXE, tasks: tasks.length, modes: MODES.map((m) => m.name) },
  byMode, paired,
  totalNative: paired.reduce((s, p) => s + p.native, 0),
  totalPtc: paired.reduce((s, p) => s + p.ptc, 0),
  rows,
};
summary.totalDeltaPct = summary.totalNative
  ? Math.round(((summary.totalPtc - summary.totalNative) / summary.totalNative) * 1000) / 10 : null;

writeFileSync(REPO + "\\eval\\p2\\ptc\\token-results.json", JSON.stringify(summary, null, 1));

console.log("");
console.log("task  kind     native    ptc   delta     pct   calls(n/p)  ok(n/p)");
for (const p of paired) {
  console.log(p.task.padEnd(5) + " " + p.kind.padEnd(8) +
    String(p.native).padStart(7) + String(p.ptc).padStart(7) + String(p.delta).padStart(8) +
    (p.pct == null ? "      -" : String(p.pct).padStart(7) + "%") + "   " +
    String(p.native_calls + "/" + p.ptc_calls).padStart(10) + "  " +
    String((p.native_ok ? "y" : "n") + "/" + (p.ptc_ok ? "y" : "n")));
}
console.log("");
console.log("TOTAL native=" + summary.totalNative + "  ptc=" + summary.totalPtc +
  "  delta=" + summary.totalDeltaPct + "%");
console.log("by mode: " + JSON.stringify(byMode));
