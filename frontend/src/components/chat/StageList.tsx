import type { StageName, StageResult, StageStatus } from '@/lib/contract'
import { ShieldCheck } from 'lucide-react'

const LABELS: Record<StageName, string> = {
  backend_guard: 'Backend guard',
  clinical_guardrails: 'Clinical guardrails',
  causal_engine: 'Causal engine',
  rag_retrieval: 'Guideline retrieval',
  llm_explanation: 'Explanation',
  output_guard: 'Output guard',
}

const STATUS_STYLE: Record<StageStatus, string> = {
  passed: 'font-bold text-safe-ink',
  blocked: 'font-bold text-danger-ink',
  skipped: 'text-ink-muted',
}

/** "1.2 ms", "0.4 s" — short enough to sit beside every stage. */
function howLong(milliseconds: number): string {
  return milliseconds >= 1000 ? `${(milliseconds / 1000).toFixed(1)} s` : `${milliseconds.toFixed(1)} ms`
}

function summary(stages: StageResult[]): string {
  const stoppedAt = stages.find((stage) => stage.status === 'blocked')
  if (stoppedAt) {
    return `Stopped at ${LABELS[stoppedAt.name].toLowerCase()} after ${howLong(stoppedAt.duration_ms)}; later stages did not run.`
  }
  const ran = stages.filter((stage) => stage.status === 'passed').length
  const total = stages.reduce((sum, stage) => sum + stage.duration_ms, 0)
  return `${ran} of ${stages.length} stages ran in ${howLong(total)}; the others are not built yet.`
}

/** What the backend pipeline did with this message (the design's "guardrail" box). */
export function StageList({ stages }: { stages: StageResult[] }) {
  return (
    <div className="flex items-start gap-3 rounded-status border-2 border-border-soft bg-ground px-4 py-3">
      <ShieldCheck aria-hidden="true" strokeWidth={2.3} className="mt-0.5 size-[22px] shrink-0 text-ink-muted" />
      <div className="flex flex-col gap-1.5">
        <p className="m-0 text-[17px] leading-normal text-ink-muted">{summary(stages)}</p>
        <ul aria-label="Pipeline stages" className="m-0 flex list-none flex-wrap gap-x-5 gap-y-1 p-0 text-[15px] md:text-base">
          {stages.map((stage) => (
            <li key={stage.name} title={stage.detail}>
              <span className="text-ink-muted">{LABELS[stage.name]}:</span>{' '}
              <span className={STATUS_STYLE[stage.status]}>{stage.status}</span>
              {stage.status !== 'skipped' && (
                <span className="text-ink-muted"> · {howLong(stage.duration_ms)}</span>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
