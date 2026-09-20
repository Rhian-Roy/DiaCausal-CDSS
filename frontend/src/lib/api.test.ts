import { answeredReply, blockedReply, jsonResponse, stages, stubBackend } from '@/test/fakeBackend'
import { describe, expect, it, vi } from 'vitest'
import { checkOutput, postChat } from './api'
import { setCsrfToken, setSessionEndedHandler } from './authSession'

describe('postChat', () => {
  it('sends the contract request to /api/v1/chat', async () => {
    const fetchMock = stubBackend((request) => answeredReply(request.client_trace_id))

    await postChat('Hello', 'a1b2c3d4')

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/chat')
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({
      schema_version: '1.0',
      client_trace_id: 'a1b2c3d4',
      parts: [{ type: 'text', text: 'Hello' }],
    })
  })

  it('sends the CSRF token and the session cookie', async () => {
    const fetchMock = stubBackend((request) => answeredReply(request.client_trace_id))
    setCsrfToken('token-123')

    await postChat('Hello', 'a1b2c3d4')

    expect(fetchMock.mock.calls[0][1]).toMatchObject({
      credentials: 'same-origin',
      headers: expect.objectContaining({ 'X-CSRF-Token': 'token-123' }),
    })
    setCsrfToken(null)
  })

  it('a 401 means the session ended: it says so and tells the app', async () => {
    stubBackend(() => jsonResponse({ error: 'session_expired', message: 'Your session has ended.' }, 401))
    const ended = vi.fn()
    setSessionEndedHandler(ended)

    expect(await postChat('x', 'a1b2c3d4')).toEqual({
      kind: 'failed',
      message: 'Your session has ended. Please sign in again.',
    })
    expect(ended).toHaveBeenCalledOnce()
    setSessionEndedHandler(null)
  })

  it('returns the body of a 200 reply', async () => {
    stubBackend((request) => answeredReply(request.client_trace_id))

    const result = await postChat('Hello', 'a1b2c3d4')

    expect(result).toEqual({ kind: 'ok', body: answeredReply('a1b2c3d4') })
  })

  it("passes on the backend's message for a 422", async () => {
    stubBackend(() =>
      jsonResponse(
        { error: 'invalid_request', message: 'Part 1 text is 8,001 characters long.', problems: [], trace_id: null },
        422,
      ),
    )

    expect(await postChat('x', 'a1b2c3d4')).toEqual({
      kind: 'rejected',
      message: 'Part 1 text is 8,001 characters long.',
    })
  })

  it('reports a server error with its status code', async () => {
    stubBackend(() => new Response('Internal Server Error', { status: 500 }))

    const result = await postChat('x', 'a1b2c3d4')

    expect(result.kind).toBe('failed')
    expect(result.kind === 'failed' && result.message).toContain('HTTP 500')
  })

  it('reports an unreachable backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    expect(await postChat('x', 'a1b2c3d4')).toEqual({
      kind: 'failed',
      message: "Couldn't reach the DiaCausal server. Check that the backend is running.",
    })
  })

  it('reports a timeout', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new DOMException('timed out', 'TimeoutError')))

    expect(await postChat('x', 'a1b2c3d4')).toEqual({
      kind: 'failed',
      message: 'The server took too long to answer. Try again.',
    })
  })
})

describe('checkOutput', () => {
  it('accepts a proper answer for this trace ID', () => {
    expect(checkOutput(answeredReply('a1b2c3d4'), 'a1b2c3d4').ok).toBe(true)
  })

  it('accepts a proper blocked reply', () => {
    expect(checkOutput(blockedReply('a1b2c3d4', 'The message is empty.'), 'a1b2c3d4').ok).toBe(true)
  })

  it("rejects a reply meant for another message's trace ID", () => {
    expect(checkOutput(answeredReply('ffffffff'), 'a1b2c3d4')).toEqual({
      ok: false,
      reason: 'the reply is for trace "ffffffff", not a1b2c3d4',
    })
  })

  it('rejects stages that are missing or out of order', () => {
    const reply = answeredReply('a1b2c3d4')
    expect(checkOutput({ ...reply, stages: reply.stages.slice(1) }, 'a1b2c3d4').ok).toBe(false)
    expect(checkOutput({ ...reply, stages: [...reply.stages].reverse() }, 'a1b2c3d4').ok).toBe(false)
  })

  it('rejects an answer whose output guard did not pass', () => {
    const reply = { ...answeredReply('a1b2c3d4'), stages: stages({ output_guard: 'skipped' }) }
    expect(checkOutput(reply, 'a1b2c3d4')).toEqual({ ok: false, reason: 'the output guard did not pass' })
  })

  it('rejects an empty answer and non-text parts', () => {
    const reply = answeredReply('a1b2c3d4')
    expect(checkOutput({ ...reply, parts: [{ type: 'text', text: '  ' }] }, 'a1b2c3d4').ok).toBe(false)
    expect(checkOutput({ ...reply, parts: [{ type: 'image', url: 'x' }] }, 'a1b2c3d4').ok).toBe(false)
  })

  it.each([
    ['a wrong schema_version', { schema_version: '2.0' }],
    ['an unknown outcome', { outcome: 'maybe', blocked_reason: 'x' }],
    ['no intended-use notice', { intended_use: undefined }],
    ['an unknown stage status', { stages: stages({ causal_engine: 'weird' as never }) }],
    ['an unknown reason_code', { reason_code: 'rude' }],
    ['a missing reason_code', { reason_code: undefined }],
    ['an unknown scope_topic', { scope_topic: 'gout' }],
    ['no request_id', { request_id: undefined }],
  ])('rejects a reply with %s', (_, patch) => {
    expect(checkOutput({ ...answeredReply('a1b2c3d4'), ...patch }, 'a1b2c3d4').ok).toBe(false)
  })

  it('accepts a blocked reply with a known reason_code and topic', () => {
    expect(checkOutput(blockedReply('a1b2c3d4', 'x', 'out_of_scope', 'pregnancy'), 'a1b2c3d4').ok).toBe(true)
  })

  it('rejects a blocked reply that does not say why', () => {
    expect(checkOutput({ ...blockedReply('a1b2c3d4', 'x'), blocked_reason: null }, 'a1b2c3d4').ok).toBe(false)
  })

  it.each([null, 'text', [], 42])('rejects a body that is not an object (%j)', (body) => {
    expect(checkOutput(body, 'a1b2c3d4').ok).toBe(false)
  })
})
