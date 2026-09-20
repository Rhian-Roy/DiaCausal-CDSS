import type { ReasonCode, ScopeTopic } from '@/lib/contract'
import { TOPIC_NAMES } from '@/lib/guards'
import { cn } from '@/lib/utils'
import { EyeOff, Info, MessageCircleX, OctagonX } from 'lucide-react'

type Props = { code: ReasonCode; topic?: ScopeTopic | null }

function Notice({ tone, Icon, word, children }: {
  tone: 'check' | 'info' | 'plain'
  Icon: typeof Info
  word: string
  children: React.ReactNode
}) {
  const styles = {
    check: { box: 'border-check-line bg-check-fill', ink: 'text-check-ink' },
    info: { box: 'border-pine bg-pine-fill', ink: 'text-pine' },
    plain: { box: 'border-border-strong bg-surface', ink: 'text-ink' },
  }[tone]
  return (
    <div role="status" className={cn('flex max-w-[900px] items-start gap-3.5 rounded-card border-2 p-[22px]', styles.box)}>
      <Icon aria-hidden="true" strokeWidth={2.4} className={cn('size-7 shrink-0', styles.ink)} />
      <div className="flex flex-col gap-2 text-lg leading-normal">
        <span className={cn('text-xl font-bold', styles.ink)}>{word}</span>
        {children}
      </div>
    </div>
  )
}

/** The four guard notices from design/v1/09-12, shown in place of an answer. */
export function GuardNotice({ code, topic }: Props) {
  switch (code) {
    case 'identifier':
      return (
        <Notice tone="check" Icon={EyeOff} word="Identifier removed — not sent">
          <p className="m-0">Please remove patient identifiers (Aadhaar, phone, PAN, email) and ask again.</p>
          <p className="m-0">Describe the patient by age, sex, lab values and current therapy instead.</p>
        </Notice>
      )
    case 'out_of_scope':
      return (
        <Notice tone="info" Icon={Info} word="Out of scope">
          <p className="m-0">
            DiaCausal covers adults with type 2 diabetes already on metformin.
            {topic && ` This question is about ${TOPIC_NAMES[topic]}.`}
          </p>
          <p className="m-0">Use your usual guideline or refer as you normally would.</p>
        </Notice>
      )
    case 'language':
      return (
        <Notice tone="plain" Icon={MessageCircleX} word="Cannot answer as written">
          <p className="m-0">Please rephrase your question.</p>
        </Notice>
      )
    case 'emergency':
      // The most prominent notice, and deliberately nothing else: no treatment content.
      return (
        <div role="alert" className="max-w-[900px] overflow-hidden rounded-card border-3 border-danger-line">
          <div className="flex items-center gap-3 bg-danger-line px-[22px] py-3 text-xl font-bold tracking-[0.06em] text-on-danger uppercase">
            <OctagonX aria-hidden="true" strokeWidth={2.6} className="size-[26px] shrink-0" />
            Emergency
          </div>
          <div className="flex flex-col gap-3 bg-danger-fill p-[22px]">
            <p className="m-0 text-2xl leading-[1.35] font-bold text-ink">
              This may be an emergency. Follow your emergency protocol.
            </p>
            <p className="m-0 text-lg leading-normal">
              DiaCausal has not answered this question and will not suggest treatment for it.
            </p>
          </div>
        </div>
      )
  }
}
