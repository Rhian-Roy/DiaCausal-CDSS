/**
 * The whole sign-in in a simulated browser, with a fake backend:
 * sign in -> authenticator set-up or code -> intended use -> chat -> sign out / timeout.
 */

import { answeredReply, jsonResponse } from '@/test/fakeBackend'
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest'
import App from './App'
import type { SessionInfo } from './features/auth/api'
import { markActivity } from './lib/authSession'

let consoleLog: MockInstance<typeof console.log>
let consoleWarn: MockInstance<typeof console.warn>
beforeEach(() => {
  consoleLog = vi.spyOn(console, 'log').mockImplementation(() => {})
  consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {})
  vi.spyOn(console, 'error').mockImplementation(() => {})
  markActivity()
})
afterEach(() => vi.useRealTimers())

const lines = (spy: MockInstance) => spy.mock.calls.map(([line]) => String(line))

function info(overrides: Partial<SessionInfo> = {}): SessionInfo {
  return {
    user_id: 'dr.rao', display_name: 'Dr Rao', role: 'clinician', stage: 'full',
    needs_mfa_setup: false, needs_acknowledgement: false, intended_use_version: '1',
    csrf_token: 'csrf-full', idle_timeout_seconds: 900, warning_seconds: 120, ...overrides,
  }
}

type Handler = (body: Record<string, unknown> | null, init: RequestInit) => Response | Promise<Response>

