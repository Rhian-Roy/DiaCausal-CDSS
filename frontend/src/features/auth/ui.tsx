/** Pieces shared by the sign-in screens (design/v1/01-08), built on the tokens in src/index.css. */

import { PulseIcon } from '@/components/chat/PulseIcon'
import { INTENDED_USE } from '@/lib/contract'
import { cn } from '@/lib/utils'
import { CircleCheck, Info, OctagonX, TriangleAlert } from 'lucide-react'
import type { ComponentProps, ReactNode } from 'react'

export function AuthShell({ wide = false, children }: { wide?: boolean; children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-ground">
      <header className="flex flex-wrap items-center gap-3 bg-pine px-4 py-3 md:px-8">
        <PulseIcon className="size-[26px] text-white" />
        <span className="font-display text-[21px] leading-[1.55] font-semibold text-white md:text-2xl">DiaCausal</span>
        <span className="rounded-md border-2 border-pine-hairline px-2.5 py-1 text-xs leading-[1.55] font-bold tracking-[0.07em] whitespace-nowrap text-white uppercase">
          <span className="hidden md:inline">Research </span>prototype
        </span>
      </header>
      <main className={cn('mx-auto p-4 md:p-8', wide ? 'max-w-[1280px]' : 'max-w-[720px]')}>{children}</main>
    </div>
  )
}

export function Heading({ step, title, lede }: { step: string; title: string; lede?: ReactNode }) {
  return (
    <div>
      <p className="m-0 text-[15px] font-bold tracking-[0.08em] text-ink-muted uppercase">{step}</p>
      <h1 className="m-0 font-display text-[28px] leading-[1.2] font-semibold md:text-[34px]">{title}</h1>
      {lede && <p className="m-0 text-ink-muted">{lede}</p>}
    </div>
  )
}

export function IntendedUseNotice() {
  return (
    <div className="flex items-start gap-3 rounded-card border-2 border-border-soft bg-surface p-4">
      <Info aria-hidden="true" strokeWidth={2.3} className="mt-0.5 size-6 shrink-0 text-ink-muted" />
      <p className="m-0 text-[17px]">{INTENDED_USE}</p>
    </div>
  )
}

const ALERTS = {
  danger: { box: 'border-danger-line bg-danger-fill', ink: 'text-danger-ink', Icon: OctagonX },
  check: { box: 'border-check-line bg-check-fill', ink: 'text-check-ink', Icon: TriangleAlert },
  safe: { box: 'border-safe-line bg-safe-fill', ink: 'text-safe-ink', Icon: CircleCheck },
  info: { box: 'border-pine bg-pine-fill', ink: 'text-pine', Icon: Info },
} as const

export function Alert({ tone, word, children }: { tone: keyof typeof ALERTS; word: string; children?: ReactNode }) {
  const { box, ink, Icon } = ALERTS[tone]
  return (
    <div role="alert" className={cn('flex items-start gap-3.5 rounded-status border-2 p-4', box)}>
      <Icon aria-hidden="true" strokeWidth={2.4} className={cn('mt-0.5 size-[26px] shrink-0', ink)} />
      <div className="flex flex-col gap-1">
        <span className={cn('text-[19px] font-bold', ink)}>{word}</span>
        {children && <div className="text-[17px] leading-normal text-ink">{children}</div>}
      </div>
    </div>
  )
}

export function Field({ id, label, hint, invalid, hideLabel, className, ...input }: ComponentProps<'input'> & {
  id: string
  label: string
  hint?: string
  invalid?: boolean
  hideLabel?: boolean // still read out by screen readers
}) {
  return (
    <div className="flex flex-col gap-2">
      <label className={hideLabel ? 'sr-only' : 'text-lg font-bold'} htmlFor={id}>{label}</label>
      {hint && <span id={`${id}-hint`} className="text-base text-ink-muted">{hint}</span>}
      <input
        id={id}
        aria-invalid={invalid || undefined}
        aria-describedby={hint ? `${id}-hint` : undefined}
        className={cn(
          'h-14 w-full rounded-control border-2 border-border-strong bg-surface px-4 text-[19px] text-ink',
          'placeholder:text-ink-placeholder focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-pine',
          'aria-invalid:border-3 aria-invalid:border-danger-line',
          className,
        )}
        {...input}
      />
    </div>
  )
}

/** 6-digit code box: large, spaced digits (designs 04-06). */
export function CodeField(props: Omit<ComponentProps<typeof Field>, 'inputMode' | 'maxLength'>) {
  return (
    <Field
      inputMode="numeric"
      maxLength={6}
      pattern="[0-9]{6}"
      autoComplete="one-time-code"
      placeholder="000000"
      className="w-[260px] max-w-full text-[26px] font-bold tracking-[0.3em]"
      {...props}
    />
  )
}

export function PrimaryButton({ className, ...props }: ComponentProps<'button'>) {
  return (
    <button
      className={cn(
        'h-[58px] cursor-pointer rounded-control border-2 border-pine bg-pine px-6 text-xl font-bold text-white hover:border-pine-dark hover:bg-pine-dark',
        'focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-pine',
        'disabled:cursor-not-allowed disabled:border-border-strong disabled:bg-track disabled:text-ink-muted',
        className,
      )}
      {...props}
    />
  )
}

export function GhostButton({ className, ...props }: ComponentProps<'button'>) {
  return (
    <button
      type="button"
      className={cn(
        'inline-flex min-h-[52px] cursor-pointer items-center justify-center gap-2 rounded-control border-2 border-border-strong bg-surface px-4 text-[17px] font-bold text-ink hover:border-ink-muted',
        'focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-pine disabled:cursor-not-allowed disabled:opacity-60',
        className,
      )}
      {...props}
    />
  )
}

export function LinkButton({ className, ...props }: ComponentProps<'button'>) {
  return (
    <button
      type="button"
      className={cn(
        'inline-flex min-h-11 cursor-pointer items-center self-start bg-transparent p-0 text-[17px] font-bold text-pine underline hover:text-pine-dark',
        'focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-pine',
        className,
      )}
      {...props}
    />
  )
}

export function Card({ className, ...props }: ComponentProps<'div'>) {
  return (
    <div
      className={cn('flex flex-col gap-3 rounded-card border-2 border-border-soft bg-surface p-[22px]', className)}
      {...props}
    />
  )
}
