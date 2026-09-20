/** Step 2 of 2 (design/v1/04-05): the 6-digit code. Console: [id] mfa passed. */

import { newTraceId, traceLogger } from '@/lib/trace'
import { useState, type FormEvent } from 'react'
import { authApi, type SessionInfo } from './api'
import { Alert, AuthShell, CodeField, Heading, IntendedUseNotice, LinkButton, PrimaryButton } from './ui'

type Props = {
  userId: string
  onVerified: (info: SessionInfo) => void
  onLocked: (message: string) => void
  onStartAgain: (why?: string) => void
}

export function CodePage({ userId, onVerified, onLocked, onStartAgain }: Props) {
  const [code, setCode] = useState('')
  const [wrongCode, setWrongCode] = useState(false) // design 05
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    const traceId = newTraceId()
    const log = traceLogger(traceId)
    const digits = code.replace(/\s/g, '')
    if (!/^\d{6}$/.test(digits)) {
      log.warn('mfa input blocked: not 6 digits')
      setWrongCode(false)
      setError('Enter the 6 digits your app shows now.')
      return
    }
    setBusy(true)
    const result = await authApi.mfa({ client_trace_id: traceId, code: digits })
    setBusy(false)
    if (result.ok) {
      log.info('mfa passed')
      onVerified(result.data)
      return
    }
    log.warn(`mfa failed (HTTP ${result.status})`)
    setCode('')
    if (result.problem.error === 'locked') return onLocked(result.problem.message)
    // 5 minutes passed, or the browser did not keep the sign-in cookie.
    if (result.status === 401 && result.problem.error !== 'code_failed') return onStartAgain(result.problem.message)
    const wrong = result.problem.error === 'code_failed'
    setWrongCode(wrong)
    setError(wrong ? null : result.problem.message)
  }

  return (
    <AuthShell>
      <form noValidate onSubmit={submit} aria-label="Enter your 6-digit code" className="flex flex-col gap-[22px]">
        <Heading step="Step 2 of 2" title="Enter your 6-digit code" lede={`Signed in as ${userId}.`} />
        {wrongCode && (
          <Alert tone="danger" word="That code did not work">
            It was wrong or it has expired. Your app shows a new code every 30 seconds — enter the one showing now.
          </Alert>
        )}
        {error && <Alert tone="check" word="Check and try again">{error}</Alert>}
        <CodeField
          id="otp"
          label="6-digit code"
          hint="From your authenticator app. It changes every 30 seconds."
          autoFocus
          value={code}
          invalid={wrongCode}
          onChange={(e) => setCode(e.target.value)}
        />
        <div className="flex flex-wrap gap-3">
          <PrimaryButton type="submit" disabled={busy}>{busy ? 'Checking…' : 'Verify and continue'}</PrimaryButton>
        </div>
        <LinkButton onClick={() => onStartAgain('Signed out. Sign in with the account you want.')}>
          Use a different account
        </LinkButton>
        <IntendedUseNotice />
      </form>
    </AuthShell>
  )
}