/** A fake backend: `routes` maps "METHOD /path" to a handler. Records every call. */
function backend(routes: Record<string, Handler>) {
  const calls: { key: string; body: Record<string, unknown> | null; headers: Record<string, string> }[] = []
  const fetchMock = vi.fn(async (url: RequestInfo | URL, init: RequestInit = {}) => {
    const key = `${init.method ?? 'GET'} ${String(url)}`
    const body = init.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null
    calls.push({ key, body, headers: (init.headers ?? {}) as Record<string, string> })
    const handler = routes[key]
    return handler ? handler(body, init) : jsonResponse({ error: 'not_found', message: 'no route' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

const CAPTCHA = { captcha_id: 'cap1', image: 'data:image/png;base64,AAAA', audio_url: '/api/v1/auth/captcha/cap1/audio' }
const notSignedIn = () => jsonResponse({ error: 'not_signed_in', message: 'Please sign in.' }, 401)

async function fillSignIn(user: ReturnType<typeof userEvent.setup>, digits = '123456') {
  await user.type(await screen.findByLabelText('User ID'), 'dr.rao')
  await user.type(screen.getByLabelText('Password'), 'correct horse battery staple')
  await user.type(screen.getByLabelText('Type the 6 digits shown'), digits)
}

describe('signing in', () => {
  it('first sign-in: ID + password + CAPTCHA, authenticator set-up, intended use, then chat', async () => {
    const calls = backend({
      'GET /api/v1/auth/me': notSignedIn,
      'GET /api/v1/auth/captcha': () => jsonResponse(CAPTCHA),
      'POST /api/v1/auth/login': () => jsonResponse({ next: 'mfa_setup', user_id: 'dr.rao', csrf_token: 'csrf-half' }),
      'POST /api/v1/auth/mfa/setup': () =>
        jsonResponse({ qr_image: 'data:image/svg+xml;base64,AAAA', key_groups: ['ABCD', 'EFGH'], issuer: 'DiaCausal', account: 'dr.rao' }),
      'POST /api/v1/auth/mfa/confirm': () => jsonResponse(info({ needs_acknowledgement: true })),
      'POST /api/v1/auth/acknowledge': () => jsonResponse(info()),
      'POST /api/v1/chat': (body) => jsonResponse(answeredReply(String(body?.client_trace_id))),
    })
    const user = userEvent.setup()
    render(<App />)

    await fillSignIn(user)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Set up your authenticator app' })).toBeInTheDocument()
    const login = calls.find((c) => c.key === 'POST /api/v1/auth/login')!
    expect(login.body).toMatchObject({ user_id: 'dr.rao', captcha_id: 'cap1', captcha_answer: '123456' })
    const trace = String(login.body?.client_trace_id)
    expect(lines(consoleLog)).toEqual([`[${trace}] login input passed`, `[${trace}] captcha passed`, `[${trace}] password passed`])

    expect(screen.getByAltText('QR code for your authenticator app')).toBeInTheDocument()
    expect(screen.getByText('ABCD')).toBeInTheDocument()
    expect(calls.find((c) => c.key === 'POST /api/v1/auth/mfa/setup')?.headers['X-CSRF-Token']).toBe('csrf-half')

    await user.type(screen.getByLabelText('Enter the 6-digit code to confirm'), '654321')
    await user.click(screen.getByRole('button', { name: 'Confirm and finish setup' }))
    expect(await screen.findByRole('heading', { name: 'How to use DiaCausal' })).toBeInTheDocument()
    expect(lines(consoleLog).at(-1)).toMatch(/^\[[0-9a-f]{8}\] mfa passed$/)

    await user.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByText('Tick “I understand” to continue.')).toBeInTheDocument()
    await user.click(screen.getByLabelText('I understand'))
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(await screen.findByText('Dr Rao')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Message DiaCausal'), 'HbA1c 8.4% on metformin{Enter}')
    expect(await screen.findByText('Dummy reply from the DiaCausal backend.')).toBeInTheDocument()
    expect(calls.find((c) => c.key === 'POST /api/v1/chat')?.headers['X-CSRF-Token']).toBe('csrf-full')
  })

  it('second sign-in asks for the 6-digit code', async () => {
    backend({
      'GET /api/v1/auth/me': notSignedIn,
      'GET /api/v1/auth/captcha': () => jsonResponse(CAPTCHA),
      'POST /api/v1/auth/login': () => jsonResponse({ next: 'mfa', user_id: 'dr.rao', csrf_token: 'csrf-half' }),
      'POST /api/v1/auth/mfa': () => jsonResponse(info()),
    })
    const user = userEvent.setup()
    render(<App />)
    await fillSignIn(user)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Enter your 6-digit code' })).toBeInTheDocument()
    expect(screen.getByText('Signed in as dr.rao.')).toBeInTheDocument()
    await user.type(screen.getByLabelText('6-digit code'), '123456{Enter}')
    expect(await screen.findByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  })

  it('the CAPTCHA sits inside the form, before "Sign in"', async () => {
    backend({ 'GET /api/v1/auth/me': notSignedIn, 'GET /api/v1/auth/captcha': () => jsonResponse(CAPTCHA) })
    render(<App />)
    const form = await screen.findByRole('form', { name: 'Sign in' })
    const captchaBox = within(form).getByLabelText('Type the 6 digits shown')
    const signIn = within(form).getByRole('button', { name: 'Sign in' })
    expect(captchaBox.compareDocumentPosition(signIn) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(within(form).getByRole('button', { name: /New image/ })).toBeInTheDocument()
    expect(within(form).getByRole('button', { name: /Play audio/ })).toBeInTheDocument()
    expect(await within(form).findByAltText(/CAPTCHA/)).toHaveAttribute('src', CAPTCHA.image)
  })

  it('"New image" fetches a new CAPTCHA', async () => {
    const calls = backend({ 'GET /api/v1/auth/me': notSignedIn, 'GET /api/v1/auth/captcha': () => jsonResponse(CAPTCHA) })
    const user = userEvent.setup()
    render(<App />)
    await user.click(await screen.findByRole('button', { name: /New image/ }))
    expect(calls.filter((c) => c.key === 'GET /api/v1/auth/captcha')).toHaveLength(2)
  })

  it('an incomplete form is not sent', async () => {
    const calls = backend({ 'GET /api/v1/auth/me': notSignedIn, 'GET /api/v1/auth/captcha': () => jsonResponse(CAPTCHA) })
    const user = userEvent.setup()
    render(<App />)
    await fillSignIn(user, '12')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByText('Enter your user ID, your password and the 6 digits shown.')).toBeInTheDocument()
    expect(calls.some((c) => c.key === 'POST /api/v1/auth/login')).toBe(false)
    expect(lines(consoleWarn)[0]).toMatch(/^\[[0-9a-f]{8}\] login input blocked/)
  })

  it('wrong details: one message for everything, attempts left, a new CAPTCHA, password cleared', async () => {
    const calls = backend({
      'GET /api/v1/auth/me': notSignedIn,
      'GET /api/v1/auth/captcha': () => jsonResponse(CAPTCHA),
      'POST /api/v1/auth/login': () =>
        jsonResponse({ error: 'login_failed', message: 'Those details did not match', attempts_left: 3 }, 401),
    })
    const user = userEvent.setup()
    render(<App />)
    await fillSignIn(user)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Those details did not match')).toBeInTheDocument()
    expect(screen.getByText(/3 attempts left before sign-in locks/)).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toHaveValue('')
    expect(calls.filter((c) => c.key === 'GET /api/v1/auth/captcha')).toHaveLength(2)
    expect(lines(consoleWarn).at(-1)).toMatch(/login failed \(HTTP 401\)/)
    expect(lines(consoleLog).some((l) => l.includes('password passed'))).toBe(false)
  })

  it('shows the locked screen', async () => {
    backend({
      'GET /api/v1/auth/me': notSignedIn,
      'GET /api/v1/auth/captcha': () => jsonResponse(CAPTCHA),
      'POST /api/v1/auth/login': () =>
        jsonResponse({ error: 'locked', message: 'Too many attempts. Try again in 15 minutes or ask your administrator.', retry_after_seconds: 900 }, 423),
    })
    const user = userEvent.setup()
    render(<App />)
    await fillSignIn(user)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Signing in is locked')).toBeInTheDocument()
    expect(screen.getByText(/Wait 15 minutes and sign in again/)).toBeInTheDocument()
  })

  it('a wrong code shows design 05', async () => {
    backend({
      'GET /api/v1/auth/me': notSignedIn,
      'GET /api/v1/auth/captcha': () => jsonResponse(CAPTCHA),
      'POST /api/v1/auth/login': () => jsonResponse({ next: 'mfa', user_id: 'dr.rao', csrf_token: 'x' }),
      'POST /api/v1/auth/mfa': () => jsonResponse({ error: 'code_failed', message: 'That code did not work', attempts_left: 4 }, 401),
    })
    const user = userEvent.setup()
    render(<App />)
    await fillSignIn(user)
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await user.type(await screen.findByLabelText('6-digit code'), '000000{Enter}')
    expect(await screen.findByText('That code did not work')).toBeInTheDocument()
    expect(screen.getByLabelText('6-digit code')).toHaveValue('')
  })
})

describe('when signed in', () => {
  function signedInBackend(extra: Record<string, Handler> = {}) {
    return backend({ 'GET /api/v1/auth/me': () => jsonResponse(info()), ...extra })
  }

  it('a reload keeps you signed in (the cookie decides)', async () => {
    signedInBackend()
    render(<App />)
    expect(await screen.findByText('Dr Rao')).toBeInTheDocument()
  })

  it('an unacknowledged user sees the intended-use page first', async () => {
    backend({ 'GET /api/v1/auth/me': () => jsonResponse(info({ needs_acknowledgement: true })) })
    render(<App />)
    expect(await screen.findByRole('heading', { name: 'How to use DiaCausal' })).toBeInTheDocument()
  })

  it('"Sign out" ends the session on the server and clears the conversation', async () => {
    const calls = signedInBackend({
      'POST /api/v1/chat': (body) => jsonResponse(answeredReply(String(body?.client_trace_id))),
      'POST /api/v1/auth/logout': () => new Response(null, { status: 204 }),
      'GET /api/v1/auth/captcha': () => jsonResponse(CAPTCHA),
    })
    const user = userEvent.setup()
    render(<App />)
    await user.type(await screen.findByLabelText('Message DiaCausal'), 'HbA1c 8.4% on metformin{Enter}')
    await screen.findByText('Dummy reply from the DiaCausal backend.')

    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    expect(await screen.findByText('You have signed out.')).toBeInTheDocument()
    expect(screen.queryByText('HbA1c 8.4% on metformin')).not.toBeInTheDocument()
    expect(calls.find((c) => c.key === 'POST /api/v1/auth/logout')?.headers['X-CSRF-Token']).toBe('csrf-full')
  })

  it('a 401 from chat (session ended on the server) goes back to sign-in', async () => {
    signedInBackend({ 'POST /api/v1/chat': notSignedIn, 'GET /api/v1/auth/captcha': () => jsonResponse(CAPTCHA) })
    const user = userEvent.setup()
    render(<App />)
    await user.type(await screen.findByLabelText('Message DiaCausal'), 'HbA1c 8.4%{Enter}')
    expect(await screen.findByText('Your session has ended. Please sign in again.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('warns 2 minutes before the idle timeout; "Stay signed in" keeps the session', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const calls = signedInBackend({ 'POST /api/v1/auth/keepalive': () => jsonResponse(info()) })
    render(<App />)
    await screen.findByText('Dr Rao')
    markActivity()

    await act(() => vi.advanceTimersByTimeAsync(779_000))
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    await act(() => vi.advanceTimersByTimeAsync(2_000))
    const dialog = screen.getByRole('alertdialog')
    expect(within(dialog).getByText('You’ll be signed out in 2 minutes')).toBeInTheDocument()

    await act(async () => within(dialog).getByRole('button', { name: 'Stay signed in' }).click())
    await act(() => vi.advanceTimersByTimeAsync(1_000))
    expect(calls.some((c) => c.key === 'POST /api/v1/auth/keepalive')).toBe(true)
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })

  it('signs out by itself when the idle time is up', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const calls = signedInBackend({
      'POST /api/v1/auth/logout': () => new Response(null, { status: 204 }),
      'GET /api/v1/auth/captcha': () => jsonResponse(CAPTCHA),
    })
    render(<App />)
    await screen.findByText('Dr Rao')
    markActivity()
    await act(() => vi.advanceTimersByTimeAsync(901_000))
    expect(await screen.findByText('You were signed out because the session was idle.')).toBeInTheDocument()
    expect(calls.some((c) => c.key === 'POST /api/v1/auth/logout')).toBe(true)
  })
})
