/**
 * The patient panel's values: what the boxes hold, the example patient, and how the
 * panel becomes the `patient` part the API takes. Kept apart from the component so the
 * page can import them without importing React (and so fast refresh keeps working).
 */

import type { PatientPart } from '@/lib/contract'
import { rangeProblem, type PatientField } from './ranges'

/** What the boxes hold while they are being typed in (text, so "8." is allowed). */
export type PanelValues = {
  age_years: string
  diabetes_duration_years: string
  hba1c_percent: string
  egfr_ml_min_1_73m2: string
  bmi_kg_m2: string
  established_ascvd: boolean | null
  ckd: boolean | null
  heart_failure: boolean | null
  past_dka: boolean | null
  recurrent_genital_or_urinary_infection: boolean | null
  past_pancreatitis: boolean | null
  past_hypoglycaemia: 'none' | 'mild' | 'severe' | null
  budget_inr_per_month: string
}

export const EMPTY_PANEL: PanelValues = {
  age_years: '', diabetes_duration_years: '', hba1c_percent: '', egfr_ml_min_1_73m2: '',
  bmi_kg_m2: '', established_ascvd: null, ckd: null, heart_failure: null, past_dka: null,
  recurrent_genital_or_urinary_infection: null, past_pancreatitis: null,
  past_hypoglycaemia: null, budget_inr_per_month: '',
}

/** The example patient from the design, clearly labelled as example data. */
export const EXAMPLE_PANEL: PanelValues = {
  ...EMPTY_PANEL,
  age_years: '58', diabetes_duration_years: '6', hba1c_percent: '8.4',
  egfr_ml_min_1_73m2: '62', bmi_kg_m2: '31.2', established_ascvd: true, ckd: false,
  heart_failure: false, past_dka: false, recurrent_genital_or_urinary_infection: false,
  past_pancreatitis: false, past_hypoglycaemia: 'none', budget_inr_per_month: '1500',
}

export const NUMBER_FIELDS: PatientField[] = [
  'age_years', 'diabetes_duration_years', 'hba1c_percent', 'egfr_ml_min_1_73m2', 'bmi_kg_m2',
]

export const YES_NO_FIELDS = [
  ['established_ascvd', 'Established heart disease'],
  ['ckd', 'Chronic kidney disease'],
  ['heart_failure', 'Heart failure'],
  // The three below are not in design 13-16; the rules in clinical/guardrails.v1.yaml need them.
  ['past_dka', 'Past diabetic ketoacidosis'],
  ['recurrent_genital_or_urinary_infection', 'Repeated genital or urine infections'],
  ['past_pancreatitis', 'Past pancreatitis'],
] as const

export const HINTS: Partial<Record<PatientField, string>> = {
  age_years: '18 or older.',
  budget_inr_per_month: 'What the patient can spend each month.',
}

export function panelProblems(values: PanelValues): Partial<Record<PatientField, string>> {
  const problems: Partial<Record<PatientField, string>> = {}
  for (const field of [...NUMBER_FIELDS, 'budget_inr_per_month' as const]) {
    const problem = rangeProblem(field, values[field])
    if (problem) problems[field] = problem
  }
  return problems
}

/** The panel as the API wants it. Empty boxes are left out, not sent as 0. */
export function toPatientPart(values: PanelValues): PatientPart {
  const part: PatientPart = { type: 'patient' }
  for (const field of [...NUMBER_FIELDS, 'budget_inr_per_month' as const]) {
    const typed = values[field].trim()
    if (typed !== '' && Number.isFinite(Number(typed))) part[field] = Number(typed)
  }
  for (const [field] of YES_NO_FIELDS) if (values[field] !== null) part[field] = values[field]
  if (values.past_hypoglycaemia !== null) part.past_hypoglycaemia = values.past_hypoglycaemia
  return part
}

export function isPanelEmpty(values: PanelValues): boolean {
  return Object.entries(values).every(([key, value]) => value === EMPTY_PANEL[key as keyof PanelValues])
}
