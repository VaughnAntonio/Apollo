import type { Entry } from '../../api/types'
import { nyDate, toSec } from '../../lib/time'
import { fmtR } from '../../lib/trade'

export function TradeList({ entries, selected, onSelect }: { entries: Entry[]; selected: number | null; onSelect: (id: number) => void }) {
  if (!entries.length) return <p className="px-5 py-4 text-muted">No trades yet</p>
  return (
    <ul aria-label="Trades">
      {entries.map((e) => (
        <li key={e.id}>
          <button
            type="button"
            aria-current={selected === e.id ? 'true' : undefined}
            onClick={() => onSelect(e.id)}
            className="grid w-full grid-cols-[1fr_auto] gap-x-3 gap-y-0.5 border-b px-5 py-2.5 text-left hover:bg-soft aria-[current]:bg-soft"
          >
            <span className="font-mono">{`${nyDate(toSec(e.opened_at))} · ${e.symbol}`}</span>
            <span className={`font-mono ${e.r === null ? 'text-muted' : e.r >= 0 ? 'text-brand' : 'text-down'}`}>
              {e.r === null ? 'Open' : fmtR(e.r)}
            </span>
            <small className="truncate text-muted">{[e.strategy, e.account].filter(Boolean).join(' · ') || 'No strategy'}</small>
          </button>
        </li>
      ))}
    </ul>
  )
}
