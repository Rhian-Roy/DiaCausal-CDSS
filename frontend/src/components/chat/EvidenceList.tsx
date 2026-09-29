/**
 * Cited evidence from licence-cleared sources (RAG): the explanation's sentences, each with
 * the numbers of the passages it comes from, and the passages themselves with their source.
 */

import type { EvidencePart } from '@/lib/contract'

export function EvidenceList({ part }: { part: EvidencePart }) {
  if (part.status === 'insufficient_evidence') {
    return (
      <section aria-label="Evidence" className="flex flex-col gap-1">
        <p className="m-0 text-base font-bold">Evidence: insufficient</p>
        <p className="m-0 text-base text-ink-muted">
          The approved sources do not answer this question{part.note ? ` (${part.note})` : ''}. DiaCausal does not guess.
        </p>
      </section>
    )
  }
  const quoted = part.backend === 'template'
  return (
    <section aria-label="Evidence" className="flex flex-col gap-2">
      <p className="m-0 text-base font-bold">
        Evidence {quoted ? '(sentences quoted from the passages below)' : '(written by a model; every citation checked)'}
      </p>
      <ul className="m-0 flex list-disc flex-col gap-1 pl-5">
        {part.sentences.map((s, i) => (
          <li key={i} className="text-base leading-normal">
            {quoted ? `“${s.text}”` : s.text}{' '}
            <span className="font-bold">{s.cites.map((n) => `[${n}]`).join('')}</span>
          </li>
        ))}
      </ul>
      {part.note && <p className="m-0 text-sm text-ink-muted">{part.note}</p>}
      <details className="text-sm">
        <summary className="min-h-11 cursor-pointer content-center font-bold text-ink-muted">
          The {part.passages.length} passages and their sources
        </summary>
        <ol className="m-0 flex list-none flex-col gap-2 p-0">
          {part.passages.map((p) => (
            <li key={p.n} data-passage={p.n} className="rounded-status border border-border-soft p-3">
              <p className="m-0 font-bold">
                [{p.n}] {p.source_id}: {p.title}
              </p>
              <p className="m-0 text-ink-muted">
                {p.section}
                {p.page ? `, page ${p.page}` : ''}
              </p>
              <p className="m-0 mt-1 leading-normal">{p.text}</p>
            </li>
          ))}
        </ol>
      </details>
    </section>
  )
}
