import { useState } from 'react'

import { askDiaCausal, checkInput, type Answer } from '@/lib/chatFlow'
import type { ReasonCode } from '@/lib/contract'
import { redactIdentifiers } from '@/lib/guards'
import { newTraceId, traceLogger } from '@/lib/trace'

/** `question` is null when it must not be shown back (a message blocked for its language). */
export type Turn = { traceId: string; question: string | null; answer: Answer }

/** What the "You asked" line may show for a message a guard stopped. */
function shownQuestion(message: string, code: ReasonCode): string | null {
  if (code === 'language') return null
  if (code === 'identifier') return redactIdentifiers(message)
  return message
}

const WAIT_NOTICE = 'Please wait for the current answer.'

/** The conversation on screen, and `send` for a new message. */
export function useChat() {
  const [turns, setTurns] = useState<Turn[]>([])
  const [notice, setNotice] = useState<string | null>(null)
  const waiting = turns.some((turn) => turn.answer.kind === 'pending')

  /** Returns true if the message was accepted (so the box can be cleared). */
  function send(typed: string): boolean {
    if (waiting) {
      setNotice(WAIT_NOTICE)
      return false
    }

    const traceId = newTraceId()
    const log = traceLogger(traceId)
    const checked = checkInput(typed, log)
    if (!checked.ok && checked.code) {
      // A guard stopped it: show the notice in the conversation (designs 09-12). Not sent.
      const { code, topic = null } = checked
      const answer: Answer = { kind: 'notice', code, topic, stages: null }
      setNotice(null)
      setTurns((all) => [...all, { traceId, question: shownQuestion(typed.trim(), code), answer }])
      return true
    }
    if (!checked.ok) {
      setNotice(checked.reason)
      return false
    }

    setNotice(null)
    setTurns((all) => [...all, { traceId, question: checked.message, answer: { kind: 'pending' } }])

    const setAnswer = (answer: Answer) => {
      setTurns((all) =>
        all.map((turn) =>
          turn.traceId !== traceId
            ? turn
            : answer.kind === 'notice' // the server's guard: hide what the browser's would have hidden
              ? { ...turn, answer, question: shownQuestion(checked.message, answer.code) }
              : { ...turn, answer },
        ),
      )
      setNotice((current) => (current === WAIT_NOTICE ? null : current)) // no longer true
    }
    askDiaCausal(checked.message, traceId, log)
      .then(setAnswer)
      .catch((error: unknown) => {
        log.error(`unexpected error: ${String(error)}`)
        setAnswer({ kind: 'error', message: 'Something went wrong in the page. Try again.' })
      })
    return true
  }

  return { turns, notice, waiting, send, clearNotice: () => setNotice(null) }
}
