/**
 * Idle timeout on the page (design/v1/08). The server ends a session after
 * `idle_timeout_seconds` without a request; this warns `warning_seconds` before that,
 * and signs out (clearing the conversation from the screen) when time is up.
 */

import { INTENDED_USE } from '@/lib/contract'
import { getLastActivity, onActivity } from '@/lib/authSession'
import { Clock } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { GhostButton, PrimaryButton } from './ui'

type Props = {
  idleSeconds: number
  warningSeconds: number
  onStay: () => void
  onSignOut: (reason: 'idle' | 'button') => void
}

export function SessionTimer({ idleSeconds, warningSeconds, onStay, onSignOut }: Props) {
  const [secondsLeft, setSecondsLeft] = useState(idleSeconds)
  const stay = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    const tick = () => {
      const left = Math.ceil(idleSeconds - (Date.now() - getLastActivity()) / 1000)
      setSecondsLeft(left)
      if (left <= 0) onSignOut('idle')
    }
    const timer = setInterval(tick, 1000)
    const stop = onActivity(tick)
    return () => {
      clearInterval(timer)
      stop()
    }
  }, [idleSeconds, onSignOut])

  const warning = secondsLeft > 0 && secondsLeft <= warningSeconds
  useEffect(() => {
    if (warning) stay.current?.focus()
  }, [warning])

  if (!warning) return null
  const minutes = Math.ceil(secondsLeft / 60)
  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-scrim p-4">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="session-title"
        aria-describedby="session-desc"
        className="flex w-full max-w-[560px] flex-col gap-4 rounded-card border-2 border-border-soft bg-surface p-6"
      >
        <div className="flex items-start gap-3">
          <Clock aria-hidden="true" strokeWidth={2.4} className="mt-1 size-7 shrink-0 text-check-ink" />
          <div className="flex flex-col gap-2">
            <h2 id="session-title" className="m-0 font-display text-[26px] leading-tight font-semibold">
              You&rsquo;ll be signed out in {minutes} minute{minutes === 1 ? '' : 's'}
            </h2>
            <p id="session-desc" className="m-0 text-lg leading-normal">
              This session has been idle. When it closes, the conversation on screen is cleared so the next person
              cannot read it.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <PrimaryButton ref={stay} type="button" onClick={onStay}>Stay signed in</PrimaryButton>
          <GhostButton onClick={() => onSignOut('button')}>Sign out now</GhostButton>
        </div>
        <p className="m-0 text-sm text-ink-muted md:text-base">{INTENDED_USE}</p>
      </div>
    </div>
  )
}
