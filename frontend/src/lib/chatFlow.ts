/**
 * What happens to one message, in order. Each step prints a console line that
 * starts with the message's trace ID:
 *
 *   1. input passed             the text was taken from the box
 *   2. ui guard passed          not empty, not too long, no foul language
 *   3. medical ui guard passed  no patient identifiers, not an emergency, in scope
 *   4. output passed            the backend answered and the answer checked out
 *   5. the answer is shown on the page
 */

import { checkOutput, postChat } from './api'
import type { OptionsPart, PatientPart, ReasonCode, ScopeTopic, StageResult } from './contract'
import { medicalUiGuard, uiGuard } from './guards'
import type { TraceLogger } from './trace'

export type Answer =
  | { kind: 'pending' }
  | { kind: 'answered'; text: string; stages: StageResult[]; options: OptionsPart | null }
  | { kind: 'blocked'; reason: string; stages: StageResult[] }
  // A guard stopped it (designs 09-12): in the browser (never sent, no stages) or on the server.
  | { kind: 'notice'; code: ReasonCode; topic: ScopeTopic | null; reason: string | null; stages: StageResult[] | null }
  | { kind: 'error'; message: string }

export type InputCheck =
  | { ok: true; message: string }
  | { ok: false; reason: string; code?: ReasonCode; topic?: ScopeTopic }

/** Steps 1-3: take the typed text and run the browser-side guards. */
export function checkInput(typed: string, log: TraceLogger): InputCheck {
  const message = typed.trim()
  log.info('input passed')

  const ui = uiGuard(message)
  if (!ui.ok) {
    log.warn(`ui guard blocked: ${ui.reason}${ui.code ? ` (${ui.code})` : ''}`)
    return ui
  }
  log.info('ui guard passed')

  const medical = medicalUiGuard(message)
  if (!medical.ok) {
    log.warn(`medical ui guard blocked (${medical.code}${medical.topic ? `: ${medical.topic}` : ''})`)
    return medical
  }
  log.info('medical ui guard passed')

  return { ok: true, message }
}

/** Steps 4-5: send to the backend and check what comes back. Never throws. */
export async function askDiaCausal(
  message: string,
  traceId: string,
  log: TraceLogger,
  fetchImpl?: typeof fetch,
  patient?: PatientPart | null,
): Promise<Answer> {
  const result = await postChat(message, traceId, fetchImpl, patient)
  if (result.kind === 'rejected') {
    log.error(`backend rejected the request: ${result.message}`)
    return { kind: 'error', message: result.message }
  }
  if (result.kind === 'failed') {
    log.error(`request failed: ${result.message}`)
    return { kind: 'error', message: result.message }
  }

  const checked = checkOutput(result.body, traceId)
  if (!checked.ok) {
    log.error(`output check failed: ${checked.reason}`)
    return { kind: 'error', message: 'The reply did not pass the output check, so it is not shown.' }
  }

  const { response } = checked
  if (response.outcome === 'blocked') {
    const reason = response.blocked_reason ?? 'The message was blocked.'
    log.warn(`backend blocked the message: ${reason}`)
    if (response.reason_code) {
      return { kind: 'notice', code: response.reason_code, topic: response.scope_topic, reason, stages: response.stages }
    }
    return { kind: 'blocked', reason, stages: response.stages }
  }

  log.info('output passed')
  const options = response.parts.find((part) => part.type === 'options') ?? null
  return {
    kind: 'answered',
    text: response.parts.filter((part) => part.type === 'text').map((part) => part.text).join('\n\n'),
    stages: response.stages,
    options: options as OptionsPart | null,
  }
}
