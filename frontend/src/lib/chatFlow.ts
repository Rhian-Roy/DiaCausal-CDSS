/**
 * What happens to one message, in order. Each step prints a console line that
 * starts with the message's trace ID:
 *
 *   1. input passed             the text was taken from the box
 *   2. ui guard passed          not empty, not too long, no blocked words
 *   3. medical ui guard passed  (stub for now)
 *   4. output passed            the backend answered and the answer checked out
 *   5. the answer is shown on the page
 */

import type { StageResult } from './contract'
import { medicalUiGuard, uiGuard } from './guards'
import type { TraceLogger } from './trace'

export type Answer =
  | { kind: 'pending' }
  | { kind: 'answered'; text: string; stages: StageResult[] }
  | { kind: 'blocked'; reason: string; stages: StageResult[] }
  | { kind: 'error'; message: string }

export type InputCheck = { ok: true; message: string } | { ok: false; reason: string }

/** Steps 1-3: take the typed text and run the browser-side guards. */
export function checkInput(typed: string, log: TraceLogger): InputCheck {
  const message = typed.trim()
  log.info('input passed')

  const ui = uiGuard(message)
  if (!ui.ok) {
    log.warn(`ui guard blocked: ${ui.reason}`)
    return ui
  }
  log.info('ui guard passed')

  const medical = medicalUiGuard(message)
  if (!medical.ok) {
    log.warn(`medical ui guard blocked: ${medical.reason}`)
    return medical
  }
  log.info('medical ui guard passed')

  return { ok: true, message }
}

/** Steps 4-5: send to the backend and check what comes back. Wired up in the next step. */
export async function askDiaCausal(_message: string, _traceId: string, _log: TraceLogger): Promise<Answer> {
  return { kind: 'error', message: 'Not connected to the backend yet.' }
}
