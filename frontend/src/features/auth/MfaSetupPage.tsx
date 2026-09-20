/** First sign-in only (design/v1/06): scan the QR code, confirm one code. Console: [id] mfa passed. */

import { newTraceId, traceLogger } from '@/lib/trace'
import { Copy } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { authApi, type MfaSetup, type SessionInfo } from './api'
import { Alert, AuthShell, Card, CodeField, GhostButton, Heading, IntendedUseNotice, PrimaryButton } from './ui'

type Props = {
  onVerified: (info: SessionInfo) => void
  onLocked: (message: string) => void
  onStartAgain: (why?: string) => void
}

export function MfaSetupPage({ onVerified, onLocked, onStartAgain }: Props) {
  const [setup, setSetup] = useState<MfaSetup | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [code, setCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let live = true
    void authApi.mfaSetup().then((result) => {
      if (!live) return
      if (result.ok) setSetup(result.data)
      else if (result.status === 401) onStartAgain(result.problem.message)
      else setLoadError(result.problem.message)
    })
    return () => {
      live = false
    }
  }, [onStartAgain])

  async function copyKey() {
    if (!setup) return
    try {
      await navigator.clipboard.writeText(setup.key_groups.join(''))
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const traceId = newTraceId()
    const log = traceLogger(traceId)
    const digits = code.replace(/\s/g, '')
    if (!/^\d{6}$/.test(digits)) {
      log.warn('mfa input blocked: not 6 digits')
      setError('Enter the 6 digits your app shows now.')
      return
    }
    setBusy(true)
    const result = await authApi.mfaConfirm({ client_trace_id: traceId, code: digits })
    setBusy(false)
    if (result.ok) {
      log.info('mfa passed')
      onVerified(result.data)
      return
    }
    log.warn(`mfa failed (HTTP ${result.status})`)
    setCode('')
    if (result.problem.error === 'locked') return onLocked(result.problem.message)
    if (result.status === 401 && result.problem.error !== 'code_failed') return onStartAgain(result.problem.message)
    setError(
      result.problem.error === 'code_failed'
        ? 'That code did not work. Check the app shows "DiaCausal" and enter the code showing now.'
        : result.problem.message,
    )
  }

  return (
    <AuthShell wide>
      <form noValidate onSubmit={submit} aria-label="Set up your authenticator app" className="flex flex-col gap-[22px]">
        <Heading
          step="First-time setup"
          title="Set up your authenticator app"
          lede="You will do this once. After today you sign in with your password and a 6-digit code."
        />
        {loadError && <Alert tone="danger" word="Could not start the setup">{loadError}</Alert>}
        <div className="grid grid-cols-1 gap-[22px] md:grid-cols-2">
          <Card>
            <h3 className="m-0 text-[19px] font-bold">1. Scan this code</h3>
            <div className="flex size-[232px] items-center justify-center self-start rounded-control border-2 border-border-soft bg-surface p-2">
              {setup ? <img src={setup.qr_image} alt="QR code for your authenticator app" className="size-full" /> : 'Loading…'}
            </div>
            <h3 className="m-0 text-[19px] font-bold">Cannot scan? Enter this key by hand</h3>
            <p className="m-0 flex flex-wrap gap-2 font-mono text-xl font-bold tracking-[0.08em]" aria-label="Setup key">
              {setup?.key_groups.map((group, index) => (
                <span key={index} className="rounded-control border-2 border-border-soft bg-ground px-2.5 py-1">{group}</span>
              ))}
            </p>
            <div className="flex flex-wrap gap-3">
              <GhostButton onClick={() => void copyKey()} disabled={!setup}>
                <Copy aria-hidden="true" className="size-5" /> {copied ? 'Key copied' : 'Copy key'}
              </GhostButton>
            </div>
            <p className="m-0 text-base text-ink-muted">Keep this key private. Anyone with it can generate your codes.</p>
          </Card>
          <Card>
            <h3 className="m-0 text-[19px] font-bold">What to do on your phone</h3>
            <ol className="m-0 flex list-decimal flex-col gap-2 pl-6">
              <li>
                Install <strong>Google Authenticator</strong> or <strong>Microsoft Authenticator</strong> from your
                phone&apos;s app store. Both are free.
              </li>
              <li>Open the app and choose <strong>Add account</strong> (the <strong>+</strong> button), then <strong>Scan a QR code</strong>.</li>
              <li>Point your camera at the code on this page.</li>
              <li>The app will show a 6-digit number that changes every 30 seconds.</li>
            </ol>
            {error && <Alert tone="danger" word="Not confirmed yet">{error}</Alert>}
            <CodeField
              id="confirm"
              label="Enter the 6-digit code to confirm"
              value={code}
              invalid={Boolean(error)}
              onChange={(e) => setCode(e.target.value)}
            />
            <div className="flex flex-wrap gap-3">
              <PrimaryButton type="submit" disabled={busy || !setup}>
                {busy ? 'Checking…' : 'Confirm and finish setup'}
              </PrimaryButton>
            </div>
          </Card>
        </div>
        <IntendedUseNotice />
      </form>
    </AuthShell>
  )
}
