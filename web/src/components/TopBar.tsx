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
            className="border-b border-transparent px-2 py-1.5 font-mono text-xs font-medium text-muted aria-[current]:border-ink aria-[current]:text-ink"
          >
            {t.label}
          </button>
        ))}
      </nav>
      )}
      <div className="ml-auto flex items-center gap-[18px] font-mono text-muted">
        {chart && (
        <button type="button" aria-pressed={trades} onClick={() => onTrades(!trades)} className="flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className={`relative inline-block h-3 w-[22px] rounded-full border border-ink after:absolute after:top-px after:left-px after:size-2 after:rounded-full after:bg-ink after:transition-transform ${trades ? 'after:translate-x-2.5' : ''}`}
          />
          Trades
        </button>
        )}
        <span>{isStatic() ? (snapshot ? `Snapshot of ${snapshot}` : 'Snapshot') : 'Delayed 10m'}</span>
      </div>
    </header>
  )
}
