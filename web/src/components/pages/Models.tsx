import { api } from '../../api/client'
import type { Ledger, ModelsReport, ModelsRun } from '../../api/types'
import { usePoll } from '../../api/usePoll'
import { isStatic } from '../../lib/mode'
import { Empty, ErrorLine, Skeleton } from '../State'
import { Heatmap } from '../viz/Heatmap'
import { Line } from '../viz/Line'
import { PdmDiagram } from '../viz/PdmDiagram'
import { Block, PageHead, num, pct, table } from './parts'

const LABELS = ['trend_up', 'trend_down', 'chop', 'normal']
const MODELS: { key: string; note: string }[] = [
  { key: 'logit', note: 'logistic regression' },
  { key: 'gbm', note: 'gradient boosting' },
  { key: 'majority', note: 'baseline: always the most common regime' },
  { key: 'yesterday', note: "baseline: yesterday's regime" },
  { key: 'frequency', note: 'baseline: each regime at its share so far' },
]
const SETS = ['health', 'context', 'both'] as const
const DROPPED: Record<string, string> = {
  short_session: 'Short sessions (holidays, early closes)',
  warmup: 'Warm-up (not enough history for the indicators)',
  roll_jump: 'Contract roll jumps',
}

/** The share of sessions whose range held, over each trailing window of `n` scored sessions. */
export function rolling(sessions: ModelsRun['sessions'], n = 60): { x: string; y: number }[] {
  const scored = sessions.filter((s) => s.hit_both !== null)
  const out: { x: string; y: number }[] = []
  let hits = 0
  scored.forEach((s, i) => {
    hits += s.hit_both ? 1 : 0
    if (i >= n) hits -= scored[i - n].hit_both ? 1 : 0
    if (i >= n - 1) out.push({ x: s.date, y: hits / n })
  })
  return out
}

function LiveSince({ ledger }: { ledger: Ledger }) {
  if (!ledger.since) return <Empty>The forward record starts with the first pre-open forecast.</Empty>
  return (
    <div>
      <p className="text-lg font-semibold tracking-tight">{`Live since ${ledger.since}`}</p>
      <p className="mt-1 font-mono text-[12px] text-muted">
        {`${ledger.scored} of ${ledger.n} forecasts scored${ledger.hit_both === null ? '' : `, both bounds held on ${pct(ledger.hit_both)}`}`}
      </p>
    </div>
  )
}

