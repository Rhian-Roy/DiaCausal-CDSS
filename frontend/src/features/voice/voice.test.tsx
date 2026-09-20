/**
 * The mic button with a fake microphone (MediaRecorder + getUserMedia) and fake backend:
 * permission only on press, recording indicator, 30-second limit, transcript into the box
 * (never sent), numbers highlighted, and the usual guards when Enter is pressed.
 */

import { ChatPage } from '@/pages/ChatPage'
import { answeredReply, jsonResponse } from '@/test/fakeBackend'
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest'
import { HighlightNumbers } from './HighlightNumbers'

let consoleLog: MockInstance<typeof console.log>
let consoleWarn: MockInstance<typeof console.warn>
const lines = (spy: MockInstance) => spy.mock.calls.map(([line]) => String(line))

const trackStop = vi.fn()
let getUserMedia: ReturnType<typeof vi.fn>

class FakeRecorder {
  static instances: FakeRecorder[] = []
  state: 'inactive' | 'recording' = 'inactive'
  mimeType = 'audio/webm;codecs=opus'
  ondataavailable: ((event: { data: Blob }) => void) | null = null
  onstop: (() => void) | null = null
  stream: MediaStream
  constructor(stream: MediaStream) {
    this.stream = stream
    FakeRecorder.instances.push(this)
  }
  start() {
    this.state = 'recording'
  }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['fake-opus-audio'], { type: this.mimeType }) })
    this.onstop?.()
  }
}

beforeEach(() => {
  consoleLog = vi.spyOn(console, 'log').mockImplementation(() => {})
  consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {})
  vi.spyOn(console, 'error').mockImplementation(() => {})
  FakeRecorder.instances = []
  trackStop.mockReset()
  getUserMedia = vi.fn(async () => ({ getTracks: () => [{ stop: trackStop }] }) as unknown as MediaStream)
  vi.stubGlobal('MediaRecorder', FakeRecorder)
  Object.defineProperty(navigator, 'mediaDevices', { value: { getUserMedia }, configurable: true })
})
afterEach(() => vi.useRealTimers())

type Route = (init: RequestInit) => Response | Promise<Response>
function backend(transcribe: Route) {
  const calls: { url: string; init: RequestInit }[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: RequestInfo | URL, init: RequestInit = {}) => {
      calls.push({ url: String(url), init })
      if (String(url) === '/api/v1/transcribe') return transcribe(init)
      const request = JSON.parse(String(init.body))
      return jsonResponse(answeredReply(request.client_trace_id))
    }),
  )
  return calls
}

const transcript = (text: string) => () =>
  jsonResponse({ trace_id: 'x', transcript: text, duration_seconds: 3.2 })

