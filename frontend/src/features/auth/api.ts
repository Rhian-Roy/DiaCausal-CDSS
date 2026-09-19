/**
 * The sign-in endpoints (backend/app/auth/routes.py; shapes in backend/app/auth/schemas.py).
 * Every call returns a result object and never throws.
 */

import { csrfHeaders, markActivity, setCsrfToken } from '@/lib/authSession'

export type SessionInfo = {
  user_id: string
  display_name: string
  role: 'clinician' | 'admin'
  stage: 'password_ok' | 'full'
  needs_mfa_setup: boolean
  needs_acknowledgement: boolean
  intended_use_version: string
  csrf_token: string
  idle_timeout_seconds: number
  warning_seconds: number
}

export type AuthError = {
  error: string
  message: string
  attempts_left?: number
  retry_after_seconds?: number
}

export type Captcha = { captcha_id: string; image: string; audio_url: string }
export type LoginOk = { next: 'mfa' | 'mfa_setup'; user_id: string; csrf_token: string }
export type MfaSetup = { qr_image: string; key_groups: string[]; issuer: string; account: string }

export type Result<T> = { ok: true; data: T } | { ok: false; status: number; problem: AuthError }

const UNREACHABLE: AuthError = {
  error: 'unreachable',
  message: "Couldn't reach the DiaCausal server. Check that the backend is running.",
}

async function request<T>(method: 'GET' | 'POST', url: string, body?: unknown): Promise<Result<T>> {
  let response: Response
  try {
    response = await fetch(url, {
      method,
      credentials: 'same-origin',
      headers: {
        ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(method === 'POST' ? csrfHeaders() : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(20_000),
    })
  } catch {
    return { ok: false, status: 0, problem: UNREACHABLE }
  }
  const data: unknown = await response.json().catch(() => null)
  if (response.ok) {
    markActivity()
    const token = (data as { csrf_token?: unknown } | null)?.csrf_token
    if (typeof token === 'string') setCsrfToken(token)
    return { ok: true, data: data as T }
  }
  const problem =
    data && typeof data === 'object' && 'message' in data
      ? (data as AuthError)
      : { error: 'server', message: `The server could not answer (HTTP ${response.status}).` }
  return { ok: false, status: response.status, problem }
}

export const authApi = {
  captcha: () => request<Captcha>('GET', '/api/v1/auth/captcha'),
  login: (body: { client_trace_id: string; user_id: string; password: string; captcha_id: string; captcha_answer: string }) =>
    request<LoginOk>('POST', '/api/v1/auth/login', body),
  mfaSetup: () => request<MfaSetup>('POST', '/api/v1/auth/mfa/setup', {}),
  mfaConfirm: (body: { client_trace_id: string; code: string }) =>
    request<SessionInfo>('POST', '/api/v1/auth/mfa/confirm', body),
  mfa: (body: { client_trace_id: string; code: string }) => request<SessionInfo>('POST', '/api/v1/auth/mfa', body),
  acknowledge: (version: string) => request<SessionInfo>('POST', '/api/v1/auth/acknowledge', { version }),
  me: () => request<SessionInfo>('GET', '/api/v1/auth/me'),
  keepalive: () => request<SessionInfo>('POST', '/api/v1/auth/keepalive', {}),
  logout: async () => {
    const result = await request<null>('POST', '/api/v1/auth/logout', {})
    setCsrfToken(null)
    return result
  },
}
