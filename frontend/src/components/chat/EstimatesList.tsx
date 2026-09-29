/**
 * The causal engine's estimates for each option (designs 17 and 19): every number comes with
 * its 95% range; an excluded option or one with too few similar patients shows no number.
 * Never green for "recommended": the clinician decides.
 */

import type { EstimatesPart, EstimateStatus, Range } from '@/lib/contract'
import { cn } from '@/lib/utils'

const STATUS = {
  estimate: { word: 'Estimate', box: 'border-border-soft bg-surface' },
  insufficient_evidence: { word: 'Insufficient evidence', box: 'border-check-line bg-check-fill' },
  excluded: { word: 'Excluded, no estimate', box: 'border-danger-line bg-danger-fill' },
} as const satisfies Record<EstimateStatus, unknown>

const signed = (x: number, digits = 2) => `${x >= 0 ? '+' : '−'}${Math.abs(x).toFixed(digits)}`

function RangeText({ range, digits = 2, unit = '' }: { range: Range; digits?: number; unit?: string }) {
  return (
    <>
      <span className="text-[22px] font-bold">
        {signed(range.value, digits)}
        {unit}
      </span>{' '}
      <span className="text-sm text-ink-muted">
        (95% range {signed(range.ci_low, digits)} to {signed(range.ci_high, digits)}
        {unit})
      </span>
    </>
  )
}

export function EstimatesList({ part }: { part: EstimatesPart }) {
  return (
    <section aria-label="Estimates for this patient" className="flex flex-col gap-3">
      <p className="m-0 text-base font-bold">{part.outcome}</p>
      <ul className="m-0 grid list-none gap-3 p-0 md:grid-cols-3">
        {part.estimates.map((e) => (
          <li key={e.option} data-option={e.option} data-status={e.status} className={cn('flex flex-col gap-1 rounded-status border-2 p-3.5', STATUS[e.status].box)}>
            <span className="text-[17px] font-bold">{e.name}</span>
            <span className="text-sm font-bold tracking-[0.04em] text-ink-muted uppercase">{STATUS[e.status].word}</span>
            {e.status === 'estimate' && e.hba1c_change ? (
              <>
                <p className="m-0">
                  <RangeText range={e.hba1c_change} />
                </p>
                {e.weight_change_kg && (
                  <p className="m-0 text-sm">
                    Weight <RangeText range={e.weight_change_kg} digits={1} unit=" kg" />
                  </p>
                )}
                {e.hypo_risk_pct && (
                  <p className="m-0 text-sm">
                    Low-sugar risk {e.hypo_risk_pct.value.toFixed(1)}% (95% range {e.hypo_risk_pct.ci_low.toFixed(1)}–
                    {e.hypo_risk_pct.ci_high.toFixed(1)}%)
                  </p>
                )}
                {e.propensity !== null && (
                  <p className="m-0 text-sm text-ink-muted">Similar patients who got it: propensity {e.propensity.toFixed(2)}</p>
                )}
              </>
            ) : (
              <p className="m-0 text-base leading-normal">{e.reason}</p>
            )}
          </li>
        ))}
      </ul>
      {part.comparisons.map((c) => {
        const overlap = c.difference.ci_low <= 0 && c.difference.ci_high >= 0
        return (
          <p key={`${c.first}-${c.second}`} className="m-0 text-base">
            {c.first} minus {c.second}: <RangeText range={c.difference} />
            {overlap && <span className="text-ink-muted"> — the range includes 0, so neither is clearly better.</span>}
          </p>
        )
      })}
      <p className="m-0 text-sm text-ink-muted">
        {part.data_note} {part.decision} Method: {part.method}.
      </p>
    </section>
  )
}
