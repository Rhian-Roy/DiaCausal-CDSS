import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { HighlightNumbers } from '@/features/voice/HighlightNumbers'
import { MAX_SECONDS, useVoiceInput } from '@/features/voice/useVoiceInput'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { INTENDED_USE, MAX_TEXT_CHARS } from '@/lib/contract'
import { countCharacters } from '@/lib/guards'
import { cn } from '@/lib/utils'
import { ArrowUp, LoaderCircle, Mic, Square } from 'lucide-react'
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
  const wide = useMediaQuery('(width >= 761px)') // same switch point as `md:` (see index.css)
  // The last dictated text, shown with its numbers marked until the message is sent.
  const [dictated, setDictated] = useState<string | null>(null)
  const voice = useVoiceInput((transcript) => {
    // Into the box, after anything already typed. Never sent by itself: the doctor
    // checks it, then presses Enter, and the usual guards run.
    setText((current) => (current.trim() ? `${current.trimEnd()} ${transcript}` : transcript))
    setDictated(transcript)
    onType()
    box.current?.focus()
  })
  const recording = voice.state.kind === 'recording'
  const transcribing = voice.state.kind === 'transcribing'

  function submit() {
    if (onSend(text)) {
      setText('')
      setDictated(null)
    }
    box.current?.focus()
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // The user may still be building a word with an input method (e.g. a Hindi or
    // Marathi keyboard); that Enter picks the word, it does not mean "send".
    // Chrome/Firefox flag it with isComposing; Safari sends keyCode 229 instead.
    const composing = event.nativeEvent.isComposing || event.keyCode === 229
    if (event.key === 'Enter' && !event.shiftKey && !composing) {
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
        {/* Voice: see src/features/voice/ (speech-to-text runs on our backend). */}
        <Button
          type="button"
          variant="outline"
          size="touch"
          onClick={voice.toggle}
          disabled={transcribing}
          aria-pressed={recording}
          aria-label={recording ? 'Stop recording' : transcribing ? 'Turning speech into text' : 'Dictate message'}
          className={cn(recording && 'border-danger-line bg-danger-fill text-danger-ink hover:bg-danger-fill')}
        >
          {recording ? (
            <Square strokeWidth={2.3} fill="currentColor" />
          ) : transcribing ? (
            <LoaderCircle strokeWidth={2.3} className="animate-spin" />
          ) : (
            <Mic strokeWidth={2.3} />
          )}
        </Button>
        <Button type="submit" size="touch" disabled={waiting} aria-label="Send message" className="border-pine">
          <ArrowUp strokeWidth={2.3} />
        </Button>
      </div>

      {recording && (
        <p role="status" className="m-0 flex items-center gap-2 text-base font-bold text-danger-ink">
          <span aria-hidden="true" className="size-3 animate-pulse rounded-full bg-danger-line" />
          Recording {formatSeconds(voice.state.kind === 'recording' ? voice.state.seconds : 0)} / {formatSeconds(MAX_SECONDS)}
          <span className="font-normal text-ink-muted">— press the square to stop</span>
        </p>
      )}
      {transcribing && (
        <p role="status" className="m-0 text-base text-ink-muted">Turning speech into text on the DiaCausal server…</p>
      )}
      {voice.state.kind === 'error' && (
        <p role="alert" className="m-0 text-base font-bold text-check-ink">{voice.state.message}</p>
      )}
      {dictated && (
        <div className="flex flex-col gap-1 rounded-status border-2 border-check-line bg-surface px-3.5 py-2.5">
          <span className="text-sm font-bold tracking-[0.06em] text-check-ink uppercase">
            From voice — check the numbers before you press Enter
          </span>
          <p className="m-0 text-base leading-relaxed" data-testid="dictated">
            <HighlightNumbers text={dictated} />
          </p>
        </div>
      )}

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

function formatSeconds(seconds: number): string {
  return `0:${String(seconds).padStart(2, '0')}`
}
