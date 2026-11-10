import { useMemo, useState } from 'react'
import { api } from '../../api/client'
import type { Bar } from '../../api/types'
import { usePoll } from '../../api/usePoll'
import { TIMEFRAMES, type Tf } from '../../lib/chart'
import { closedBars } from '../../lib/replay'
import { nyDate, nyTime } from '../../lib/time'
import { Empty, ErrorLine, Skeleton } from '../State'
import { ExplainChart } from '../viz/ExplainChart'

const REVIEW: { label: string; tf: Tf; prompt: string }[] = [
  { label: 'Daily bias', tf: '1d', prompt: 'Look for a closed C2 sweep at a point of interest and pick your bias.' },
  { label: '4H setup', tf: '4h', prompt: 'Look for a closed 4H C2 in the daily bias direction.' },
  { label: '1H confirmation', tf: '1h', prompt: 'Check whether a change in the state of delivery confirms the bias.' },
  { label: '15m confirmation', tf: '15m', prompt: 'Check for a 15m change in the state of delivery after the 4H setup.' },
  { label: '5m entry', tf: '5m', prompt: 'Look for a 5m trigger and identify the entry, stop, and target.' },
]
const EMPTY: Bar[] = []

export function Replay({ symbol }: { symbol: string }) {
  const data = usePoll(
    () => Promise.all(TIMEFRAMES.map(async ({ tf }) => [tf, (await api.bars(symbol, tf)).slice(-300)] as const)),
    [symbol],
    3_600_000,
  )
  const frames = useMemo(() => new Map(data.data), [data.data])
  const times = useMemo(() => {
    const closes = (['5m', '1m'] as const).flatMap((tf) =>
      (frames.get(tf) ?? EMPTY).flatMap((bar) => bar.close_time === undefined ? [] : [bar.close_time]),
    )
    return [...new Set(closes)].sort((a, b) => a - b)
  }, [frames])
  const [index, setIndex] = useState(0)
  const [tf, setTf] = useState<Tf>('1d')
  const [checked, setChecked] = useState<Tf[]>([])
  const position = Math.min(index, times.length - 1)
  const cutoff = times[position]
  const visible = useMemo(() => closedBars(frames.get(tf) ?? EMPTY, cutoff), [frames, tf, cutoff])
  const move = (i: number) => {
    if (i < position) setChecked([])
    setIndex(i)
  }

  if (data.error && !data.data) return <ErrorLine error={data.error} />
  if (!data.data) return <Skeleton rows={3} />
  if (cutoff === undefined) return <Empty>No replay candles with close times for {symbol} in this build</Empty>

  return (
    <div className="grid gap-4">
      <p>Review {symbol} at your own pace. The chart reveals candles as they close. Mark each check yourself.</p>
      <div className="grid max-w-xl gap-2">
        <label htmlFor="replay-time" className="font-mono text-xs">{`${nyDate(cutoff)} ${nyTime(cutoff)} ET`}</label>
        <input id="replay-time" aria-label="Replay time" type="range" min={0} max={times.length - 1} value={position} onChange={(e) => move(Number(e.target.value))} className="w-full accent-[var(--brand)]" />
        <div className="flex flex-wrap gap-2">
          <button type="button" className="rounded-sm border px-3 py-1 disabled:opacity-40" disabled={position === 0} onClick={() => move(position - 1)}>Previous candle</button>
          <button type="button" className="rounded-sm border px-3 py-1 disabled:opacity-40" disabled={position === times.length - 1} onClick={() => move(position + 1)}>Next candle</button>
        </div>
      </div>
      <ol className="grid max-w-2xl gap-2">
        {REVIEW.map((step) => (
          <li key={step.tf} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-t py-1">
            <label className="inline-flex items-center gap-2">
              <input type="checkbox" checked={checked.includes(step.tf)} onChange={(e) => setChecked(e.target.checked ? [...checked, step.tf] : checked.filter((item) => item !== step.tf))} />
              {step.label}
            </label>
            <button type="button" aria-pressed={tf === step.tf} onClick={() => setTf(step.tf)} className="font-mono text-xs text-muted underline aria-pressed:text-brand">View {step.tf === '1d' ? 'Daily' : step.tf}</button>
            {tf === step.tf && <p className="w-full text-muted">{step.prompt}</p>}
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap items-baseline gap-3">
        <button type="button" aria-pressed={tf === '1m'} onClick={() => setTf('1m')} className="font-mono text-xs text-muted underline aria-pressed:text-brand">View 1m</button>
        <p className="text-muted">Use 1m for visual review. Apollo’s tested trigger uses 5m.</p>
      </div>
      {visible.length ? <ExplainChart bars={visible} markers={[]} lines={[]} label={`${symbol} ${tf} replay candles`} /> : <Empty>No closed {tf} candles in this window</Empty>}
    </div>
  )
}
