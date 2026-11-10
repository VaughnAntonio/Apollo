import { useState, type FormEvent, type ReactNode } from 'react'
import { api, ApiError } from '../api/client'
import type { CheckRow, Entry, Signal } from '../api/types'
import { usePoll } from '../api/usePoll'
import { isStatic } from '../lib/mode'
import { fmtPct, fmtPrice, fmtR, fmtUsd, message, openR, parseNum, parseSize } from '../lib/trade'
import { Empty, ErrorLine, Skeleton } from './State'

const STEPS: Record<string, string> = {
  daily_bias: 'Daily bias',
  '4h': '4H',
  '1h': '1H',
  '15m': '15m',
  '5m_trigger': '5m trigger',
}

const DOT: Record<CheckRow['status'], string> = {
  pass: 'bg-ink border-ink',
  wait: 'border-ink',
  fail: 'bg-down border-down',
  no_data: 'border-muted border-dashed',
}

type Props = {
  symbol: string
  openTrade: Entry | null
  lastClose: number | null
  onTaken: (id: number) => void
  onChanged: () => void
}

function Section({ label, tour, children }: { label: string; tour?: string; children: ReactNode }) {
  return (
    <section data-tour={tour} className="border-b px-5 py-4">
      <h2 className="mb-3 font-mono text-[10px] font-medium tracking-widest text-muted uppercase">{label}</h2>
      {children}
    </section>
  )
}

function Kv({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="flex justify-between py-1 font-mono">
      <span className="font-sans text-muted">{k}</span>
      <span>{v}</span>
    </div>
  )
}

const btn = 'rounded-sm bg-brand px-3 py-1.5 font-mono text-[10px] font-medium tracking-widest text-brand-fg uppercase'
const ghost = 'rounded-sm border px-3 py-1.5 font-mono text-[10px] font-medium tracking-widest uppercase'
const field = 'w-full rounded-sm border bg-transparent px-2 py-1 font-mono'

function Checklist({ signal }: { signal: Signal }) {
  if (signal.status === 'no_model') return <Empty>Model not trained for this symbol</Empty>
  if (!signal.checklist.length) return <Empty>No checklist yet</Empty>
  return (
    <ul>
      {signal.checklist.map((r) => (
        <li key={r.step} className="grid grid-cols-[12px_auto_1fr] items-start gap-2.5 py-1.5">
          <span aria-label={r.status} className={`mt-1 size-[7px] rounded-full border ${DOT[r.status]}`} />
          <span>{STEPS[r.step] ?? r.step}</span>
          <span className="text-right font-mono text-[11px] text-muted">{r.detail}</span>
        </li>
      ))}
    </ul>
  )
}

function TakeTrade({ symbol, signal, onTaken }: { symbol: string; signal: Signal; onTaken: (id: number) => void }) {
  const [form, setForm] = useState<{ fill: string; size: string } | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)

  if (!form) {
    return (
      <button
        type="button"
        data-tour="take-trade"
        className={`${btn} mt-3 w-full`}
        onClick={() => setForm({ fill: String(signal.entry ?? ''), size: String(signal.contracts ?? 1) })}
      >
        Take trade
      </button>
    )
  }
  const save = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const fill = parseNum('Fill', form.fill)
      const size = form.size.trim() === '' ? undefined : parseSize(form.size)
      const { id } = await api.journal.take(symbol, { ...(fill === undefined ? {} : { fill }), ...(size === undefined ? {} : { size }) })
      setForm(null)
      onTaken(id)
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(message(err), -1))
    } finally {
      setBusy(false)
    }
  }
  return (
    <form onSubmit={save} className="mt-3 grid gap-2">
      <div className="grid grid-cols-2 gap-2">
        <label className="grid gap-1 text-muted">
          Fill
          <input inputMode="decimal" className={field} value={form.fill} onChange={(e) => setForm({ ...form, fill: e.target.value })} />
        </label>
        <label className="grid gap-1 text-muted">
          Contracts
          <input inputMode="numeric" className={field} value={form.size} onChange={(e) => setForm({ ...form, size: e.target.value })} />
        </label>
      </div>
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className={btn}>
          Save trade
        </button>
        <button type="button" className={ghost} onClick={() => (setForm(null), setError(null))}>
          Cancel
        </button>
      </div>
      {error && <ErrorLine error={error} />}
    </form>
  )
}

