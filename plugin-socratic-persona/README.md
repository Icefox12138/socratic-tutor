# dsh-socratic-persona

The teaching layer for the Socratic tutor — split out of `dsh-socratic` so a
development session can install the tools without being turned into a student.

| Installed | Behaviour |
|---|---|
| `dsh-socratic` only | 13 tools + console cards, ordinary assistant |
| `dsh-socratic` + this package | teaching charter, per-step state summary, citation/leak/single-question rewriting |

## What it adds

| Hook | Effect |
|---|---|
| `systemPrompt` section `socratic:charter`, order 120 | 10 rules: no answer before L4, one question per turn, every factual claim needs a `kb_search` citation with a locator, never reveal `answer_key` |
| `agent/pre-step` | prefixes the sidecar's state summary (`【状态摘要】阶段=…`) so the model never has to remember the state machine |
| `llm/stream` | buffers the reply, then rewrites: uncited factual sentences → "尚未核验"; answer leaks → withheld; multiple questions → only the first is kept |

All three act at Host level and therefore apply to **every session in the
profile**. That is the reason for the split: there is no per-session switch.

## Install

```powershell
# both bundles, for teaching
dsh plugin --profile tutor add "link:/path/to/socratic-tutor/plugin-socratic"
dsh plugin --profile tutor add "link:/path/to/socratic-tutor/plugin-socratic-persona"
```

`SOCRATIC_HARD_REWRITE=0` disables the stream hook only (the charter and the
summary still apply). `SOCRATIC_STREAM=stream` keeps the hook but forwards deltas
untouched — it costs the interception, so use it for demos only.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SOCRATIC_SIDECAR_URL` | `http://127.0.0.1:8765` | where the state summary comes from |
| `SOCRATIC_TOKEN` | empty | sent as `X-Sidecar-Token` when set |
| `SOCRATIC_STREAM` | `buffer` | `buffer` rewrites, `stream` passes deltas through |
| `SOCRATIC_HARD_REWRITE` | (on) | `0` removes the `llm/stream` hook entirely |
| `SOCRATIC_CITATION_MODE` | `soften` | `soften` / `mark` / `off` |
| `SOCRATIC_LEAK_MODE` | `soften` | `soften` / `mark` / `off` (L4+ always passes) |
| `SOCRATIC_DEBUG` | off | `1` writes `persona.log` next to this package |

The sidecar is optional: with it down the summary falls back to
`【状态摘要】阶段=ALIGN…` and everything else still works.

## Tests

```powershell
node --test --test-isolation=none test/persona.test.mjs
```

12 tests, no sidecar and no live session needed: charter wording, the stream
switch, rewriting of uncited / cited / non-teaching streams, and the pre-step
summary with the sidecar up, down, or with no `next()` call.
