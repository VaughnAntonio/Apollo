import { useState } from 'react'
import { api } from '../../api/client'
import type { BacktestRecord, Layer } from '../../api/types'
import { usePoll } from '../../api/usePoll'
import { isStatic } from '../../lib/mode'
import { Empty, ErrorLine, Skeleton } from '../State'
import { Bars, type Bin } from '../viz/Bars'
import { Line, type Series } from '../viz/Line'
import { Block, PageHead, Tabs, dash, num, pct, r2, table, usd } from './parts'

const LAYERS: Layer[] = ['D-1H', '1H-5m']

/** Trade R in half-R bins from the lowest to the highest trade, empty bins included. */
export function rBins(rs: number[]): Bin[] {
  if (!rs.length) return []
  const lo = Math.floor(Math.min(...rs) / 0.5)
  const hi = Math.floor(Math.max(...rs) / 0.5)
  return Array.from({ length: hi - lo + 1 }, (_, i) => {
    const start = (lo + i) * 0.5
    return {
      label: `${start < 0 ? '−' : '+'}${Math.abs(start).toFixed(1)}`,
      value: rs.filter((r) => Math.floor(r / 0.5) === lo + i).length,
      tone: start < 0 ? 'down' : 'up',
    }
  })
}

function curves(rec: BacktestRecord): Series[] {
  const c = rec.curves
  if (!c) return []
  const pts = (p: { date: string; usd: number }[] = []) => p.map((d) => ({ x: d.date, y: d.usd }))
  return [
    { name: 'Strategy', color: 'var(--brand)', points: pts(c.strategy) },
    { name: 'Buy & hold', color: 'var(--muted)', points: pts(c.buy_hold) },
    { name: 'MA 20/50', color: 'var(--muted)', dashed: true, points: pts(c.ma_20_50) },
  ].filter((s) => s.points.length)
}