function OpenTrade({ trade, lastClose, onChanged }: { trade: Entry; lastClose: number | null; onChanged: () => void }) {
  const [exit, setExit] = useState<string | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const done = trade.needs_confirm && trade.exit !== null
  const at = done ? trade.exit : lastClose
  const r = at === null ? null : openR(trade, at)

  const close = async (body: { exit: number | string; at?: string; reason?: string }) => {
    setError(null)
    try {
      const exit = typeof body.exit === 'number' ? body.exit : parseNum('Exit', body.exit)
      if (exit === undefined) throw new Error('Exit must be a number')
      await api.journal.close(trade.id, { ...body, exit })
      setExit(null)
      onChanged()
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(message(err), -1))
    }
  }

  return (
    <div>
      <div className="mb-2.5 flex items-baseline justify-between">
        <strong className={`text-[22px] font-semibold tracking-tight ${trade.side === 'short' ? 'text-down' : 'text-brand'}`}>
          {trade.side === 'short' ? 'Short' : 'Long'}
        </strong>
        <span className="font-mono">{`${trade.size ?? ''} ${trade.symbol}`}</span>
      </div>
      <Kv k="Entry" v={fmtPrice(trade.entry)} />
      <Kv k="Stop" v={fmtPrice(trade.stop)} />
      <Kv k="Target" v={fmtPrice(trade.target)} />
      <Kv k={done ? 'R at exit' : 'Open R'} v={<span className={r !== null && r < 0 ? 'text-down' : 'text-brand'}>{fmtR(r)}</span>} />
      {done ? (
        <div className="mt-3 grid gap-2">
          <p className="text-muted">{`Closed at ${fmtPrice(trade.exit)} (${trade.exit_reason?.replace('_auto', '')}). Check the fill.`}</p>
          <button
            type="button"
            className={btn}
            onClick={() => close({ exit: trade.exit!, at: trade.closed_at ?? undefined, reason: trade.exit_reason ?? 'manual' })}
          >
            Confirm exit
          </button>
        </div>
      ) : exit === null ? (
        <button type="button" className={`${ghost} mt-3 w-full`} onClick={() => setExit(lastClose === null ? '' : String(lastClose))}>
          Close trade
        </button>
      ) : (
        <form
          className="mt-3 grid gap-2"
          onSubmit={(e) => (e.preventDefault(), close({ exit, reason: 'manual' }))}
        >
          <label className="grid gap-1 text-muted">
            Exit
            <input inputMode="decimal" className={field} value={exit} onChange={(e) => setExit(e.target.value)} />
          </label>
          <div className="flex gap-2">
            <button type="submit" className={btn}>
              Save exit
            </button>
            <button type="button" className={ghost} onClick={() => setExit(null)}>
              Cancel
            </button>
          </div>
        </form>
      )}
      {error && <ErrorLine error={error} />}
    </div>
  )
}

type SignalProps = { symbol: string; signal: Signal; stale: boolean; onTaken: (id: number) => void }

function SignalPanel({ symbol, signal, stale, onTaken }: SignalProps) {
  if (signal.status === 'no_model') return <Empty>No signal for this symbol</Empty>
  if (signal.status !== 'trigger') return <Empty>No trade signal</Empty>
  const long = signal.direction === 'bull'
  return (
    <div>
      <div className="mb-2.5 flex items-baseline justify-between">
        <strong className={`text-[22px] font-semibold tracking-tight ${long ? 'text-brand' : 'text-down'}`}>{long ? 'Long' : 'Short'}</strong>
        <span className="font-mono">{`${signal.contracts} ${signal.symbol}`}</span>
      </div>
      <Kv k="Entry" v={fmtPrice(signal.entry)} />
      <Kv k="Stop" v={fmtPrice(signal.stop)} />
      <Kv k="Target" v={fmtPrice(signal.target)} />
      <Kv k="Planned stop risk" v={fmtUsd(signal.risk_usd ?? null)} />
      <Kv k="Account value" v={fmtPct(signal.risk_of_account ?? null)} />
      <Kv k="Drawdown limit" v={fmtPct(signal.risk_of_limit)} />
      <div className="mt-1 h-[3px] bg-soft">
        <i className="block h-full bg-ink" style={{ width: `${Math.min(100, (signal.risk_of_limit ?? 0) * 100)}%` }} />
      </div>
      {!stale && !isStatic() && <TakeTrade symbol={symbol} signal={signal} onTaken={onTaken} />}
    </div>
  )
}

export function Rail({ symbol, openTrade, lastClose, onTaken, onChanged }: Props) {
  const sig = usePoll(() => api.signal(symbol), [symbol])
  const fc = usePoll(() => api.forecast(symbol), [symbol], 3_600_000)
  const mc = fc.data?.model_check

  return (
    <aside className="border-t md:overflow-auto md:border-t-0 md:border-l">
      <Section label="Top-down" tour="checklist">
        {sig.data ? (
          <>
            <Checklist signal={sig.data} />
            {sig.error && <ErrorLine error={sig.error} />}
          </>
        ) : sig.error ? (
          <ErrorLine error={sig.error} />
        ) : (
          <Skeleton rows={5} />
        )}
      </Section>
      <Section label={openTrade ? 'Open trade' : 'Signal'} tour="signal">
        {openTrade ? (
          <OpenTrade trade={openTrade} lastClose={lastClose} onChanged={onChanged} />
        ) : sig.data ? (
          <>
            <SignalPanel symbol={symbol} signal={sig.data} stale={!!sig.error} onTaken={onTaken} />
            {sig.error && <ErrorLine error={sig.error} />}
          </>
        ) : sig.error ? (
          <ErrorLine error={sig.error} />
        ) : (
          <Skeleton rows={4} />
        )}
      </Section>
      <Section label="Model check, last 60 sessions" tour="model-check">
        {fc.data?.status === 'no_model' ? (
          <Empty>Nothing to check yet</Empty>
        ) : mc ? (
          <>
            <div data-tour="range">
              <Kv k="Range hit rate" v={fmtPct(mc.range_hit)} />
            </div>
            <div data-tour="regime">
              <Kv k="Regime accuracy" v={fmtPct(mc.regime_accuracy)} />
            </div>
            {fc.error && <ErrorLine error={fc.error} />}
          </>
        ) : fc.error ? (
          <ErrorLine error={fc.error} />
        ) : (
          <Skeleton rows={2} />
        )}
      </Section>
    </aside>
  )
}
