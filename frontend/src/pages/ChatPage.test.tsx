/**
 * The whole flow in a simulated browser, with a fake backend:
 * type, press Enter, check the console lines and what appears on screen.
 */

import { answeredReply, blockedReply, jsonResponse, stubBackend } from '@/test/fakeBackend'
import { render, screen } from '@testing-library/react'
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
    stubBackend((request) => answeredReply(request.client_trace_id))
    const { user, box } = setup()

    await user.type(box, '  HbA1c 8.4% on metformin  {Enter}')

    expect(screen.getByText('You asked')).toBeInTheDocument()
    expect(screen.getByText('HbA1c 8.4% on metformin')).toBeInTheDocument()
    expect(box).toHaveValue('')
    expect(await screen.findByText('DiaCausal answered')).toBeInTheDocument()
    expect(screen.getByText('2 of 6 stages ran; the others are not built yet.')).toBeInTheDocument()
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
