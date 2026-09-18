import type { Answer } from '@/lib/chatFlow'
import type { ReactNode } from 'react'
import { StageList } from './StageList'
import { StatusBlock } from './StatusBlock'

function Card({ label, busy = false, children }: { label: string; busy?: boolean; children: ReactNode }) {
  return (
    <section
      aria-busy={busy}
      className="flex max-w-[900px] flex-col gap-3 rounded-card border-2 border-border-soft bg-surface p-4 md:gap-4 md:p-6"
    >
      <span className="text-sm font-bold tracking-[0.08em] text-ink-muted uppercase">{label}</span>
      {children}
    </section>
  )
}

function TraceNote({ traceId }: { traceId: string }) {
  return (
    <p className="m-0 text-sm leading-normal text-ink-muted md:text-base">
      Trace ID <code className="font-mono">{traceId}</code> — the same ID is in the browser console and the
      backend log.
    </p>
  )
}

export function AnswerCard({ answer, traceId }: { answer: Answer; traceId: string }) {
  switch (answer.kind) {
    case 'pending':
      return (
        <Card label="DiaCausal is answering" busy>
          <p className="m-0 text-ink-muted">Working on it…</p>
        </Card>
      )
    case 'error':
      return (
        <Card label="DiaCausal could not answer">
          <StatusBlock tone="danger" word="Couldn't get a reply">
            {answer.message}
          </StatusBlock>
          <TraceNote traceId={traceId} />
        </Card>
      )
    case 'blocked':
      return (
        <Card label="DiaCausal did not answer">
          <StatusBlock tone="check" word="Not answered">
            {answer.reason}
          </StatusBlock>
          <StageList stages={answer.stages} />
          <TraceNote traceId={traceId} />
        </Card>
      )
    case 'answered':
      return (
        <Card label="DiaCausal answered">
          {answer.text.split(/\n{2,}/).map((paragraph, index) => (
            <p key={index} className="m-0 whitespace-pre-wrap wrap-break-word">
              {paragraph}
            </p>
          ))}
          <StageList stages={answer.stages} />
          <TraceNote traceId={traceId} />
        </Card>
      )
  }
}