function Variants({ recs, chosen, onChoose }: { recs: BacktestRecord[]; chosen: string; onChoose: (v: string) => void }) {
  return (
    <div className="overflow-x-auto">
      <table aria-label="Variants" className={table}>
        <thead>
          <tr>
            <th>Variant</th>
            <th>Trades</th>
            <th>Expectancy</th>
            <th>95% range</th>
            <th>Win rate</th>
            <th>Max DD</th>
            <th>Pass at 1%</th>
            <th>Pass at 2%</th>
          </tr>
        </thead>
        <tbody>
          {recs.map((r) => (
            <tr key={r.variant}>
              <td>
                <button
                  type="button"
                  aria-pressed={r.variant === chosen}
                  onClick={() => onChoose(r.variant)}
                  className="font-mono text-muted hover:text-brand aria-pressed:text-brand"
                >
                  {r.variant}
                </button>
              </td>
              <td className={num}>{r.expectancy.n}</td>
              <td className={`${num} ${(r.expectancy.mean ?? 0) < 0 ? 'text-down' : ''}`}>{r2(r.expectancy.mean)}</td>
              <td className={`${num} text-muted`}>{r.expectancy.n ? `${r2(r.expectancy.low)} to ${r2(r.expectancy.high)}` : dash}</td>
              <td className={num}>{r.expectancy.n ? pct(r.expectancy.win_rate) : dash}</td>
              <td className={num}>{r.expectancy.n ? r2(r.equity.max_dd_r) : dash}</td>
              <td className={num}>{pct(r.monte_carlo['1%'].p_pass, 1)}</td>
              <td className={num}>{pct(r.monte_carlo['2%'].p_pass, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Detail({ rec }: { rec: BacktestRecord }) {
  const rs = (rec.trades ?? []).flatMap((t) => (t.r === null ? [] : [t.r]))
  const series = curves(rec)
  return (
    <>
      <Block
        label={`Equity, ${rec.variant}`}
        note="The strategy is sized by the risk rules. Buy & hold and MA 20/50 hold 1 contract over the same dates."
      >
        {series.length ? <Line label={`Equity in dollars, ${rec.variant}`} yFormat={usd} series={series} /> : <Empty>No closed trades</Empty>}
      </Block>
      <Block label="R per trade" note={`${rs.length} trades in bins of 0.5R. Losses are red.`}>
        {rs.length ? <Bars label="Trades by R" bins={rBins(rs)} /> : <Empty>No closed trades</Empty>}
      </Block>
      <Block label="By month">
        {rec.monthly?.length ? (
          <table aria-label="Monthly" className={`${table} max-w-xl`}>
            <thead>
              <tr>
                <th>Month</th>
                <th>Trades</th>
                <th>Total R</th>
                <th>Net</th>
              </tr>
            </thead>
            <tbody>
              {rec.monthly.map((m) => (
                <tr key={m.month}>
                  <td className={num}>{m.month}</td>
                  <td className={num}>{m.n}</td>
                  <td className={`${num} ${m.r < 0 ? 'text-down' : ''}`}>{r2(m.r)}</td>
                  <td className={`${num} ${m['net_$'] < 0 ? 'text-down' : ''}`}>{usd(m['net_$'])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <Empty>No closed trades</Empty>
        )}
      </Block>
      <Block
        label="Prop-firm Monte Carlo"
        note="Each run resamples these trades into a new order and plays them through the account until it passes or breaches."
      >
        <table aria-label="Monte Carlo" className={`${table} max-w-xl`}>
          <thead>
            <tr>
              <th>Risk per trade</th>
              <th>Pass</th>
              <th>Breach</th>
              <th>Median trades to pass</th>
            </tr>
          </thead>
          <tbody>
            {(['1%', '2%'] as const).map((k) => {
              const m = rec.monte_carlo[k]
              return (
                <tr key={k}>
                  <td className={num}>{k}</td>
                  <td className={num}>{pct(m.p_pass, 1)}</td>
                  <td className={num}>{pct(m.p_breach, 1)}</td>
                  <td className={num}>{m.median_trades_to_pass ?? dash}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Block>
    </>
  )
}

export function Backtest({ symbol }: { symbol: string }) {
  const [layer, setLayer] = useState<Layer>('D-1H')
  const [chosen, setChosen] = useState('plain')
  const res = usePoll(() => api.backtest(symbol, layer), [symbol, layer], 3_600_000)
  const recs = res.data && res.data[0]?.code === symbol && res.data[0]?.layer === layer ? res.data : undefined
  const rec = recs?.find((r) => r.variant === chosen) ?? recs?.[0]
  const first = recs?.[0]

  return (
    <div>
      <PageHead title="Backtest">
        <p>
          The codified Fractal Model on {symbol}, with each filter switched on and off. Every number here comes from
          sessions before the holdout, which stays untouched until the final test.
        </p>
      </PageHead>
      <div className="flex flex-wrap items-center gap-4 border-b px-5 py-3">
        <Tabs label="Layer" value={layer} options={LAYERS} onChange={setLayer} />
        {first && (
          <span className="font-mono text-[11px] text-muted">
            {`${first.final ? 'Final test on the holdout' : `Development backtest, holdout locked from ${first.holdout_from}`} · ${first.period.start ?? dash} to ${first.period.end ?? dash}`}
            {first.attempt !== undefined && ` · ${first.attempt} backtest runs logged so far`}
          </span>
        )}
      </div>
      {res.error?.status === 404 ? (
        <Block label="No report">
          <Empty>{`No backtest for ${symbol} yet`}</Empty>
          {!isStatic() && (
            <p className="mt-2 font-mono text-[11px] text-muted">{`python -m apollo.strategy.backtest --symbol ${symbol} --layer ${layer}`}</p>
          )}
        </Block>
      ) : res.error && !recs ? (
        <Block label="Error">
          <ErrorLine error={res.error} />
        </Block>
      ) : !recs || !rec ? (
        <Block label="Variants">
          <Skeleton rows={4} />
        </Block>
      ) : (
        <>
          <Block label="Variants" note="Pick a variant to see its equity, trades and Monte Carlo below. Research tool. Not financial advice.">
            <Variants recs={recs} chosen={rec.variant} onChoose={setChosen} />
          </Block>
          <Detail rec={rec} />
          {!isStatic() && (
            <p className="px-5 py-4 font-mono text-[11px] text-muted">
              {`Full tearsheet: reports/tearsheet_${symbol}_${layer}_${rec.variant}.html (made with --tearsheet)`}
            </p>
          )}
        </>
      )}
    </div>
  )
}
