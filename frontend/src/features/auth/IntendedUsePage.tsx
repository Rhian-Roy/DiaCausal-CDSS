/** After the first sign-in, and whenever the text changes (design/v1/07). Stored per user with date and version. */

import { INTENDED_USE } from '@/lib/contract'
import { Check, X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { authApi, type SessionInfo } from './api'
import { Alert, AuthShell, Card, Heading, PrimaryButton } from './ui'

const DOES = [
  'Suggests which second-line agent to consider for an adult with type 2 diabetes who is already on metformin.',
  'Compares the options with an estimate and an uncertainty interval, never a bare number.',
  'Runs contraindication, kidney-function and interaction checks before it ranks anything.',
  'Cites the source, version and section behind every clinical statement.',
  'Says “insufficient evidence” and stops when the patient falls outside what it can support.',
]
const DOES_NOT = [
  'It does not prescribe, place orders, or act on its own. You decide.',
  'It does not diagnose, and it does not replace your examination of the patient.',
  'It does not cover type 1 diabetes, pregnancy, under-18s, or starting insulin.',
  'It does not accept patient identifiers. Do not type names, Aadhaar, phone, PAN or email.',
  'It is not a marketed medical device and has not been approved for routine clinical use.',
]

type Props = { version: string; onAcknowledged: (info: SessionInfo) => void; onSessionEnded: () => void }

export function IntendedUsePage({ version, onAcknowledged, onSessionEnded }: Props) {
  const [ticked, setTicked] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!ticked) {
      setError('Tick “I understand” to continue.')
      return
    }
    const result = await authApi.acknowledge(version)
    if (result.ok) onAcknowledged(result.data)
    else if (result.status === 401) onSessionEnded()
    else setError(result.problem.message)
  }

  return (
    <AuthShell>
      <form onSubmit={submit} aria-label="How to use DiaCausal" className="flex flex-col gap-[22px]">
        <Heading step="Before you start" title="How to use DiaCausal" lede="Read this once, each time the tool is updated." />
        <Card>
          <h2 className="m-0 font-display text-[23px] font-semibold md:text-[26px]">What DiaCausal does</h2>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {DOES.map((line) => (
              <li key={line} className="flex gap-2">
                <Check aria-hidden="true" className="mt-1 size-5 shrink-0 text-safe-ink" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Card>
          <h2 className="m-0 font-display text-[23px] font-semibold md:text-[26px]">What DiaCausal does not do</h2>
          <ul className="m-0 flex list-none flex-col gap-2 p-0">
            {DOES_NOT.map((line) => (
              <li key={line} className="flex gap-2">
                <X aria-hidden="true" className="mt-1 size-5 shrink-0 text-danger-ink" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </Card>
        <Alert tone="info" word="Intended use">{INTENDED_USE}</Alert>
        {error && <Alert tone="check" word="Not yet">{error}</Alert>}
        <label className="flex min-h-11 items-center gap-3 text-lg font-bold">
          <input type="checkbox" className="size-6 accent-pine" checked={ticked} onChange={(e) => setTicked(e.target.checked)} />
          I understand
        </label>
        <div className="flex flex-wrap gap-3">
          <PrimaryButton type="submit">Continue</PrimaryButton>
        </div>
      </form>
    </AuthShell>
  )
}
