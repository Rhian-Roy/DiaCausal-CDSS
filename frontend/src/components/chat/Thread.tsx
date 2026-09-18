import type { Turn } from '@/hooks/useChat'
import { Info } from 'lucide-react'
import { Fragment, useEffect, useRef } from 'react'
import { AnswerCard } from './AnswerCard'

function EmptyState() {
  return (
    <div className="flex max-w-[900px] items-start gap-3 rounded-status border-2 border-border-soft bg-surface px-4 py-3">
      <Info aria-hidden="true" strokeWidth={2.3} className="mt-0.5 size-6 shrink-0 text-ink-muted" />
      <p className="m-0 leading-normal text-ink-muted">
        Ask a question below and press Enter. This first version passes it through the pipeline and returns a
        fixed test reply — no clinical analysis runs yet.
      </p>
    </div>
  )
}

/** The scrollable conversation: "You asked" followed by DiaCausal's answer, oldest first. */
export function Thread({ turns }: { turns: Turn[] }) {
  const scroller = useRef<HTMLElement>(null)

  useEffect(() => {
    const element = scroller.current
    if (element) element.scrollTop = element.scrollHeight
  }, [turns])

  return (
    <main ref={scroller} className="min-h-0 flex-1 overflow-y-auto">
      <h1 className="sr-only">DiaCausal chat</h1>
      <div role="log" aria-label="Conversation" className="flex flex-col gap-4 p-4 md:gap-[22px] md:px-8 md:py-6">
        {turns.length === 0 && <EmptyState />}
        {turns.map((turn) => (
          <Fragment key={turn.traceId}>
            <section className="flex max-w-[900px] flex-col gap-2">
              <span className="text-sm font-bold tracking-[0.08em] text-ink-muted uppercase">You asked</span>
              <p className="m-0 whitespace-pre-wrap wrap-break-word">{turn.question}</p>
            </section>
            <AnswerCard answer={turn.answer} traceId={turn.traceId} />
          </Fragment>
        ))}
      </div>
    </main>
  )
}
