import { useMemo, useState } from 'react'
import type { JournalStats, Summary } from '../../api/types'
import { fmtPct, fmtR } from '../../lib/trade'

const SOURCES: [string, string][] = [
  ['signal', 'Followed signal'],
  ['manual', 'Manual'],
  ['imported', 'Case study'],
]

function Cell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="border-b py-3.5 pr-4">
      <div className="mb-1.5 font-mono text-[10px] font-medium tracking-widest text-muted uppercase">{label}</div>
      {children}
    </div>
  )
}

const line = (s?: Summary) =>
  s && s.n ? `${s.n} · ${fmtPct(s.win_rate)} · ${fmtR(s.mean_r)}` : 'None yet'

const MONTHS = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' })

/** A month of daily R: one cell per day, coloured by sign. */
function Calendar({ days, day, onDay }: { days: JournalStats['calendar']; day: string | null; onDay: (d: string | null) => void }) {
  const byDate = useMemo(() => new Map(days.map((d) => [d.date, d])), [days])
  const latest = days.at(-1)?.date ?? new Date().toISOString().slice(0, 10)
  const [month, setMonth] = useState(latest.slice(0, 7))
  const [y, m] = month.split('-').map(Number)
  const first = new Date(Date.UTC(y, m - 1, 1))
  const lead = (first.getUTCDay() + 6) % 7 // Monday first
  const count = new Date(Date.UTC(y, m, 0)).getUTCDate()
  const shift = (n: number) => setMonth(new Date(Date.UTC(y, m - 1 + n, 1)).toISOString().slice(0, 7))

  return (
    <div className="pt-5">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[10px] font-medium tracking-widest text-muted uppercase">{MONTHS.format(first)}</span>
        <span className="flex gap-3 font-mono text-muted">
          <button type="button" aria-label="Previous month" onClick={() => shift(-1)}>←</button>
          <button type="button" aria-label="Next month" onClick={() => shift(1)}>→</button>
        </span>
      </div>
      <div className="grid grid-cols-7 gap-1">
        {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, i) => (
          <span key={i} className="text-center font-mono text-[10px] text-muted">{d}</span>
        ))}
        {Array.from({ length: lead }, (_, i) => <span key={`x${i}`} />)}
        {Array.from({ length: count }, (_, i) => {
          const date = `${month}-${String(i + 1).padStart(2, '0')}`
          const d = byDate.get(date)
          const tone = !d ? 'border text-muted' : d.r >= 0 ? 'bg-brand text-brand-fg' : 'bg-down text-brand-fg'
          return (
            <button
              key={date}
              type="button"
              disabled={!d}
              aria-label={d ? `${date}, ${d.n} trade${d.n === 1 ? "" : "s"}, ${fmtR(d.r)}` : date}
              aria-pressed={day === date}
              onClick={() => onDay(day === date ? null : date)}
              className={`grid h-10 place-items-center rounded-sm font-mono text-[11px] aria-pressed:outline aria-pressed:outline-ink ${tone}`}
            >
              {i + 1}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function Stats({ stats, day, onDay }: { stats: JournalStats; day: string | null; onDay: (d: string | null) => void }) {
  const s = stats.stats
  const worst = s.worst_days[0]
  return (
    <div>
      <div className="grid grid-cols-2 border-t xl:grid-cols-5">
        {SOURCES.map(([k, label]) => (
          <Cell key={k} label={label}>
            <span className="font-mono">{line(s.by_source[k])}</span>
          </Cell>
        ))}
        <Cell label="Skipped signals">
          <span className="font-mono">{s.skipped.length}</span>
        </Cell>
        <Cell label="Worst day">
          {worst ? (
            <span className="font-mono">
              <span>{worst.date}</span> <span className="text-down">{fmtR(worst.r)}</span>
            </span>
          ) : (
            <span className="text-muted">None yet</span>
          )}
        </Cell>
      </div>
      <p className="pt-2 font-mono text-[11px] text-muted">n · win rate · mean R, closed trades only</p>
      <Calendar days={stats.calendar} day={day} onDay={onDay} />
    </div>
  )
}
