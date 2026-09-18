import { cn } from '@/lib/utils'
import { CircleCheck, OctagonX, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

/** The green / amber / red boxes from the design ("Safe to start", "Check this", "Do not use"). */
const TONES = {
  safe: { box: 'border-safe-line bg-safe-fill', ink: 'text-safe-ink', Icon: CircleCheck },
  check: { box: 'border-check-line bg-check-fill', ink: 'text-check-ink', Icon: TriangleAlert },
  danger: { box: 'border-danger-line bg-danger-fill', ink: 'text-danger-ink', Icon: OctagonX },
} as const

type Props = { tone: keyof typeof TONES; word: string; children: ReactNode }

export function StatusBlock({ tone, word, children }: Props) {
  const { box, ink, Icon } = TONES[tone]
  return (
    <div
      className={cn(
        'flex items-start gap-[11px] rounded-status border-2 px-3.5 py-3 md:gap-3.5 md:px-[18px] md:py-4',
        box,
      )}
    >
      <Icon aria-hidden="true" strokeWidth={2.4} className={cn('mt-0.5 size-[26px] shrink-0', ink)} />
      <div className="flex flex-col gap-1">
        <span className={cn('text-[17px] font-bold md:text-[19px]', ink)}>{word}</span>
        <p className="m-0 text-base leading-normal md:text-lg">{children}</p>
      </div>
    </div>
  )
}
