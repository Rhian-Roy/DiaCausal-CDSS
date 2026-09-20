/**
 * TypeScript copy of the API contract in backend/app/schemas.py.
 * Keep the two in sync: change one, change the other.
 */

export const SCHEMA_VERSION = '1.0'
export const MAX_TEXT_CHARS = 8000

export const INTENDED_USE =
  'Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.'

export type TextPart = { type: 'text'; text: string }

/** The patient details from the panel (design/v1/13-16). Mirrors PatientPart in schemas.py. */
export type PatientPart = {
  type: 'patient'
  age_years?: number | null
  diabetes_duration_years?: number | null
  hba1c_percent?: number | null
  egfr_ml_min_1_73m2?: number | null
  bmi_kg_m2?: number | null
  established_ascvd?: boolean | null
  ckd?: boolean | null
  heart_failure?: boolean | null
  past_dka?: boolean | null
  recurrent_genital_or_urinary_infection?: boolean | null
  past_pancreatitis?: boolean | null
  past_hypoglycaemia?: 'none' | 'mild' | 'severe' | null
  budget_inr_per_month?: number | null
}

export type Part = TextPart | PatientPart

/** What the clinical guardrails decided about one option (OptionResult in schemas.py). */
export const OPTION_STATUSES = ['safe_to_consider', 'check_first', 'do_not_use'] as const
export type OptionStatus = (typeof OPTION_STATUSES)[number]

export type OptionResult = {
  option: 'sglt2i' | 'dpp4i' | 'sulfonylurea'
  name: string
  status: OptionStatus
  reasons: string[]
  sources: string[]
  notes: string[]
  rule_ids: string[]
}

/** A reply part carrying the three options (OptionsPart in schemas.py). */
export type OptionsPart = {
  type: 'options'
  options: OptionResult[]
  rules_version: string
  draft_warning: string | null
}

export type ReplyPart = TextPart | OptionsPart

export type ChatRequest = {
  schema_version: typeof SCHEMA_VERSION
  client_trace_id: string
  parts: Part[]
}

/** Part types this version of the API understands (SUPPORTED_PART_TYPES in settings.py). */
export const SUPPORTED_PART_TYPES = ['text', 'patient'] as const

export const STAGE_ORDER = [
  'backend_guard',
  'clinical_guardrails',
  'causal_engine',
  'rag_retrieval',
  'llm_explanation',
  'output_guard',
] as const

export type StageName = (typeof STAGE_ORDER)[number]
export type StageStatus = 'passed' | 'blocked' | 'skipped'
export type StageResult = { name: StageName; status: StageStatus; detail: string; duration_ms: number }

/** Why backend_guard blocked a message; the page shows the matching notice (designs 09-12). */
export const REASON_CODES = ['identifier', 'out_of_scope', 'emergency', 'language', 'insufficient_evidence'] as const
export type ReasonCode = (typeof REASON_CODES)[number]

/** Which out-of-scope topic (only with reason_code "out_of_scope"). */
export const SCOPE_TOPICS = ['type_1', 'pregnancy', 'under_18', 'dka_hhs', 'insulin_start'] as const
export type ScopeTopic = (typeof SCOPE_TOPICS)[number]

export type ChatResponse = {
  schema_version: typeof SCHEMA_VERSION
  trace_id: string
  outcome: 'answered' | 'blocked'
  parts: ReplyPart[] // text, plus the options part once the guardrails have run
  blocked_reason: string | null
  reason_code: ReasonCode | null
  scope_topic: ScopeTopic | null
  stages: StageResult[]
  intended_use: string
  request_id: string // server-generated UUID: this request's row in audit_log
}

export type ErrorResponse = {
  error: 'invalid_request'
  message: string
  problems: { field: string; message: string }[]
  trace_id: string | null
}
