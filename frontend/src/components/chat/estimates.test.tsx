/** The causal engine's estimates and the cited evidence, shown in the answer. */

import { checkOutput } from '@/lib/api'
import type { ChatResponse, EstimatesPart, EvidencePart } from '@/lib/contract'
import { ChatPage } from '@/pages/ChatPage'
import { answeredReply, optionsPart, stubBackend } from '@/test/fakeBackend'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

beforeEach(() => {
  vi.spyOn(console, 'log').mockImplementation(() => {})
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

const r = (value: number, ci_low: number, ci_high: number) => ({ value, ci_low, ci_high })

const ESTIMATES: EstimatesPart = {
  type: 'estimates',
  outcome: 'Change in HbA1c at 6 months (percentage points; negative = better control)',
  estimates: [
    { option: 'sglt2i', name: 'SGLT2 inhibitor', status: 'excluded', hba1c_change: null, weight_change_kg: null,
      hypo_risk_pct: null, propensity: null, reason: 'Not recommended when eGFR < 45.', rule_ids: ['R01'] },
    { option: 'dpp4i', name: 'DPP-4 inhibitor', status: 'estimate', hba1c_change: r(-0.68, -1.09, -0.27),
      weight_change_kg: r(0.56, -0.68, 1.8), hypo_risk_pct: r(1.2, 0, 6.9), propensity: 0.54, reason: null, rule_ids: [] },
    { option: 'sulfonylurea', name: 'Sulfonylurea', status: 'insufficient_evidence', hba1c_change: null,
      weight_change_kg: null, hypo_risk_pct: null, propensity: 0.01, reason: 'Too few similar patients.', rule_ids: [] },
  ],
  comparisons: [],
  method: 'DR-learner on cross-fitted AIPW scores, HC3 95% interval',
  engine_version: 'engine 0.3.0',
  data_note: 'Estimates come from an India-calibrated synthetic cohort, not real patients.',
  decision: 'Decision support only. The clinician decides.',
}

const EVIDENCE: EvidencePart = {
  type: 'evidence',
  status: 'answered',
  sentences: [{ text: 'SGLT2 inhibitors may lead to ketoacidosis.', cites: [1] }],
  passages: [{ n: 1, source_id: 'S19', title: 'FDA Drug Safety Communication', section: 'Safety Announcement',
               page: null, text: 'FDA warns that SGLT2 inhibitors may lead to ketoacidosis.' }],
  backend: 'template',
  note: '',
}

async function ask(parts: unknown[]) {
  stubBackend((request) => ({ ...answeredReply(request.client_trace_id), parts: parts as ChatResponse['parts'] }))
  const user = userEvent.setup()
  render(<ChatPage />)
  await user.type(screen.getByLabelText('Message DiaCausal'), 'What should I add?{Enter}')
  return user
}

describe('the causal engine and the evidence in the answer', () => {
  it('shows each estimate with its 95% range and no number for the others', async () => {
    await ask([optionsPart(), ESTIMATES, EVIDENCE, { type: 'text', text: 'Summary.' }])
    const card = await screen.findByRole('region', { name: 'Estimates for this patient' })
    const row = (option: string) => card.querySelector(`[data-option="${option}"]`)!
    expect(row('dpp4i')).toHaveTextContent('−0.68')
    expect(row('dpp4i')).toHaveTextContent('95% range −1.09 to −0.27')
    expect(row('sglt2i')).toHaveTextContent('Excluded, no estimate')
    expect(row('sglt2i')).not.toHaveTextContent('95% range')
    expect(row('sulfonylurea')).toHaveTextContent('Insufficient evidence')
    expect(within(card).getByText(/synthetic cohort/)).toBeInTheDocument()
    expect(within(card).getByText(/The clinician decides/)).toBeInTheDocument()
  })

  it('quotes the evidence with its citation and keeps the passage one click away', async () => {
    const user = await ask([optionsPart(), EVIDENCE, { type: 'text', text: 'Summary.' }])
    const evidence = await screen.findByRole('region', { name: 'Evidence' })
    expect(within(evidence).getByText(/“SGLT2 inhibitors may lead to ketoacidosis\.”/)).toBeInTheDocument()
    expect(within(evidence).getByText('[1]')).toBeInTheDocument()
    await user.click(within(evidence).getByText('The 1 passages and their sources'))
    expect(within(evidence).getByText(/S19: FDA Drug Safety Communication/)).toBeVisible()
  })

  it('says insufficient evidence instead of guessing', async () => {
    await ask([{ ...EVIDENCE, status: 'insufficient_evidence', sentences: [], passages: [] },
               { type: 'text', text: 'Insufficient evidence.' }])
    const evidence = await screen.findByRole('region', { name: 'Evidence' })
    expect(within(evidence).getByText('Evidence: insufficient')).toBeInTheDocument()
  })
})

describe('the output check on the new parts', () => {
  const body = (parts: unknown[]) => ({ ...answeredReply('abcd1234'), parts: [...parts, { type: 'text', text: 'x' }] })

  it('accepts well-formed estimates and evidence', () => {
    expect(checkOutput(body([ESTIMATES, EVIDENCE]), 'abcd1234').ok).toBe(true)
  })

  it('refuses an estimate without its 95% range', () => {
    const bad = { ...ESTIMATES, estimates: [{ ...ESTIMATES.estimates[1], hba1c_change: null }] }
    expect(checkOutput(body([bad]), 'abcd1234').ok).toBe(false)
  })

  it('refuses a number on an excluded option', () => {
    const bad = { ...ESTIMATES, estimates: [{ ...ESTIMATES.estimates[0], hba1c_change: r(-1, -2, 0) }] }
    expect(checkOutput(body([bad]), 'abcd1234').ok).toBe(false)
  })

  it('refuses a sentence that cites a passage that was not sent', () => {
    const bad = { ...EVIDENCE, sentences: [{ text: 'Made up.', cites: [7] }] }
    expect(checkOutput(body([bad]), 'abcd1234').ok).toBe(false)
  })
})
