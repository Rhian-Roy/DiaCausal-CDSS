/**
 * Step 1 of 2 (design/v1/01-03): user ID + password + CAPTCHA.
 * Console, with a fresh trace ID per attempt:
 *   [id] login input passed   -> sent ->   [id] captcha passed, [id] password passed
 * The server answers every wrong detail the same way ("Those details did not match").
 */

import { newTraceId, traceLogger } from '@/lib/trace'
import { Check, Clock, RefreshCw, Volume2 } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { authApi, type Captcha, type LoginOk } from './api'
import { Alert, AuthShell, Card, Field, GhostButton, Heading, IntendedUseNotice, LinkButton, PrimaryButton } from './ui'

type Problem =
  | { kind: 'mismatch'; attemptsLeft?: number }
  | { kind: 'locked'; minutes: number; message: string }
  | { kind: 'other'; message: string }
  | { kind: 'input'; message: string }

type Props = { onSignedIn: (result: LoginOk) => void; notice?: string | null }

export function SignInPage({ onSignedIn, notice }: Props) {
  const [userId, setUserId] = useState('')
  const [password, setPassword] = useState('')
  const [answer, setAnswer] = useState('')
  const [captcha, setCaptcha] = useState<Captcha | null>(null)
  const [captchaError, setCaptchaError] = useState<string | null>(null)
  const [problem, setProblem] = useState<Problem | null>(null)
  const [busy, setBusy] = useState(false)
  const [help, setHelp] = useState(false)
  const firstField = useRef<HTMLInputElement>(null)

  const showCaptcha = useCallback((result: Awaited<ReturnType<typeof authApi.captcha>>) => {
    setCaptcha(result.ok ? result.data : null)
    setCaptchaError(result.ok ? null : result.problem.message)
  }, [])

  const newCaptcha = useCallback(async () => {
    setAnswer('')
    showCaptcha(await authApi.captcha())
  }, [showCaptcha])

  useEffect(() => {
    let live = true
    void authApi.captcha().then((result) => live && showCaptcha(result)) // the first one
    return () => {
      live = false
    }
  }, [showCaptcha])

  function playAudio() {
    if (captcha) void new Audio(captcha.audio_url).play().catch(() => setCaptchaError('This browser could not play the audio.'))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    const traceId = newTraceId()
    const log = traceLogger(traceId)
    const code = answer.replace(/\s/g, '')
    if (!userId.trim() || !password || !/^\d{6}$/.test(code) || !captcha) {
      log.warn('login input blocked: a field is empty or the CAPTCHA is not 6 digits')
      setProblem({ kind: 'input', message: 'Enter your user ID, your password and the 6 digits shown.' })
      return
    }
    log.info('login input passed')
    setBusy(true)
    const result = await authApi.login({
      client_trace_id: traceId,
      user_id: userId.trim(),
      password,
      captcha_id: captcha.captcha_id,
      captcha_answer: code,
    })
    setBusy(false)
    if (result.ok) {
      log.info('captcha passed')
      log.info('password passed')
      setPassword('')
      onSignedIn(result.data)
      return
    }

    log.warn(`login failed (HTTP ${result.status})`)
    setPassword('')
    const { problem: p } = result
    if (p.error === 'locked') {
      setProblem({ kind: 'locked', minutes: Math.max(1, Math.ceil((p.retry_after_seconds ?? 60) / 60)), message: p.message })
      return
    }
    setProblem(p.error === 'login_failed' ? { kind: 'mismatch', attemptsLeft: p.attempts_left } : { kind: 'other', message: p.message })
    void newCaptcha()
    firstField.current?.focus()
  }

  if (problem?.kind === 'locked') {
    return (
      <AuthShell>
        <div className="flex flex-col gap-[22px]">
          <Heading step="Step 1 of 2" title="Sign in" />
          <Alert tone="check" word="Signing in is locked">{problem.message}</Alert>
          <Card>
            <h3 className="m-0 text-[19px] font-bold">What to do now</h3>
            <ul className="m-0 flex list-none flex-col gap-2 p-0">
              <li className="flex gap-2">
                <Clock aria-hidden="true" className="mt-1 size-5 shrink-0 text-ink-muted" />
                <span>Wait {problem.minutes} minute{problem.minutes > 1 ? 's' : ''} and sign in again. The lock clears on its own.</span>
              </li>
              <li className="flex gap-2">
                <Check aria-hidden="true" className="mt-1 size-5 shrink-0 text-ink-muted" />
                <span>If you need access sooner, ask your site administrator to unlock your account.</span>
              </li>
            </ul>
          </Card>
          <div className="flex flex-wrap gap-3">
            <PrimaryButton type="button" onClick={() => { setProblem(null); void newCaptcha() }}>
              Sign in
            </PrimaryButton>
          </div>
          <IntendedUseNotice />
        </div>
      </AuthShell>
    )
  }

  const mismatch = problem?.kind === 'mismatch'
  return (
    <AuthShell wide>
      <form
        noValidate
        onSubmit={submit}
        aria-label="Sign in"
        className="grid grid-cols-1 items-start gap-4 md:grid-cols-[minmax(0,560px)_minmax(0,1fr)] md:gap-x-16 md:gap-y-[22px] md:[&>*:not([data-captcha])]:col-start-1"
      >
        <Heading step="Step 1 of 2" title="Sign in" lede="Second-line therapy support for adults already taking metformin." />

        {notice && <Alert tone="info" word="Please sign in again">{notice}</Alert>}
        {mismatch && (
          <Alert tone="danger" word="Those details did not match">
            Enter your user ID, password and a new set of digits, then try again.
            {problem.attemptsLeft !== undefined &&
              ` ${problem.attemptsLeft} attempt${problem.attemptsLeft === 1 ? '' : 's'} left before sign-in locks.`}
          </Alert>
        )}
        {(problem?.kind === 'other' || problem?.kind === 'input') && (
          <Alert tone="check" word="Check and try again">{problem.message}</Alert>
        )}

        <Field
          ref={firstField}
          id="user"
          label="User ID"
          autoComplete="username"
          placeholder="Hospital user ID"
          autoFocus
          value={userId}
          invalid={mismatch}
          onChange={(e) => setUserId(e.target.value)}
        />
        <Field
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          placeholder="••••••••••"
          value={password}
          invalid={mismatch}
          onChange={(e) => setPassword(e.target.value)}
        />

        {/* Beside the fields on a wide screen, but before "Sign in" in the page and keyboard order. */}
        <Card data-captcha className="md:col-start-2 md:row-span-8 md:row-start-1">
          <p aria-hidden="true" className="m-0 text-lg font-bold">Type the 6 digits shown</p>
          <div className="flex h-24 items-center justify-center overflow-hidden rounded-control border-2 border-dashed border-border-strong bg-surface">
            {captcha ? (
              <img src={captcha.image} alt="CAPTCHA: six digits. Use Play audio to hear them." className="h-full" />
            ) : (
              <span className="text-ink-muted">{captchaError ?? 'Loading…'}</span>
            )}
          </div>
          <div className="flex flex-wrap gap-3">
            <GhostButton onClick={() => void newCaptcha()}>
              <RefreshCw aria-hidden="true" className="size-5" /> New image
            </GhostButton>
            <GhostButton onClick={playAudio} disabled={!captcha}>
              <Volume2 aria-hidden="true" className="size-5" /> Play audio
            </GhostButton>
          </div>
          <Field
            id="captcha"
            label="Type the 6 digits shown"
            hideLabel
            inputMode="numeric"
            maxLength={7}
            autoComplete="off"
            placeholder="6 digits"
            value={answer}
            invalid={mismatch}
            onChange={(e) => setAnswer(e.target.value)}
            hint="Digits only. The audio reads the same 6 digits."
          />
        </Card>

        <PrimaryButton type="submit" disabled={busy} className="justify-self-start">
          {busy ? 'Signing in…' : 'Sign in'}
        </PrimaryButton>

        <LinkButton onClick={() => setHelp((open) => !open)} aria-expanded={help}>
          Trouble signing in?
        </LinkButton>
        {help && (
          <p className="m-0 text-base text-ink-muted">
            Your site administrator can unlock your account, reset a forgotten password, or reset your
            authenticator app if you lost your phone. There is no self-service reset.
          </p>
        )}

        <IntendedUseNotice />
      </form>
    </AuthShell>
  )
}
