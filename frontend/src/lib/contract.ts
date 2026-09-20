/**
 * TypeScript copy of the API contract in backend/app/schemas.py.
 * Keep the two in sync: change one, change the other.
 */

export const SCHEMA_VERSION = '1.0'
export const MAX_TEXT_CHARS = 8000

export const INTENDED_USE =
  'Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.'

export type TextPart = { type: 'text'; text: string }
export type Part = TextPart

export type ChatRequest = {
  schema_version: typeof SCHEMA_VERSION
  client_trace_id: string
  parts: Part[]
}

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
export const REASON_CODES = ['identifier', 'out_of_scope', 'emergency', 'language'] as const
export type ReasonCode = (typeof REASON_CODES)[number]

/** Which out-of-scope topic (only with reason_code "out_of_scope"). */
export const SCOPE_TOPICS = ['type_1', 'pregnancy', 'under_18', 'dka_hhs', 'insulin_start'] as const
export type ScopeTopic = (typeof SCOPE_TOPICS)[number]

export type ChatResponse = {
  schema_version: typeof SCHEMA_VERSION
  trace_id: string
  outcome: 'answered' | 'blocked'
  parts: Part[]
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