describe('the mic button', () => {
  it('asks for the microphone only when pressed', async () => {
    backend(transcript('x'))
    const user = userEvent.setup()
    render(<ChatPage />)
    expect(getUserMedia).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Dictate message' }))
    expect(getUserMedia).toHaveBeenCalledOnce()
    expect(getUserMedia).toHaveBeenCalledWith({ audio: true })
  })

  it('shows it is recording; the second press stops, and the text goes INTO the box, not sent', async () => {
    const calls = backend(transcript('HbA1c 8.4% on metformin 1 g twice daily, eGFR 62.'))
    const user = userEvent.setup()
    render(<ChatPage />)

    await user.click(screen.getByRole('button', { name: 'Dictate message' }))
    expect(screen.getByRole('status')).toHaveTextContent('Recording 0:00 / 0:30')
    expect(screen.getByRole('button', { name: 'Stop recording' })).toHaveAttribute('aria-pressed', 'true')

    await user.click(screen.getByRole('button', { name: 'Stop recording' }))
    expect(await screen.findByDisplayValue('HbA1c 8.4% on metformin 1 g twice daily, eGFR 62.')).toBeInTheDocument()
    expect(trackStop).toHaveBeenCalled() // microphone released

    const sent = calls.find((c) => c.url === '/api/v1/transcribe')!
    expect((sent.init.headers as Record<string, string>)['Content-Type']).toBe('audio/webm;codecs=opus')
    expect((sent.init.headers as Record<string, string>)['X-Trace-Id']).toMatch(/^[0-9a-f]{8}$/)
    expect(calls.some((c) => c.url === '/api/v1/chat')).toBe(false) // never auto-sent

    const trace = (sent.init.headers as Record<string, string>)['X-Trace-Id']
    expect(lines(consoleLog)).toEqual([
      expect.stringMatching(new RegExp(`^\\[${trace}\\] voice: [\\d.]+ s recorded$`)),
      `[${trace}] voice: transcript put in the message box (not sent)`,
    ])
  })

  it('highlights every number for the doctor to check', async () => {
    backend(transcript('eGFR 45, should I add empagliflozin 10 mg?'))
    const user = userEvent.setup()
    render(<ChatPage />)
    await user.click(screen.getByRole('button', { name: 'Dictate message' }))
    await user.click(screen.getByRole('button', { name: 'Stop recording' }))

    expect(await screen.findByText(/check the numbers before you press Enter/i)).toBeInTheDocument()
    const marked = within(screen.getByTestId('dictated'))
      .getAllByText(/./, { selector: 'mark' })
      .map((mark) => mark.textContent)
    expect(marked).toEqual(['45', '10'])
  })

  it('Enter then sends it through the usual guards, and the check box goes away', async () => {
    const calls = backend(transcript('HbA1c 8.4% on metformin, what next?'))
    const user = userEvent.setup()
    render(<ChatPage />)
    await user.click(screen.getByRole('button', { name: 'Dictate message' }))
    await user.click(screen.getByRole('button', { name: 'Stop recording' }))
    await screen.findByDisplayValue('HbA1c 8.4% on metformin, what next?')

    consoleLog.mockClear()
    await user.type(screen.getByLabelText('Message DiaCausal'), '{Enter}')
    expect(await screen.findByText('Dummy reply from the DiaCausal backend.')).toBeInTheDocument()
    expect(lines(consoleLog).map((l) => l.replace(/^\[\w+\] /, ''))).toEqual([
      'input passed', 'ui guard passed', 'medical ui guard passed', 'output passed',
    ])
    expect(calls.filter((c) => c.url === '/api/v1/chat')).toHaveLength(1)
    expect(screen.queryByTestId('dictated')).not.toBeInTheDocument()
  })

  it('a dictated identifier is still stopped by the guards', async () => {
    const calls = backend(transcript('Patient mobile 9876543210, HbA1c 9'))
    const user = userEvent.setup()
    render(<ChatPage />)
    await user.click(screen.getByRole('button', { name: 'Dictate message' }))
    await user.click(screen.getByRole('button', { name: 'Stop recording' }))
    await screen.findByDisplayValue('Patient mobile 9876543210, HbA1c 9')
    await user.type(screen.getByLabelText('Message DiaCausal'), '{Enter}')

    expect(await screen.findByText('Identifier removed — not sent')).toBeInTheDocument()
    expect(calls.some((c) => c.url === '/api/v1/chat')).toBe(false)
    expect(lines(consoleWarn).at(-1)).toMatch(/medical ui guard blocked \(identifier\)/)
  })

  it('adds to what was already typed', async () => {
    backend(transcript('eGFR 45.'))
    const user = userEvent.setup()
    render(<ChatPage />)
    await user.type(screen.getByLabelText('Message DiaCausal'), 'On metformin.')
    await user.click(screen.getByRole('button', { name: 'Dictate message' }))
    await user.click(screen.getByRole('button', { name: 'Stop recording' }))
    expect(await screen.findByDisplayValue('On metformin. eGFR 45.')).toBeInTheDocument()
  })

  it('stops by itself after 30 seconds', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    backend(transcript('Consider sitagliptin 100 mg once daily.'))
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    render(<ChatPage />)
    await user.click(screen.getByRole('button', { name: 'Dictate message' }))
    await act(() => vi.advanceTimersByTimeAsync(15_000))
    expect(screen.getByRole('status')).toHaveTextContent('Recording 0:15 / 0:30')
    await act(() => vi.advanceTimersByTimeAsync(15_500))
    expect(FakeRecorder.instances[0].state).toBe('inactive')
    expect(await screen.findByDisplayValue('Consider sitagliptin 100 mg once daily.')).toBeInTheDocument()
  })

  it('says so when the microphone is blocked', async () => {
    backend(transcript('x'))
    getUserMedia.mockRejectedValueOnce(new DOMException('denied', 'NotAllowedError'))
    const user = userEvent.setup()
    render(<ChatPage />)
    await user.click(screen.getByRole('button', { name: 'Dictate message' }))
    expect(await screen.findByText(/The microphone is blocked/)).toBeInTheDocument()
  })

  it("shows the server's message when speech-to-text fails", async () => {
    backend(() => jsonResponse({ error: 'audio_too_long', message: 'The recording is 32 seconds; the limit is 30.' }, 413))
    const user = userEvent.setup()
    render(<ChatPage />)
    await user.click(screen.getByRole('button', { name: 'Dictate message' }))
    await user.click(screen.getByRole('button', { name: 'Stop recording' }))
    expect(await screen.findByText('The recording is 32 seconds; the limit is 30.')).toBeInTheDocument()
    expect(screen.getByLabelText('Message DiaCausal')).toHaveValue('')
  })

  it('says so when this browser cannot record', async () => {
    vi.stubGlobal('MediaRecorder', undefined)
    Reflect.deleteProperty(window, 'MediaRecorder')
    backend(transcript('x'))
    const user = userEvent.setup()
    render(<ChatPage />)
    await user.click(screen.getByRole('button', { name: 'Dictate message' }))
    expect(await screen.findByText(/This browser cannot record audio/)).toBeInTheDocument()
  })
})

describe('HighlightNumbers', () => {
  it('marks stand-alone numbers and decimals, not the 1 in HbA1c', () => {
    render(<p><HighlightNumbers text="HbA1c 8.4%, eGFR 62, 1,000 mg" /></p>)
    expect(screen.getAllByText(/./, { selector: 'mark' }).map((m) => m.textContent)).toEqual(['8.4', '62', '1,000'])
  })
})
