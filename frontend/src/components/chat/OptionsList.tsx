/**
 * What the clinical guardrails decided about each of the three add-on options, before
 * anything is ranked. The full comparison card is design 17 (docs/prompts/08-answer-card.md);
 * this shows the safety part of it honestly in the meantime.
 */

import type { OptionsPart, OptionStatus } from '@/lib/contract'
import { cn } from '@/lib/utils'
import { CircleCheck, OctagonX, TriangleAlert } from 'lucide-react'

const STATUS = {
  safe_to_consider: { word: 'Safe to consider', box: 'border-safe-line bg-safe-fill', ink: 'text-safe-ink', Icon: CircleCheck },
  check_first: { word: 'Check first', box: 'border-check-line bg-check-fill', ink: 'text-check-ink', Icon: TriangleAlert },
  do_not_use: { word: 'Do not use', box: 'border-danger-line bg-danger-fill', ink: 'text-danger-ink', Icon: OctagonX },
} as const satisfies Record<OptionStatus, unknown>

export function OptionsList({ part }: { part: OptionsPart }) {
  return (
    <section aria-label="The three options" className="flex flex-col gap-3">
      {part.draft_warning && (
        <p className="m-0 text-base font-bold text-check-ink">
          Clinical rules {part.rules_version} — {part.draft_warning}.
        </p>
      )}
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {part.options.map((option) => {
          const { word, box, ink, Icon } = STATUS[option.status]
          return (
            <li key={option.option} data-option={option.option} className={cn('flex items-start gap-3 rounded-status border-2 p-3.5', box)}>
              <Icon aria-hidden="true" strokeWidth={2.4} className={cn('mt-0.5 size-6 shrink-0', ink)} />
              <div className="flex flex-col gap-1">
                <span className="text-[17px] font-bold">
                  {option.name}: <span className={ink}>{word}</span>
                </span>
                {option.reasons.map((reason) => (
                  <p key={reason} className="m-0 text-base leading-normal">{reason}</p>
                ))}
                {option.notes.map((note) => (
                  <p key={note} className="m-0 text-base leading-normal text-ink-muted">{note}</p>
                ))}
                {option.sources.length > 0 && (
                  <details className="text-sm text-ink-muted">
                    <summary className="min-h-11 cursor-pointer content-center font-bold">
                      Where this comes from ({option.sources.length})
                    </summary>
                    <ul className="m-0 flex list-disc flex-col gap-1 py-1 pl-5">
                      {option.sources.map((source) => (
                        <li key={source}>{source}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
