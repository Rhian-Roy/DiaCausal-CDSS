/**
 * Talking to the backend. The page calls /api/v1/chat on its own address;
 * in development Vite forwards /api to FastAPI on port 8000 (vite.config.ts).
 */

import { csrfHeaders, markActivity, sessionEnded } from './authSession'
import {
  OPTION_STATUSES,
  REASON_CODES,
  SCHEMA_VERSION,
  SCOPE_TOPICS,
  STAGE_ORDER,
  type ChatRequest,
  type ChatResponse,
  type ErrorResponse,
  type OptionsPart,
  type PatientPart,
  type ReplyPart,
  type StageStatus,
  type TextPart,
} from './contract'

export const CHAT_URL = '/api/v1/chat'
const TIMEOUT_MS = 30_000

export type PostResult =
  | { kind: 'ok'; body: unknown } // HTTP 200; the body still has to pass checkOutput
  | { kind: 'rejected'; message: string } // HTTP 422: the backend explained what was wrong
  | { kind: 'failed'; message: string } // no answer, or an unexpected one

export async function postChat(
  message: string,
  traceId: string,
  fetchImpl?: typeof fetch,
  patient?: PatientPart | null,
): Promise<PostResult> {
  const send = fetchImpl ?? ((input, init) => globalThis.fetch(input, init))
  const request: ChatRequest = {
    schema_version: SCHEMA_VERSION,
    client_trace_id: traceId,
    // The question first, then the panel: one patient part at most (schemas.py).
    parts: patient ? [{ type: 'text', text: message }, patient] : [{ type: 'text', text: message }],
  }

  let response: Response
  try {
    response = await send(CHAT_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...csrfHeaders() },
      credentials: 'same-origin',
      body: JSON.stringify(request),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    })
  } catch (error) {
    const timedOut = (error as { name?: unknown } | null)?.name === 'TimeoutError'
    return {
      kind: 'failed',
      message: timedOut
        ? 'The server took too long to answer. Try again.'
        : "Couldn't reach the DiaCausal server. Check that the backend is running.",
    }
  }

  const body: unknown = await response.json().catch(() => null)
  if (response.status === 401) {
    sessionEnded() // timed out or signed out: the page goes back to sign-in
    return { kind: 'failed', message: 'Your session has ended. Please sign in again.' }
  }
  if (response.ok) {
    markActivity()
    return { kind: 'ok', body }
  }
  if (response.status === 422 && isErrorResponse(body)) return { kind: 'rejected', message: body.message }
  return {
    kind: 'failed',
    message: `The server could not answer (HTTP ${response.status}). Check that the backend is running and look at its terminal.`,
  }
}

export type OutputCheck = { ok: true; response: ChatResponse } | { ok: false; reason: string }

const STATUSES: readonly unknown[] = ['passed', 'blocked', 'skipped'] satisfies StageStatus[]

/**
 * The browser's output check: only a reply of the right shape, for *this*
 * message's trace ID, with all six stages in order, is shown on screen.
 */
export function checkOutput(body: unknown, traceId: string): OutputCheck {
  const fail = (reason: string): OutputCheck => ({ ok: false, reason })

  if (!isRecord(body)) return fail('the reply is not a JSON object')
  if (body.schema_version !== SCHEMA_VERSION) return fail(`unexpected schema_version ${JSON.stringify(body.schema_version)}`)
  if (body.trace_id !== traceId) return fail(`the reply is for trace ${JSON.stringify(body.trace_id)}, not ${traceId}`)
  if (body.outcome !== 'answered' && body.outcome !== 'blocked') return fail('unknown outcome')
  if (!Array.isArray(body.parts) || !body.parts.every(isReplyPart)) return fail('the reply has a part we do not understand')
  const replyParts = body.parts.filter(isTextPart)
  if (!hasAllStagesInOrder(body.stages)) return fail('the pipeline stages are missing or out of order')
  if (typeof body.intended_use !== 'string') return fail('the intended-use notice is missing')
  if (body.reason_code !== null && !(REASON_CODES as readonly unknown[]).includes(body.reason_code)) {
    return fail('unknown reason_code')
  }
  if (body.scope_topic !== null && !(SCOPE_TOPICS as readonly unknown[]).includes(body.scope_topic)) {
    return fail('unknown scope_topic')
  }
  if (typeof body.request_id !== 'string') return fail('the request_id is missing')

  if (body.outcome === 'answered') {
    if (!replyParts.some((part) => part.text.trim() !== '')) return fail('the answer is empty')
    if (body.stages.at(-1)?.status !== 'passed') return fail('the output guard did not pass')
  } else if (typeof body.blocked_reason !== 'string') {
    return fail('a blocked reply must say why')
  }

  return { ok: true, response: body as ChatResponse }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isTextPart(value: unknown): value is TextPart {
  return isRecord(value) && value.type === 'text' && typeof value.text === 'string'
}

/** An options part: the three options, each with a status from the cited rules. */
function isOptionsPart(value: unknown): value is OptionsPart {
  return (
    isRecord(value) &&
    value.type === 'options' &&
    typeof value.rules_version === 'string' &&
    Array.isArray(value.options) &&
    value.options.every(
      (option) =>
        isRecord(option) &&
        (OPTION_STATUSES as readonly unknown[]).includes(option.status) &&
        typeof option.name === 'string' &&
        Array.isArray(option.reasons) &&
        Array.isArray(option.sources),
    )
  )
}

function isReplyPart(value: unknown): value is ReplyPart {
  return isTextPart(value) || isOptionsPart(value)
}

function hasAllStagesInOrder(value: unknown): value is { name: string; status: StageStatus; detail: string; duration_ms: number }[] {
  return (
    Array.isArray(value) &&
    value.length === STAGE_ORDER.length &&
    value.every(
      (stage, index) =>
        isRecord(stage) &&
        stage.name === STAGE_ORDER[index] &&
        STATUSES.includes(stage.status) &&
        typeof stage.detail === 'string' &&
        typeof stage.duration_ms === 'number',
    )
  )
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  return isRecord(value) && value.error === 'invalid_request' && typeof value.message === 'string'
}
