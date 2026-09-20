/** The three options as the clinical guardrails leave them, shown in the answer. */

import { ChatPage } from '@/pages/ChatPage'
import { answeredReply, jsonResponse, optionsPart, stubBackend } from '@/test/fakeBackend'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

beforeEach(() => {
  vi.spyOn(console, 'log').mockImplementation(() => {})
  vi.spyOn(console, 'warn').mockImplementation(() => {})
})

async function ask(build: (traceId: string) => ReturnType<typeof answeredReply>) {
  stubBackend((request) => build(request.client_trace_id))
  const user = userEvent.setup()
  render(<ChatPage />)
  await user.type(screen.getByLabelText('Message DiaCausal'), 'What should I add?{Enter}')
  return screen.findByRole('region', { name: 'The three options' })
}

describe('the options from the clinical guardrails', () => {
  it('shows all three with their status', async () => {
    const options = await ask((trace) => ({
      ...answeredReply(trace),
      parts: [
        optionsPart([
          { status: 'do_not_use', reasons: ['SGLT2 inhibitors are not recommended after DKA.'], sources: ['FDA label — 2023'] },
          { status: 'check_first', reasons: ['Heart failure: check before using.'] },
          {},
        ]),
        { type: 'text', text: 'Dummy reply from the DiaCausal backend.' },
      ],
    }))

    const row = (option: string) => options.querySelector(`[data-option="${option}"]`)!
    expect(row('sglt2i')).toHaveTextContent('SGLT2 inhibitor: Do not use')
    expect(row('dpp4i')).toHaveTextContent('DPP-4 inhibitor: Check first')
    expect(row('sulfonylurea')).toHaveTextContent('Sulfonylurea: Safe to consider')
    expect(within(options).getByText('SGLT2 inhibitors are not recommended after DKA.')).toBeInTheDocument()
  })

  it('says the rules are still a draft', async () => {
    const options = await ask((trace) => ({
      ...answeredReply(trace),
      parts: [optionsPart(), { type: 'text', text: 'Dummy reply from the DiaCausal backend.' }],
    }))
    expect(within(options).getByText(/1\.0\.0-draft — draft — not clinically reviewed/)).toBeInTheDocument()
  })

  it('keeps every source one click away', async () => {
    const options = await ask((trace) => ({
      ...answeredReply(trace),
      parts: [optionsPart([{ status: 'check_first', reasons: ['Why'], sources: ['KDIGO 2022 — chapter 1'] }]),
              { type: 'text', text: 'Dummy reply from the DiaCausal backend.' }],
    }))
    const user = userEvent.setup()
    await user.click(within(options).getByText('Where this comes from (1)'))
    expect(within(options).getByText('KDIGO 2022 — chapter 1')).toBeVisible()
  })

  it('shows the abstain notice when the clinical rules stop the question', async () => {
    stubBackend((request) =>
      jsonResponse({
        ...answeredReply(request.client_trace_id),
        outcome: 'blocked',
        parts: [],
        blocked_reason: 'Kidney function is needed before any of the three options can be judged.',
        reason_code: 'insufficient_evidence',
      }),
    )
    const user = userEvent.setup()
    render(<ChatPage />)
    await user.type(screen.getByLabelText('Message DiaCausal'), 'What should I add?{Enter}')

    expect(await screen.findByText('Not enough to go on')).toBeInTheDocument()
    expect(screen.getByText('Kidney function is needed before any of the three options can be judged.')).toBeInTheDocument()
  })
})
