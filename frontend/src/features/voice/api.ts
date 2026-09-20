/** POST /api/v1/transcribe (backend/app/voice/routes.py): the recording in, text out. */

import { csrfHeaders, markActivity, sessionEnded } from '@/lib/authSession'

export const TRANSCRIBE_URL = '/api/v1/transcribe'

export type TranscribeResult = { ok: true; transcript: string; seconds: number } | { ok: false; message: string }

export async function postTranscribe(audio: Blob, traceId: string): Promise<TranscribeResult> {
  let response: Response
  try {
    response = await fetch(TRANSCRIBE_URL, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': audio.type || 'audio/webm', 'X-Trace-Id': traceId, ...csrfHeaders() },
      body: audio,
      signal: AbortSignal.timeout(60_000),
    })
  } catch {
    return { ok: false, message: "Couldn't reach the DiaCausal server to turn speech into text." }
  }
  const body = (await response.json().catch(() => null)) as
    | { transcript?: unknown; duration_seconds?: unknown; message?: unknown }
    | null
  if (response.status === 401) {
    sessionEnded()
    return { ok: false, message: 'Your session has ended. Please sign in again.' }
  }
  if (response.ok && typeof body?.transcript === 'string') {
    markActivity()
    return { ok: true, transcript: body.transcript, seconds: Number(body.duration_seconds) || 0 }
  }
  return {
    ok: false,
    message: typeof body?.message === 'string' ? body.message : `Speech-to-text failed (HTTP ${response.status}).`,
  }
}
