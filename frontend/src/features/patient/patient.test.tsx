/**
 * The patient panel (design/v1/13-16): ranges, BMI category, what is sent, and
 * "New patient" clearing both the panel and the conversation.
 */

import { ChatPage } from '@/pages/ChatPage'
import { answeredReply, stubBackend } from '@/test/fakeBackend'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { EMPTY_PANEL, EXAMPLE_PANEL, isPanelEmpty, panelProblems, toPatientPart } from './PatientPanel'
import { bmiCategory, RANGES, rangeProblem, type PatientField } from './ranges'

const FIELDS = Object.keys(RANGES) as PatientField[]

describe('the plausibility ranges', () => {
  it.each(FIELDS)('%s accepts both ends and refuses just outside', (field) => {
    const { low, high } = RANGES[field]
    expect(rangeProblem(field, String(low))).toBeNull()
    expect(rangeProblem(field, String(high))).toBeNull()
    expect(rangeProblem(field, String(low - 1))).not.toBeNull()
    expect(rangeProblem(field, String(high + 1))).not.toBeNull()
  })

  it('allows an empty box: the panel starts empty', () => {
    expect(FIELDS.every((field) => rangeProblem(field, '') === null)).toBe(true)
  })

  it('names the field and the expected range, as design 15 does', () => {
    expect(rangeProblem('hba1c_percent', '45')).toBe('HbA1c 45%? Check the value — expected 4.0–20.0 %.')
  })

  it('refuses something that is not a number', () => {
    expect(rangeProblem('age_years', 'fifty')).toBe('Age must be a number.')
  })
})

describe('BMI category (Asian-Indian cut-offs, Misra et al. JAPI 2009)', () => {
  it.each([
    [17, 'Underweight'], [18.5, 'Normal'], [22.9, 'Normal'],
    [23, 'Overweight'], [24.9, 'Overweight'], [25, 'Obese'], [31.2, 'Obese'],
  ])('%s kg/m² is %s', (bmi, category) => {
    expect(bmiCategory(bmi)).toContain(category)
  })
})

describe('what gets sent', () => {
  it('leaves empty boxes out instead of sending zero', () => {
    expect(toPatientPart(EMPTY_PANEL)).toEqual({ type: 'patient' })
  })

  it('sends numbers as numbers and the answers as true/false', () => {
    expect(toPatientPart(EXAMPLE_PANEL)).toEqual({
      type: 'patient', age_years: 58, diabetes_duration_years: 6, hba1c_percent: 8.4,
      egfr_ml_min_1_73m2: 62, bmi_kg_m2: 31.2, established_ascvd: true, ckd: false,
      heart_failure: false, past_dka: false, recurrent_genital_or_urinary_infection: false,
      past_pancreatitis: false, past_hypoglycaemia: 'none', budget_inr_per_month: 1500,
    })
  })

  it('knows when the panel is empty', () => {
    expect(isPanelEmpty(EMPTY_PANEL)).toBe(true)
    expect(isPanelEmpty(EXAMPLE_PANEL)).toBe(false)
  })

  it('finds every out-of-range value at once', () => {
    const problems = panelProblems({ ...EMPTY_PANEL, hba1c_percent: '45', age_years: '4' })
    expect(Object.keys(problems).sort()).toEqual(['age_years', 'hba1c_percent'])
  })
})

