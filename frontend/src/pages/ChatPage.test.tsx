/**
 * The whole flow in a simulated browser, with a fake backend:
 * type, press Enter, check the console lines and what appears on screen.
 */

import { answeredReply, blockedReply, jsonResponse, stubBackend } from '@/test/fakeBackend'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest'
import { ChatPage } from './ChatPage'

let consoleLog: MockInstance<typeof console.log>
let consoleWarn: MockInstance<typeof console.warn>
let consoleError: MockInstance<typeof console.error>

beforeEach(() => {
  consoleLog = vi.spyOn(console, 'log').mockImplementation(() => {})
  consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {})
  consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
})

const lines = (spy: MockInstance) => spy.mock.calls.map(([line]) => String(line))

function setup() {
  const user = userEvent.setup()
  render(<ChatPage />)
  return { user, box: screen.getByLabelText('Message DiaCausal') }
}

describe('pressing Enter on a message', () => {
  it('prints the four console lines with one trace ID and shows the reply', async () => {
    const fetchMock = stubBackend((request) => answeredReply(request.client_trace_id))
    const { user, box } = setup()

    await user.type(box, 'What should I add to metformin?{Enter}')

    expect(await screen.findByText('Dummy reply from the DiaCausal backend.')).toBeInTheDocument()
    const printed = lines(consoleLog)
    const traceId = /^\[([0-9a-f]{8})\] /.exec(printed[0] ?? '')?.[1]
    expect(printed).toEqual([
      `[${traceId}] input passed`,
      `[${traceId}] ui guard passed`,
      `[${traceId}] medical ui guard passed`,
      `[${traceId}] output passed`,
    ])

    const sent = JSON.parse(String(fetchMock.mock.calls[0][1]?.body))
    expect(sent.client_trace_id).toBe(traceId)
    expect(screen.getByText(traceId!)).toBeInTheDocument() // shown under the answer too
  })

  it('shows the question under "You asked" and empties the box', async () => {
    const fetchMock = stubBackend((request) => answeredReply(request.client_trace_id))
    const { user, box } = setup()

    await user.type(box, '  HbA1c 8.4% on metformin  {Enter}')

    // getByText ignores outer spaces, so check the trimming on what was actually sent.
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body)).parts[0].text).toBe('HbA1c 8.4% on metformin')

    expect(screen.getByText('You asked')).toBeInTheDocument()
    expect(screen.getByText('HbA1c 8.4% on metformin')).toBeInTheDocument()
    expect(box).toHaveValue('')
    expect(await screen.findByText('DiaCausal answered')).toBeInTheDocument()
    expect(screen.getByText(/^2 of 6 stages ran in [\d.]+ ms; the others are not built yet\.$/)).toBeInTheDocument()
  })

  it('also sends with the send button', async () => {
    const fetchMock = stubBackend((request) => answeredReply(request.client_trace_id))
    const { user, box } = setup()

    await user.type(box, 'Hello')
    await user.click(screen.getByRole('button', { name: 'Send message' }))

    expect(await screen.findByText('DiaCausal answered')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

describe('what does not get sent', () => {
  it('Shift+Enter adds a new line instead of sending', async () => {
    const fetchMock = stubBackend((request) => answeredReply(request.client_trace_id))
    const { user, box } = setup()

    await user.type(box, 'line one{Shift>}{Enter}{/Shift}line two')

    expect(box).toHaveValue('line one\nline two')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('Enter that picks a word on a Hindi keyboard does not send (Chrome and Firefox)', () => {
    const fetchMock = stubBackend((request) => answeredReply(request.client_trace_id))
    const { box } = setup()

    fireEvent.change(box, { target: { value: 'मेट' } })
    fireEvent.keyDown(box, { key: 'Enter', isComposing: true })

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('Enter that picks a word on a Hindi keyboard does not send (Safari)', () => {
    const fetchMock = stubBackend((request) => answeredReply(request.client_trace_id))
    const { box } = setup()

    fireEvent.compositionStart(box)
    fireEvent.change(box, { target: { value: 'नमस्ते' } })
    fireEvent.compositionEnd(box)
    fireEvent.keyDown(box, { key: 'Enter', keyCode: 229, isComposing: false })

    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('an empty message is blocked by the ui guard and never sent', async () => {
    const fetchMock = stubBackend((request) => answeredReply(request.client_trace_id))
    const { user, box } = setup()

    await user.type(box, '   {Enter}')

    expect(screen.getByRole('alert')).toHaveTextContent('Type a question first.')
    expect(fetchMock).not.toHaveBeenCalled()
    expect(lines(consoleLog)).toEqual([expect.stringMatching(/^\[[0-9a-f]{8}\] input passed$/)])
    expect(lines(consoleWarn)).toEqual([
      expect.stringMatching(/^\[[0-9a-f]{8}\] ui guard blocked: Type a question first\.$/),
    ])
  })

  it('a second message waits until the first is answered', async () => {
    let answer: (response: Response) => void = () => {}
    stubBackend(() => new Promise<Response>((resolve) => (answer = resolve)))
    const { user, box } = setup()

    await user.type(box, 'first{Enter}')
    await user.type(box, 'second{Enter}')

    expect(screen.getByRole('alert')).toHaveTextContent('Please wait for the current answer.')
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled()
    expect(box).toHaveValue('second')
    answer(new Response('{}'))
  })

  it('the "please wait" notice goes away once the answer arrives', async () => {
    let release = () => {}
    stubBackend(
      (request) =>
        new Promise<Response>((resolve) => {
          release = () => resolve(jsonResponse(answeredReply(request.client_trace_id)))
        }),
    )
    const { user, box } = setup()

    await user.type(box, 'first{Enter}')
    await user.type(box, 'second{Enter}')
    expect(screen.getByRole('alert')).toHaveTextContent('Please wait for the current answer.')

    release()
    expect(await screen.findByText('DiaCausal answered')).toBeInTheDocument()
    expect(screen.queryByText('Please wait for the current answer.')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send message' })).toBeEnabled()
  })
})

describe('when the backend does not answer normally', () => {
  it('shows the reason when the backend blocks the message', async () => {
    stubBackend((request) => blockedReply(request.client_trace_id, 'The message contains language that is not allowed.'))
    const { user, box } = setup()

    await user.type(box, 'hello{Enter}')

    expect(await screen.findByText('Not answered')).toBeInTheDocument()
    expect(screen.getByText('The message contains language that is not allowed.')).toBeInTheDocument()
    expect(lines(consoleLog)).not.toContainEqual(expect.stringContaining('output passed'))
    expect(lines(consoleWarn)).toContainEqual(expect.stringContaining('backend blocked the message'))
  })

  it("shows the backend's 422 message", async () => {
    stubBackend(() =>
      jsonResponse(
        { error: 'invalid_request', message: 'Part 1 text is 9,000 characters long; the limit is 8,000.', problems: [], trace_id: null },
        422,
      ),
    )
    const { user, box } = setup()

    await user.type(box, 'hello{Enter}')

    expect(await screen.findByText("Couldn't get a reply")).toBeInTheDocument()
    expect(screen.getByText('Part 1 text is 9,000 characters long; the limit is 8,000.')).toBeInTheDocument()
    expect(lines(consoleError)).toContainEqual(expect.stringContaining('backend rejected the request'))
  })

  it('says so when the backend is not running', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const { user, box } = setup()

    await user.type(box, 'hello{Enter}')

    expect(await screen.findByText(/Couldn't reach the DiaCausal server/)).toBeInTheDocument()
  })

  it('does not show a reply that fails the output check', async () => {
    stubBackend(() => answeredReply('ffffffff', 'A reply meant for someone else'))
    const { user, box } = setup()

    await user.type(box, 'hello{Enter}')

    expect(await screen.findByText(/did not pass the output check/)).toBeInTheDocument()
    expect(screen.queryByText('A reply meant for someone else')).not.toBeInTheDocument()
    expect(lines(consoleLog)).not.toContainEqual(expect.stringContaining('output passed'))
    expect(lines(consoleError)).toContainEqual(expect.stringContaining('output check failed'))
  })
})

describe('guard notices (design/v1/09-12)', () => {
  it('an identifier is stopped in the browser, never sent, and not shown back', async () => {
    const fetchMock = stubBackend((request) => answeredReply(request.client_trace_id))
    const { user, box } = setup()

    await user.type(box, 'Patient Aadhaar 726018159082, HbA1c 8.4%{Enter}')

    expect(await screen.findByText('Identifier removed — not sent')).toBeInTheDocument()
    expect(screen.getByText('Patient Aadhaar [removed], HbA1c 8.4%')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('726018159082')
    expect(fetchMock).not.toHaveBeenCalled()
    const printed = lines(consoleLog)
    const traceId = /^\[([0-9a-f]{8})\] /.exec(printed[0] ?? '')?.[1]
    expect(printed).toEqual([`[${traceId}] input passed`, `[${traceId}] ui guard passed`])
    expect(lines(consoleWarn)).toEqual([`[${traceId}] medical ui guard blocked (identifier)`])
  })

  it('foul language fails the ui guard, is not sent and the message is not repeated', async () => {
    const fetchMock = stubBackend((request) => answeredReply(request.client_trace_id))
    const { user, box } = setup()

    await user.type(box, 'what bullshit answer is this{Enter}')

    expect(await screen.findByText('Cannot answer as written')).toBeInTheDocument()
    expect(screen.getByText('Message not shown.')).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('bullshit')
    expect(fetchMock).not.toHaveBeenCalled()
    expect(lines(consoleWarn)).toContainEqual(expect.stringMatching(/^\[[0-9a-f]{8}\] ui guard blocked: .*\(language\)$/))
    expect(lines(consoleWarn).join('\n')).not.toContain('bullshit')
  })

  it('an emergency shows only the emergency notice', async () => {
    const fetchMock = stubBackend((request) => answeredReply(request.client_trace_id))
    const { user, box } = setup()

    await user.type(box, 'CBG 45 mg/dL, sweating{Enter}')

    expect(await screen.findByRole('alert')).toHaveTextContent('This may be an emergency. Follow your emergency protocol.')
    expect(screen.getByText('DiaCausal has not answered this question and will not suggest treatment for it.')).toBeInTheDocument()
    expect(screen.queryByText('DiaCausal answered')).not.toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('an out-of-scope question names the reason', async () => {
    stubBackend((request) => answeredReply(request.client_trace_id))
    const { user, box } = setup()

    await user.type(box, 'She is pregnant, 28 weeks, on metformin{Enter}')

    expect(await screen.findByText('Out of scope')).toBeInTheDocument()
    expect(screen.getByText(/This question is about pregnancy\./)).toBeInTheDocument()
  })

  it('shows the notice when only the server guard blocks (the server has the final say)', async () => {
    stubBackend((request) =>
      blockedReply(request.client_trace_id, 'Out of scope: …', 'out_of_scope', 'type_1'),
    )
    const { user, box } = setup()

    await user.type(box, 'HbA1c 8.4% on metformin{Enter}')

    expect(await screen.findByText('Out of scope')).toBeInTheDocument()
    expect(screen.getByText(/This question is about type 1 diabetes\./)).toBeInTheDocument()
    expect(lines(consoleWarn)).toContainEqual(expect.stringContaining('backend blocked the message'))
  })

  it('hides the question when the server blocks it for language', async () => {
    stubBackend((request) => blockedReply(request.client_trace_id, 'The message contains language that is not allowed.', 'language'))
    const { user, box } = setup()

    await user.type(box, 'HbA1c 8.4% on metformin{Enter}')

    expect(await screen.findByText('Cannot answer as written')).toBeInTheDocument()
    expect(screen.queryByText('HbA1c 8.4% on metformin')).not.toBeInTheDocument()
  })
})

describe('the conversation is scrollable (whiteboard: "scrollable")', () => {
  it('scrolls and keeps the newest answer in view', async () => {
    stubBackend((request) => answeredReply(request.client_trace_id))
    const { user, box } = setup()
    const thread = screen.getByRole('log', { name: 'Conversation' }).parentElement!
    expect(thread.className).toContain('overflow-y-auto')

    // jsdom gives every element height 0, so pretend the conversation is taller than the window.
    Object.defineProperty(thread, 'scrollHeight', { value: 2000, configurable: true })
    await user.type(box, 'HbA1c 8.4% on metformin{Enter}')
    await screen.findByText('Dummy reply from the DiaCausal backend.')

    expect(thread.scrollTop).toBe(2000) // scrolled to the newest message
  })
})

describe('how long each stage took', () => {
  it('shows the time beside each stage that ran, and the total', async () => {
    stubBackend((request) => answeredReply(request.client_trace_id))
    const { user, box } = setup()

    await user.type(box, 'HbA1c 8.4% on metformin{Enter}')
    await screen.findByText('Dummy reply from the DiaCausal backend.')

    const list = screen.getByRole('list', { name: 'Pipeline stages' })
    expect(within(list).getAllByText(/1\.2 ms/)).toHaveLength(2) // backend_guard and output_guard
    expect(screen.getByText(/2 of 6 stages ran in 2\.4 ms/)).toBeInTheDocument()
  })
})
