/**
 * The same plausibility limits as backend/app/patient_ranges.py — **not** clinical
 * thresholds. They catch a typing slip (HbA1c 45% for 4.5%) before anything is sent.
 * A test checks these numbers against the backend's copy; the server is the authority.
 */

export type PatientField =
  | 'age_years'
  | 'diabetes_duration_years'
  | 'hba1c_percent'
  | 'egfr_ml_min_1_73m2'
  | 'bmi_kg_m2'
  | 'budget_inr_per_month'

export type Range = { low: number; high: number; unit: string; label: string; decimals: number }

export const RANGES: Record<PatientField, Range> = {
  age_years: { low: 18, high: 110, unit: 'years', label: 'Age', decimals: 0 },
  diabetes_duration_years: { low: 0, high: 80, unit: 'years', label: 'Diabetes duration', decimals: 0 },
  hba1c_percent: { low: 4, high: 20, unit: '%', label: 'HbA1c', decimals: 1 },
  egfr_ml_min_1_73m2: { low: 0, high: 150, unit: 'mL/min/1.73m²', label: 'eGFR', decimals: 0 },
  bmi_kg_m2: { low: 12, high: 70, unit: 'kg/m²', label: 'BMI', decimals: 1 },
  budget_inr_per_month: { low: 0, high: 100_000, unit: '₹ per month', label: 'Budget', decimals: 0 },
}

/** Why this typed value cannot be right, or null. Empty is allowed: the panel starts empty. */
export function rangeProblem(field: PatientField, typed: string): string | null {
  if (typed.trim() === '') return null
  const value = Number(typed)
  if (!Number.isFinite(value)) return `${RANGES[field].label} must be a number.`
  const { low, high, unit, label, decimals } = RANGES[field]
  if (value < low || value > high) {
    const shown = `${value}${unit === '%' ? '%' : ''}`
    return `${label} ${shown}? Check the value — expected ${low.toFixed(decimals)}–${high.toFixed(decimals)} ${unit}.`
  }
  return null
}

/**
 * BMI categories for Indian adults. Source: Misra A, et al. Consensus statement for
 * diagnosis of obesity … for Asian Indians. J Assoc Physicians India 2009;57:163-170.
 * Lower than the WHO cut-offs (25 / 30), which is why they are here and not guessed.
 */
export function bmiCategory(bmi: number): string {
  if (bmi < 18.5) return 'Underweight (<18.5)'
  if (bmi < 23) return 'Normal (18.5–22.9)'
  if (bmi < 25) return 'Overweight (23–24.9)'
  return 'Obese (≥25)'
}
