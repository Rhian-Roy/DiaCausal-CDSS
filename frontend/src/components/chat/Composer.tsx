import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { INTENDED_USE, MAX_TEXT_CHARS } from '@/lib/contract'
import { countCharacters } from '@/lib/guards'
import { ArrowUp, Mic } from 'lucide-react'
import { useRef, useState, type KeyboardEvent } from 'react'

const SHOW_COUNT_FROM = 7000

type Props = {
  onSend: (text: string) => boolean
  onType: () => void
  notice: string | null
  waiting: boolean
}

/** The message box. Enter sends; Shift+Enter starts a new line. */
export function Composer({ onSend, onType, notice, waiting }: Props) {
  const [text, setText] = useState('')
  const box = useRef<HTMLTextAreaElement>(null)
  const count = countCharacters(text)
  const wide = useMediaQuery('(width >= 48rem)') // Tailwind's `md`

  function submit() {
    if (onSend(text)) setText('')
    box.current?.focus()
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // isComposing: the user is still building a character with an input method
    // (e.g. a Hindi or Marathi keyboard); Enter there picks the character, not "send".
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <form
      className="flex shrink-0 flex-col gap-3 border-t-2 border-border-soft bg-surface px-4 pt-[11px] pb-3.5 md:px-8 md:pt-3.5 md:pb-[18px]"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <div className="flex items-end gap-3 rounded-card border-2 border-border-strong px-3 py-2.5 has-[textarea:focus-visible]:outline-3 has-[textarea:focus-visible]:outline-offset-2 has-[textarea:focus-visible]:outline-pine">
        <label className="sr-only" htmlFor="message">
          Message DiaCausal
        </label>
        <Textarea
          ref={box}
          id="message"
          name="message"
          rows={2}
          autoFocus
          value={text}
          onChange={(event) => {
            setText(event.target.value)
            onType()
          }}
          onKeyDown={onKeyDown}
          placeholder={wide ? 'Ask about a class, a dose, or a contraindication' : 'Ask a question'}
          aria-describedby="composer-help"
          className="max-h-56 min-h-[calc(2lh+1rem)] flex-1 resize-none self-center rounded-none border-0 bg-transparent px-1 py-2 text-[17px] leading-normal text-ink shadow-none placeholder:text-ink-placeholder focus-visible:ring-0 focus-visible:outline-none md:text-[19px]"
        />
        {/* VOICE: speech-to-text goes here — see frontend/src/features/voice/README.md */}
        <span title="Voice input is not built yet">
          <Button type="button" variant="outline" size="touch" disabled aria-label="Voice input (not built yet)">
            <Mic strokeWidth={2.3} />
          </Button>
        </span>
        <Button type="submit" size="touch" disabled={waiting} aria-label="Send message" className="border-pine">
          <ArrowUp strokeWidth={2.3} />
        </Button>
      </div>

      {(notice || count >= SHOW_COUNT_FROM) && (
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <p role="alert" className="m-0 text-base font-bold text-check-ink">
            {notice}
          </p>
          {count >= SHOW_COUNT_FROM && (
            <p className={count > MAX_TEXT_CHARS ? 'm-0 text-sm font-bold text-check-ink' : 'm-0 text-sm text-ink-muted'}>
              {count.toLocaleString('en-US')} / {MAX_TEXT_CHARS.toLocaleString('en-US')} characters
            </p>
          )}
        </div>
      )}

      <p id="composer-help" className="m-0 text-sm leading-normal text-ink-muted md:text-base">
        <span className="sr-only">Press Enter to send, Shift and Enter for a new line. </span>
        {INTENDED_USE}
      </p>
    </form>
  )
}
