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
export type StageResult = { name: StageName; status: StageStatus; detail: string }

export type ChatResponse = {
  schema_version: typeof SCHEMA_VERSION
  trace_id: string
  outcome: 'answered' | 'blocked'
  parts: Part[]
  blocked_reason: string | null
  stages: StageResult[]
  intended_use: string
}

export type ErrorResponse = {
  error: 'invalid_request'
  message: string
  problems: { field: string; message: string }[]
  trace_id: string | null
}
