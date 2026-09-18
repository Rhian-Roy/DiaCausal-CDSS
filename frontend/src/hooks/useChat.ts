import { useState } from 'react'

import { askDiaCausal, checkInput, type Answer } from '@/lib/chatFlow'
import { newTraceId, traceLogger } from '@/lib/trace'

export type Turn = { traceId: string; question: string; answer: Answer }

/** The conversation on screen, and `send` for a new message. */
export function useChat() {
  const [turns, setTurns] = useState<Turn[]>([])
  const [notice, setNotice] = useState<string | null>(null)
  const waiting = turns.some((turn) => turn.answer.kind === 'pending')

  /** Returns true if the message was accepted (so the box can be cleared). */
  function send(typed: string): boolean {
    if (waiting) {
      setNotice('Please wait for the current answer.')
      return false
    }

    const traceId = newTraceId()
    const log = traceLogger(traceId)
    const checked = checkInput(typed, log)
    if (!checked.ok) {
      setNotice(checked.reason)
      return false
    }

    setNotice(null)
    setTurns((all) => [...all, { traceId, question: checked.message, answer: { kind: 'pending' } }])

    const setAnswer = (answer: Answer) =>
      setTurns((all) => all.map((turn) => (turn.traceId === traceId ? { ...turn, answer } : turn)))
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
