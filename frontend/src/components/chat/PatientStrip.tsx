/**
 * The patient summary line from the design. It is fixed example data for now and
 * is not sent to the backend; later it will come from the selected patient record.
 */
export function PatientStrip() {
  return (
    <div className="flex shrink-0 flex-wrap items-center justify-between gap-4 border-b-2 border-border-soft bg-surface px-4 py-3 md:px-8">
      <p className="m-0 text-base leading-[1.4] font-bold md:text-lg">
        <span className="md:hidden">58 y · T2D 6 y · on metformin · HbA1c 8.4% · eGFR 62</span>
        <span className="hidden md:inline">
          Adult, 58 y · Type 2 diabetes 6 y · on metformin 1 g twice daily · HbA1c 8.4% · eGFR 62 · BMI 31.2
        </span>
      </p>
      <span className="rounded-md border-2 border-border-soft bg-ground px-2.5 py-1 text-sm leading-normal font-bold whitespace-nowrap text-ink-muted">
        Example data
      </span>
    </div>
  )
}
