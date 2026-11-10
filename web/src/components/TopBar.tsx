import type { ReactNode } from 'react'
import { useSnapshotDate } from '../api/static'
import { isStatic } from '../lib/mode'
import { TIMEFRAMES, type Tf } from '../lib/chart'

type Props = {
  tf: Tf
  onTf: (tf: Tf) => void
  trades: boolean
  onTrades: (on: boolean) => void
  left?: ReactNode
  chart?: boolean
}

export function TopBar({ tf, onTf, trades, onTrades, left, chart = true }: Props) {
  const snapshot = useSnapshotDate()
  return (
    <header className="flex flex-wrap items-center gap-6 border-b px-5 py-3">
      {left}
      {chart && (
      <nav aria-label="Timeframe" data-tour="timeframes" className="flex gap-0.5">
        {TIMEFRAMES.map((t) => (
          <button
            key={t.tf}
            type="button"
            aria-current={t.tf === tf ? 'true' : undefined}
            onClick={() => onTf(t.tf)}
            className="border-b border-transparent px-2 py-1.5 font-mono text-xs font-medium text-muted hover:text-ink aria-[current]:border-ink aria-[current]:text-ink motion-safe:transition-colors motion-safe:duration-300"
          >
            {t.label}
          </button>
        ))}
      </nav>
      )}
      <div className="ml-auto flex items-center gap-[18px] font-mono text-muted">
        {chart && (
        <button
          type="button"
          aria-pressed={trades}
          onClick={() => onTrades(!trades)}
          className="group/trades flex items-center gap-2 hover:text-ink aria-pressed:text-ink motion-safe:transition-colors motion-safe:duration-300"
        >
          {/* off: a muted outline; on: the track fills with brand and the knob slides across */}
          <span
            aria-hidden="true"
            className={`relative inline-block h-[14px] w-[24px] rounded-full border after:absolute after:top-[2px] after:left-[2px] after:size-[8px] after:rounded-full motion-safe:transition-colors motion-safe:duration-300 motion-safe:after:transition-[translate,background-color] motion-safe:after:duration-500 after:ease-[cubic-bezier(0.7,0,0.3,1)] ${
              trades
                ? 'border-brand bg-brand/20 after:translate-x-[10px] after:bg-brand'
                : 'border-muted/60 after:bg-muted group-hover/trades:border-ink group-hover/trades:after:bg-ink'
            }`}
          />
          Trades
        </button>
        )}
        <span>{isStatic() ? (snapshot ? `Build ${snapshot}` : 'Build') : 'Delayed 10m'}</span>
      </div>
    </header>
  )
}
