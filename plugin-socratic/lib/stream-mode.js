// Streaming vs buffered rewriting.
//
// The hard intervention (single question / citation / leak) can only decide
// after it has the whole reply, so the default is buffer: hold the deltas,
// rewrite once, then emit. stream trades that guarantee for token-by-token
// output - useful while demoing or when the charter is off.
//
//   SOCRATIC_STREAM=buffer   (default) rewrite before the user sees text
//   SOCRATIC_STREAM=stream   forward deltas as they arrive, audit only

const MODES = new Set(["buffer", "stream"]);

export function streamMode(env = process.env) {
  const raw = String((env && env.SOCRATIC_STREAM) || "buffer").trim().toLowerCase();
  return MODES.has(raw) ? raw : "buffer";
}

export function rewrites(env = process.env) {
  return streamMode(env) === "buffer";
}
