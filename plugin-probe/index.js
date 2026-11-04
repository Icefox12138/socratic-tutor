import { appendFileSync, mkdirSync } from 'node:fs'
import { dirname } from 'node:path'

const LOG = 'D:/Guo-Code/socratic-tutor/eval/p0/capability/probe-log.jsonl'

function log(event, data = {}) {
  try {
    mkdirSync(dirname(LOG), { recursive: true })
    appendFileSync(LOG, JSON.stringify({ t: new Date().toISOString(), event, ...data }) + '\n')
  } catch {
    /* probe must never break boot */
  }
}

export const name = 'capability-probe'
export const inject = ['tools', 'systemPrompt', 'jobs', 'storage']

export function apply(ctx, config) {
  const report = {}
  const safe = (key, fn) => {
    try { report[key] = fn() } catch (e) { report[key] = 'ERR:' + (e && e.message) }
  }

  safe('tools_register', () => typeof ctx.tools?.register)
  safe('tools_guard', () => typeof ctx.tools?.guard)
  safe('tools_restrict', () => typeof ctx.tools?.restrict)
  safe('tools_keys', () => Object.keys(ctx.tools ?? {}).slice(0, 20))
  safe('tools_proto', () => Object.getOwnPropertyNames(Object.getPrototypeOf(ctx.tools ?? {})).slice(0, 30))
  safe('systemPrompt_section', () => typeof ctx.systemPrompt?.section)
  safe('systemPrompt_context', () => typeof ctx.systemPrompt?.context)
  safe('jobs_start', () => typeof ctx.jobs?.start)
  safe('storage', () => (ctx.storage ? Object.keys(ctx.storage).slice(0, 20) : null))
  safe('storage_forms', () => Object.keys(ctx.storage?.forms ?? {}).slice(0, 20))
  safe('on', () => typeof ctx.on)
  safe('env_token', () => Boolean(process.env.DSH_SIDECAR_TOKEN))
  safe('config', () => config ?? null)

  const def = {
    name: 'probe_ping',
    description: 'Capability probe: returns pong and records hook execution.',
    parameters: {
      type: 'object',
      properties: { note: { type: 'string' } },
      additionalProperties: false,
    },
    output: {
      schema: { type: 'string' },
      render: (_args, value) => [{ type: 'text', text: String(value) }],
    },
    async execute(args, exec) {
      log('tool_execute', {
        args,
        hasSignal: Boolean(exec?.signal),
        hasAgent: Boolean(exec?.agent),
        execKeys: exec ? Object.keys(exec).slice(0, 15) : [],
      })
      return 'pong'
    },
  }

  try { ctx.tools.register(def); report.tool_register = 'ok' } catch (e) { report.tool_register = 'ERR:' + e?.message }

  try {
    ctx.on('tools/pre-execute', async (exec, next) => {
      log('pre_execute', { name: exec?.name, callId: exec?.callId, hasSignal: Boolean(exec?.signal) })
      return next()
    })
    report.hook_pre = 'ok'
  } catch (e) { report.hook_pre = 'ERR:' + e?.message }

  try {
    ctx.on('tools/post-execute', async (exec, result) => {
      log('post_execute', {
        execName: exec?.name,
        resultType: typeof result,
        resultKeys: result && typeof result === 'object' ? Object.keys(result).slice(0, 15) : null,
      })
      try {
        if (result && Array.isArray(result.content)) {
          log('post_rewrite', { before: result.content.length })
          return { content: [...result.content, { type: 'text', text: '[probe-marker]' }] }
        }
      } catch { /* ignore */ }
      return undefined
    })
    report.hook_post = 'ok'
  } catch (e) { report.hook_post = 'ERR:' + e?.message }

  try {
    ctx.systemPrompt.section({ name: 'probe:section', order: 999, text: 'CAPABILITY-PROBE-MARKER' })
    report.section = 'ok'
  } catch (e) { report.section = 'ERR:' + e?.message }

  try {
    const r = ctx.systemPrompt.context({ name: 'probe:context', order: 998, text: 'PROBE-CONTEXT-MARKER' })
    report.context_call = typeof r
  } catch (e) { report.context_call = 'ERR:' + e?.message }

  log('apply', report)
  console.error('[capability-probe] ' + JSON.stringify(report))
}
