/**
 * What the page knows about the sign-in, kept in memory only (never localStorage):
 *  - the CSRF token, sent as X-CSRF-Token on every state-changing request
 *  - when the page last talked to the server (the server's idle timer counts from there)
 *  - who to tell when the server says the session has ended (App goes back to sign-in)
 * The session itself is an HttpOnly cookie the page cannot read.
 */

export const CSRF_HEADER = 'X-CSRF-Token'

let csrfToken: string | null = null
let lastActivity = Date.now()
const activityListeners = new Set<() => void>()
let onSessionEnded: (() => void) | null = null

export function setCsrfToken(token: string | null): void {
  csrfToken = token
}

export function csrfHeaders(): Record<string, string> {
  return csrfToken ? { [CSRF_HEADER]: csrfToken } : {}
}

export function markActivity(): void {
  lastActivity = Date.now()
  activityListeners.forEach((listener) => listener())
}

export function getLastActivity(): number {
  return lastActivity
}

export function onActivity(listener: () => void): () => void {
  activityListeners.add(listener)
  return () => activityListeners.delete(listener)
}

export function setSessionEndedHandler(handler: (() => void) | null): void {
  onSessionEnded = handler
}

/** The server answered 401: the session is gone (timed out, signed out elsewhere, disabled). */
export function sessionEnded(): void {
  csrfToken = null
  onSessionEnded?.()
}