function Regime({ run }: { run: ModelsRun }) {
  const chosen = run.regime[run.chosen]
  const freq = run.regime.frequency
  return (
    <>
      <table aria-label="Regime models" className={`${table} max-w-3xl`}>
        <thead>
          <tr>
            <th>Model</th>
            <th>Accuracy</th>
            <th>Log-loss</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {MODELS.filter((m) => run.regime[m.key]).map((m) => (
            <tr key={m.key}>
              <td>
                <span className="font-mono">{m.key}</span> <span className="text-muted">{m.note}</span>
              </td>
              <td className={num}>{pct(run.regime[m.key].accuracy, 1)}</td>
              <td className={num}>{run.regime[m.key].log_loss.toFixed(3)}</td>
              <td>{m.key === run.chosen && <span className="rounded-sm border border-brand px-1.5 font-mono text-[10px] text-brand">chosen</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {chosen && freq && chosen.log_loss >= freq.log_loss && (
        <p className="mt-3 font-medium text-down">The regime model does not beat the frequency baseline yet.</p>
      )}
    </>
  )
}

function Importance({ items }: { items: { feature: string; drop: number }[] }) {
  const max = Math.max(1e-9, ...items.map((i) => Math.abs(i.drop)))
  return (
    <ul aria-label="Feature importance" className="grid max-w-2xl gap-1.5">
      {items.map((i) => (
        <li key={i.feature} className="grid grid-cols-[140px_1fr_64px] items-center gap-3">
          <span className="truncate font-mono text-[12px]">{i.feature}</span>
          <span className="h-2.5 rounded-sm bg-soft">
            <span
              className={`block h-full rounded-sm ${i.drop < 0 ? 'bg-down' : 'bg-brand'}`}
              style={{ width: `${(Math.abs(i.drop) / max) * 100}%` }}
            />
          </span>
          <span className={`${num} text-right text-[12px]`}>{i.drop.toFixed(3)}</span>
        </li>
      ))}
    </ul>
  )
}

function Report({ report }: { report: ModelsReport }) {
  const run = report.both ?? report.health ?? report.context!
  const cover = rolling(run.sessions)
  return (
    <>
      <Block label="How it works">
        <PdmDiagram />
      </Block>
      <Block label="Forward record">
        <LiveSince ledger={report.ledger} />
      </Block>
      <Block
        label="Regime detector"
        note={`Scored walk-forward on ${run.regime[run.chosen]?.n ?? 0} sessions it never saw while fitting. Lower log-loss is better. The model with the lower log-loss before the holdout is the one used.`}
      >
        <Regime run={run} />
      </Block>
      {run.regime[run.chosen] && (
        <Block label={`Confusion matrix, ${run.chosen}`} note="Each cell counts sessions. The diagonal is where the model was right.">
          <div className="overflow-x-auto">
            <Heatmap labels={LABELS} matrix={run.regime[run.chosen].confusion} label={`Confusion matrix for ${run.chosen}`} />
          </div>
        </Block>
      )}
      <Block
        label="Range forecaster"
        note={`Both bounds held on ${pct(run.range.both, 1)} of ${run.range.n} sessions, against a 90% target. Mean width ${Math.round(run.range.mean_width)} points.`}
      >
        {cover.length ? (
          <Line label="Range hit rate, rolling 60 sessions" yFormat={(v) => pct(v)} zero={false} refs={[{ y: 0.9, label: '90% target' }]} series={[{ name: 'Hit rate', color: 'var(--brand)', points: cover }]} />
        ) : (
          <Empty>Fewer than 60 scored sessions so far</Empty>
        )}
        {run.range.by_regime && (
          <table aria-label="Coverage by regime" className={`${table} mt-5 max-w-md`}>
            <thead>
              <tr>
                <th>Regime that day</th>
                <th>Both bounds held</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(run.range.by_regime).map(([k, v]) => (
                <tr key={k}>
                  <td>{k.replace('_', ' ')}</td>
                  <td className={`${num} ${v < 0.9 ? 'text-down' : ''}`}>{pct(v, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Block>
      <Block label="Ablation" note="The same sessions with three feature sets: the health indicators alone, the market context alone (VIX, events), and both.">
        <table aria-label="Ablation" className={`${table} max-w-3xl`}>
          <thead>
            <tr>
              <th>Features</th>
              <th>Model</th>
              <th>Log-loss</th>
              <th>Accuracy</th>
              <th>Range held</th>
              <th>Mean width</th>
            </tr>
          </thead>
          <tbody>
            {SETS.flatMap((k) => {
              const r = report[k]
              if (!r) return []
              const m = r.regime[r.chosen]
              return [
                <tr key={k}>
                  <td>{k}</td>
                  <td className={num}>{r.chosen}</td>
                  <td className={num}>{m?.log_loss.toFixed(3)}</td>
                  <td className={num}>{pct(m?.accuracy, 1)}</td>
                  <td className={num}>{pct(r.range.both, 1)}</td>
                  <td className={num}>{Math.round(r.range.mean_width)}</td>
                </tr>,
              ]
            })}
          </tbody>
        </table>
      </Block>
      <Block
        label="Feature importance"
        note="How much worse the log-loss gets when one feature is shuffled, scored on the last 60 sessions after fitting on the rest."
      >
        {run.importance?.length ? <Importance items={run.importance} /> : <Empty>Not in this report yet</Empty>}
      </Block>
      <Block label="Data quality">
        <p className="font-mono text-[12px]">{`${run.sessions_used} of ${run.sessions_total} sessions used`}</p>
        <ul className="mt-2 grid gap-1 text-muted">
          {Object.entries(run.dropped).map(([k, n]) => (
            <li key={k} className="flex max-w-md justify-between">
              <span>{DROPPED[k] ?? k}</span>
              <span className={num}>{n}</span>
            </li>
          ))}
        </ul>
      </Block>
    </>
  )
}

export function Models({ symbol }: { symbol: string }) {
  const res = usePoll(() => api.models(symbol), [symbol], 3_600_000)
  const report = res.data && (res.data.both ?? res.data.health ?? res.data.context)?.code === symbol ? res.data : undefined
  return (
    <div>
      <PageHead title="Models">
        <p>
          The regime detector and the range forecaster for {symbol}, each against simple baselines. Research tool. Not
          financial advice.
        </p>
      </PageHead>
      {res.error?.status === 404 ? (
        <Block label="No report">
          <Empty>{`No models report for ${symbol} yet`}</Empty>
          {!isStatic() && <p className="mt-2 font-mono text-[11px] text-muted">{`python -m apollo.models.report --symbol ${symbol} --ablation`}</p>}
        </Block>
      ) : res.error && !report ? (
        <Block label="Error">
          <ErrorLine error={res.error} />
        </Block>
      ) : !report ? (
        <Block label="Models">
          <Skeleton rows={4} />
        </Block>
      ) : (
        <Report report={report} />
      )}
    </div>
  )
}
