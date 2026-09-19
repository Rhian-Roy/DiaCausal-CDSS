import { PulseIcon } from './PulseIcon'

type Props = { userName?: string; onSignOut?: () => void }

export function TopBar({ userName, onSignOut }: Props) {
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
      {userName && onSignOut ? (
        <div className="flex flex-wrap items-center gap-[22px]">
          <span className="hidden text-base text-on-pine-muted md:inline">{userName}</span>
          <button
            type="button"
            onClick={onSignOut}
            className="flex min-h-11 cursor-pointer items-center bg-transparent p-0 text-base font-bold text-white underline focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            Sign out
          </button>
        </div>
      ) : (
        <span className="hidden text-base text-on-pine-muted md:inline">Not signed in</span>
      )}
    </header>
  )
}
