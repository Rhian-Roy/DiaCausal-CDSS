import { PulseIcon } from './PulseIcon'

export function TopBar() {
  return (
    <header className="flex shrink-0 flex-wrap items-center justify-between gap-4 bg-pine px-4 py-3 md:px-8">
      <div className="flex flex-wrap items-center gap-3">
        <PulseIcon className="size-[26px] text-white" />
        <span className="font-display text-[21px] leading-[1.55] font-semibold text-white md:text-2xl">
          DiaCausal
        </span>
        <span className="rounded-md border-2 border-pine-hairline px-2.5 py-1 text-xs leading-[1.55] font-bold tracking-[0.07em] whitespace-nowrap text-white uppercase">
          <span className="hidden md:inline">Research </span>prototype
        </span>
      </div>
      {/* LOGIN: replace with the signed-in clinician's name and a "Sign out" link (design/chat.html). */}
      <span className="hidden text-base text-on-pine-muted md:inline">Not signed in · login comes later</span>
    </header>
  )
}
