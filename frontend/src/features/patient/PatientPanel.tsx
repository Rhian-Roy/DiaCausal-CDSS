/**
 * The patient details panel (design/v1/13-16): a side panel on a wide screen, a
 * collapsible sheet on a phone.
 *
 * Why a panel and not free text: the values a clinical rule needs (eGFR, past DKA …) are
 * asked for, not guessed out of a sentence. The browser checks each value is plausible so
 * a slip is caught while typing; the server checks again and has the final say.
 * Values are never logged, here or on the server.
 */

import { cn } from '@/lib/utils'
import type { PatientPart } from '@/lib/contract'
import { ChevronDown, Info, RotateCcw, TriangleAlert } from 'lucide-react'
import { useId, useState } from 'react'
import { bmiCategory, RANGES, rangeProblem, type PatientField } from './ranges'

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

const NUMBER_FIELDS: PatientField[] = [
  'age_years', 'diabetes_duration_years', 'hba1c_percent', 'egfr_ml_min_1_73m2', 'bmi_kg_m2',
]

const YES_NO_FIELDS = [
  ['established_ascvd', 'Established heart disease'],
  ['ckd', 'Chronic kidney disease'],
  ['heart_failure', 'Heart failure'],
  // The three below are not in design 13-16; the rules in clinical/guardrails.v1.yaml need them.
  ['past_dka', 'Past diabetic ketoacidosis'],
  ['recurrent_genital_or_urinary_infection', 'Repeated genital or urine infections'],
  ['past_pancreatitis', 'Past pancreatitis'],
] as const

const HINTS: Partial<Record<PatientField, string>> = {
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

type Props = {
  values: PanelValues
  onChange: (values: PanelValues) => void
  onNewPatient: () => void
  isExample: boolean
}

export function PatientPanel({ values, onChange, onNewPatient, isExample }: Props) {
  const [open, setOpen] = useState(true)
  const problems = panelProblems(values)
  const bmi = Number(values.bmi_kg_m2)
  const bmiShown = values.bmi_kg_m2.trim() !== '' && Number.isFinite(bmi) && !problems.bmi_kg_m2
  const set = (patch: Partial<PanelValues>) => onChange({ ...values, ...patch })

  const status = isExample ? 'Example data' : isPanelEmpty(values) ? 'Not filled in' : 'Entered by you'

  return (
    <aside
      aria-label="Patient details"
      className="w-full shrink-0 overflow-y-auto border-b-2 border-border-soft bg-surface lg:w-[360px] lg:border-r-2 lg:border-b-0"
    >
      <h2 className="sr-only">Patient details</h2>
      <button
        type="button"
        onClick={() => setOpen((shown) => !shown)}
        aria-expanded={open}
        className="sticky top-0 z-2 flex min-h-[52px] w-full cursor-pointer items-center justify-between gap-3 border-b-2 border-border-soft bg-surface px-4 py-3 text-left focus-visible:outline-3 focus-visible:outline-offset-[-3px] focus-visible:outline-pine lg:px-[22px] lg:py-4"
      >
        <span className="text-[19px] font-semibold lg:text-[21px]">Patient details</span>
        <span className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-md border-2 border-border-soft bg-ground px-2.5 py-1 text-[13px] font-bold whitespace-nowrap text-ink-muted">
            {isExample && <Info aria-hidden="true" className="size-4" />}
            {status}
          </span>
          <ChevronDown aria-hidden="true" className={cn('size-5 text-ink-muted transition-transform lg:hidden', open && 'rotate-180')} />
        </span>
      </button>

      {open && (
        <div className="flex flex-col gap-4 p-4 lg:p-[22px]">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onNewPatient}
              className="inline-flex min-h-[52px] cursor-pointer items-center gap-2 rounded-control border-2 border-border-strong bg-surface px-4 text-[17px] font-bold hover:border-ink-muted focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-pine"
            >
              <RotateCcw aria-hidden="true" className="size-5" /> New patient
            </button>
            <span className="text-base text-ink-muted">Clears these details and the conversation.</span>
          </div>

          {NUMBER_FIELDS.map((field) => (
            <NumberField
              key={field}
              field={field}
              value={values[field]}
              hint={HINTS[field]}
              problem={problems[field]}
              onChange={(typed) => set({ [field]: typed } as Partial<PanelValues>)}
              extra={
                field === 'bmi_kg_m2' ? (
                  <>
                    <p className="m-0 text-base font-bold">Category: {bmiShown ? bmiCategory(bmi) : '—'}</p>
                    <p className="m-0 text-sm text-ink-muted">
                      Asian-Indian cut-offs: normal &lt;23 · overweight 23–24.9 · obese ≥25
                    </p>
                  </>
                ) : null
              }
            />
          ))}

          {YES_NO_FIELDS.map(([field, label]) => (
            <Choice
              key={field}
              label={label}
              options={[
                ['Yes', true],
                ['No', false],
              ]}
              value={values[field]}
              onChange={(chosen) => set({ [field]: chosen } as Partial<PanelValues>)}
            />
          ))}

          <Choice
            label="Past hypoglycaemia"
            options={[
              ['None', 'none'],
              ['Mild', 'mild'],
              ['Severe', 'severe'],
            ]}
            value={values.past_hypoglycaemia}
            onChange={(chosen) => set({ past_hypoglycaemia: chosen })}
          />

          <NumberField
            field="budget_inr_per_month"
            value={values.budget_inr_per_month}
            hint={HINTS.budget_inr_per_month}
            problem={problems.budget_inr_per_month}
            onChange={(typed) => set({ budget_inr_per_month: typed })}
          />
        </div>
      )}
    </aside>
  )
}

