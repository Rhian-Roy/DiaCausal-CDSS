/** A stand-in for the FastAPI backend, so frontend tests run without a server. */

import {
  INTENDED_USE,
  STAGE_ORDER,
  type ChatRequest,
  type ChatResponse,
  type OptionResult,
  type OptionsPart,
  type ReasonCode,
  type ScopeTopic,
  type StageName,
  type StageResult,
  type StageStatus,
} from '@/lib/contract'
import { vi } from 'vitest'

export function stages(statuses: Partial<Record<StageName, StageStatus>> = {}): StageResult[] {
  return STAGE_ORDER.map((name) => {
    const ranToday = name === 'backend_guard' || name === 'output_guard'
    const status = statuses[name] ?? (ranToday ? 'passed' : 'skipped')
    return { name, status, detail: status === 'skipped' ? 'Not built yet.' : 'ok', duration_ms: status === 'skipped' ? 0 : 1.2 }
  })
}

/** The three options as the clinical guardrails return them. */
export function optionsPart(overrides: Partial<OptionResult>[] = []): OptionsPart {
  const base: OptionResult[] = [
    { option: 'sglt2i', name: 'SGLT2 inhibitor', status: 'safe_to_consider', reasons: [], sources: [], notes: [], rule_ids: [] },
    { option: 'dpp4i', name: 'DPP-4 inhibitor', status: 'safe_to_consider', reasons: [], sources: [], notes: [], rule_ids: [] },
    { option: 'sulfonylurea', name: 'Sulfonylurea', status: 'safe_to_consider', reasons: [], sources: [], notes: [], rule_ids: [] },
  ]
  return {
    type: 'options',
    options: base.map((option, index) => ({ ...option, ...overrides[index] })),
    rules_version: '1.0.0-draft',
    draft_warning: 'draft — not clinically reviewed',
  }
}

export function answeredReply(traceId: string, text = 'Dummy reply from the DiaCausal backend.'): ChatResponse {
  return {
    schema_version: '1.0',
    trace_id: traceId,
    outcome: 'answered',
    parts: [{ type: 'text', text }],
    blocked_reason: null,
    reason_code: null,
    scope_topic: null,
    stages: stages(),
    intended_use: INTENDED_USE,
    request_id: '6f1c2d3e-4a5b-4c6d-8e9f-0a1b2c3d4e5f',
  }
}

export function blockedReply(
  traceId: string,
  reason: string,
  reasonCode: ReasonCode | null = null,
  scopeTopic: ScopeTopic | null = null,
): ChatResponse {
  const later = { clinical_guardrails: 'skipped', output_guard: 'skipped' } as const
  return {
    ...answeredReply(traceId),
    outcome: 'blocked',
    parts: [],
    blocked_reason: reason,
    reason_code: reasonCode,
    scope_topic: scopeTopic,
    stages: stages({ backend_guard: 'blocked', ...later }),
  }
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

/** Replace `fetch` with a fake backend; `reply` gets the parsed request. */
export function stubBackend(reply: (request: ChatRequest) => Response | ChatResponse | Promise<Response>) {
  const fetchMock = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
    const request = JSON.parse(String(init?.body)) as ChatRequest
    const result = await reply(request)
    return result instanceof Response ? result : jsonResponse(result)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