describe('the panel on screen', () => {
  function setup() {
    const fetchMock = stubBackend((request) => answeredReply(request.client_trace_id))
    const user = userEvent.setup()
    render(<ChatPage />)
    return { user, fetchMock, panel: screen.getByRole('complementary', { name: 'Patient details' }) }
  }

  const sentPatient = (fetchMock: ReturnType<typeof vi.fn>) =>
    JSON.parse(String(fetchMock.mock.calls.at(-1)?.[1]?.body)).parts.find(
      (part: { type: string }) => part.type === 'patient',
    )

  it('starts as the example patient, badged "Example data" (design 16)', () => {
    const { panel } = setup()
    expect(within(panel).getByText('Example data')).toBeInTheDocument()
    expect(within(panel).getByLabelText('HbA1c')).toHaveValue('8.4')
    expect(within(panel).getByText('Category: Obese (≥25)')).toBeInTheDocument()
  })

  it('says "Entered by you" once a value is changed (design 14)', async () => {
    const { user, panel } = setup()
    await user.clear(within(panel).getByLabelText('HbA1c'))
    await user.type(within(panel).getByLabelText('HbA1c'), '9.1')
    expect(within(panel).getByText('Entered by you')).toBeInTheDocument()
    expect(within(panel).queryByText('Example data')).not.toBeInTheDocument()
  })

  it('shows the out-of-range message next to the field (design 15)', async () => {
    const { user, panel } = setup()
    const hba1c = within(panel).getByLabelText('HbA1c')
    await user.clear(hba1c)
    await user.type(hba1c, '45')

    expect(within(panel).getByRole('alert')).toHaveTextContent('HbA1c 45%? Check the value — expected 4.0–20.0 %.')
    expect(hba1c).toHaveAttribute('aria-invalid', 'true')
  })

  it('sends the panel with the question', async () => {
    const { user, fetchMock } = setup()
    await user.type(screen.getByLabelText('Message DiaCausal'), 'What should I add?{Enter}')
    await screen.findByText('Dummy reply from the DiaCausal backend.')

    expect(sentPatient(fetchMock)).toMatchObject({ hba1c_percent: 8.4, egfr_ml_min_1_73m2: 62, established_ascvd: true })
  })

  it('does not send a value it has flagged as out of range', async () => {
    const { user, fetchMock, panel } = setup()
    const hba1c = within(panel).getByLabelText('HbA1c')
    await user.clear(hba1c)
    await user.type(hba1c, '45')
    await user.type(screen.getByLabelText('Message DiaCausal'), 'What should I add?{Enter}')
    await screen.findByText('Dummy reply from the DiaCausal backend.')

    const sent = sentPatient(fetchMock)
    expect(sent.hba1c_percent).toBeUndefined()
    expect(sent.egfr_ml_min_1_73m2).toBe(62) // the rest still goes
  })

  it('the Yes/No answers the guardrail rules need are on the panel', () => {
    const { panel } = setup()
    for (const label of ['Established heart disease', 'Chronic kidney disease', 'Heart failure',
                         'Past diabetic ketoacidosis', 'Repeated genital or urine infections',
                         'Past pancreatitis', 'Past hypoglycaemia']) {
      expect(within(panel).getByRole('group', { name: label })).toBeInTheDocument()
    }
  })

  it('records a Yes/No answer and sends it', async () => {
    const { user, fetchMock, panel } = setup()
    await user.click(within(within(panel).getByRole('group', { name: 'Heart failure' })).getByText('Yes'))
    await user.type(screen.getByLabelText('Message DiaCausal'), 'Which add-on?{Enter}')
    await screen.findByText('Dummy reply from the DiaCausal backend.')

    expect(sentPatient(fetchMock).heart_failure).toBe(true)
  })

  it('"New patient" clears the panel AND the conversation (design 13)', async () => {
    const { user, panel } = setup()
    await user.type(screen.getByLabelText('Message DiaCausal'), 'First question about metformin{Enter}')
    await screen.findByText('Dummy reply from the DiaCausal backend.')

    await user.click(within(panel).getByRole('button', { name: 'New patient' }))

    expect(within(panel).getByLabelText('HbA1c')).toHaveValue('')
    expect(within(panel).getByText('Not filled in')).toBeInTheDocument()
    expect(within(panel).getByText('Category: —')).toBeInTheDocument()
    expect(screen.queryByText('First question about metformin')).not.toBeInTheDocument()
    expect(screen.queryByText('Dummy reply from the DiaCausal backend.')).not.toBeInTheDocument()
  })

  it('a question after "New patient" gets a fresh trace ID and an empty panel', async () => {
    const { user, fetchMock, panel } = setup()
    await user.type(screen.getByLabelText('Message DiaCausal'), 'First question{Enter}')
    await screen.findByText('Dummy reply from the DiaCausal backend.')
    const firstTrace = JSON.parse(String(fetchMock.mock.calls[0][1]?.body)).client_trace_id

    await user.click(within(panel).getByRole('button', { name: 'New patient' }))
    await user.type(screen.getByLabelText('Message DiaCausal'), 'Second question{Enter}')
    await screen.findByText('Dummy reply from the DiaCausal backend.')

    const second = JSON.parse(String(fetchMock.mock.calls.at(-1)?.[1]?.body))
    expect(second.client_trace_id).not.toBe(firstTrace)
    expect(sentPatient(fetchMock)).toEqual({ type: 'patient' })
  })

  it('can be folded away on a small screen', async () => {
    const { user, panel } = setup()
    const toggle = within(panel).getByRole('button', { name: /Patient details/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(within(panel).queryByLabelText('HbA1c')).not.toBeInTheDocument()
  })
})