function NumberField({ field, value, hint, problem, onChange, extra }: {
  field: PatientField
  value: string
  hint?: string
  problem?: string
  onChange: (typed: string) => void
  extra?: React.ReactNode
}) {
  const { label, unit } = RANGES[field]
  return (
    <div className="flex flex-col gap-2">
      <label className="text-lg font-bold" htmlFor={field}>{label}</label>
      {hint && <span id={`${field}-hint`} className="text-base text-ink-muted">{hint}</span>}
      <div className="flex items-center gap-3">
        <input
          id={field}
          inputMode="decimal"
          autoComplete="off"
          value={value}
          aria-invalid={Boolean(problem) || undefined}
          aria-describedby={cn(hint && `${field}-hint`, problem && `${field}-problem`) || undefined}
          onChange={(event) => onChange(event.target.value)}
          className="h-14 w-full min-w-0 rounded-control border-2 border-border-strong bg-surface px-4 text-[19px] focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-pine aria-invalid:border-3 aria-invalid:border-danger-line"
        />
        <span className="shrink-0 text-base whitespace-nowrap text-ink-muted">{unit}</span>
      </div>
      {problem && (
        <p id={`${field}-problem`} role="alert" className="m-0 flex items-start gap-2 text-base font-bold text-danger-ink">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
          {problem}
        </p>
      )}
      {extra}
    </div>
  )
}

function Choice<T extends string | boolean>({ label, options, value, onChange }: {
  label: string
  options: readonly (readonly [string, T])[]
  value: T | null
  onChange: (chosen: T) => void
}) {
  const name = useId()
  return (
    <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
      <legend className="p-0 text-lg font-bold">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {options.map(([text, option]) => {
          const id = `${name}-${String(option)}`
          const chosen = value === option
          return (
            <span key={id}>
              <input
                type="radio"
                id={id}
                name={name}
                checked={chosen}
                onChange={() => onChange(option)}
                className="sr-only peer"
              />
              <label
                htmlFor={id}
                className={cn(
                  'inline-flex min-h-[52px] cursor-pointer items-center rounded-control border-2 border-border-strong px-4 text-[17px] font-bold',
                  'peer-focus-visible:outline-3 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-pine',
                  chosen ? 'border-pine bg-pine text-white' : 'bg-surface',
                )}
              >
                {text}
              </label>
            </span>
          )
        })}
      </div>
    </fieldset>
  )
}
