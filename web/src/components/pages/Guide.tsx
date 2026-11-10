import { useState, type ReactNode } from 'react'
import { api } from '../../api/client'
import type { Explain, Setup } from '../../api/types'
import { usePoll } from '../../api/usePoll'
import { fmtPrice } from '../../lib/trade'
import { Empty, ErrorLine, Skeleton } from '../State'
import { ExplainChart, type Level, type Mark } from '../viz/ExplainChart'
import { PdmDiagram } from '../viz/PdmDiagram'
import { Block, PageHead, num, pct } from './parts'

const label = (s: string) => s.replace('_', ' ')

/** What the Fractal chart shows at each step. Steps 0-2 are on the daily bars, 3-4 on the hourly. */
export function fractalStep(s: Setup, step: number): { tf: 'htf' | 'ltf'; markers: Mark[]; lines: Level[] } {
  const bear = s.direction === 'bear'
  const above = bear ? 'aboveBar' : 'belowBar'
  if (step <= 2) {
    const markers: Mark[] = [{ time: s.c1_ts, text: 'C1', position: above, tone: 'ink' }]
    const lines: Level[] = []
    if (step >= 1) {
      markers.push({ time: s.c2_ts, text: 'C2', position: above, tone: 'brand' })
      if (s.poi_level !== null) lines.push({ price: s.poi_level, title: 'POI', tone: 'muted', dashed: true })
    }
    if (step >= 2) markers.push({ time: s.c2_close, text: 'C3', position: bear ? 'belowBar' : 'aboveBar', tone: 'brand' })
    return { tf: 'htf', markers, lines }
  }
  const markers: Mark[] = [{ time: s.cisd_ts, text: 'CISD', position: bear ? 'belowBar' : 'aboveBar', tone: 'brand' }]
  const lines: Level[] = [
    { price: s.cisd_level, title: 'CISD', tone: 'brand', dashed: true },
    { price: s.protected, title: bear ? 'Protected high' : 'Protected low', tone: 'muted', dashed: true },
  ]
  if (step >= 4) {
    if (s.entry_ts !== null) markers.push({ time: s.entry_ts, text: 'Entry', position: bear ? 'aboveBar' : 'belowBar', tone: 'ink' })
    lines.push(
      { price: s.entry, title: 'Entry', tone: 'ink' },
      { price: s.stop, title: 'Stop', tone: 'down' },
      { price: s.target, title: 'Target', tone: 'brand' },
    )
  }
  return { tf: 'ltf', markers, lines }
}

function Stepper({ name, steps, step, onStep, children }: { name: string; steps: string[]; step: number; onStep: (n: number) => void; children: ReactNode }) {
  return (
    <div className="grid gap-4">
      <div className="grid max-w-xl gap-2">
        <input
          type="range"
          min={0}
          max={steps.length - 1}
          step={1}
          value={step}
          aria-label={`${name} step`}
          aria-valuetext={steps[step]}
          onChange={(e) => onStep(Number(e.target.value))}
          className="w-full accent-[var(--brand)]"
        />
        <ol className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[11px]">
          {steps.map((s, i) => (
            <li key={s}>
              <button type="button" onClick={() => onStep(i)} className={i === step ? 'text-ink' : 'text-muted hover:text-ink'}>
                {`${i + 1}. ${s}`}
              </button>
            </li>
          ))}
        </ol>
      </div>
      {children}
    </div>
  )
}

const FRACTAL_STEPS = ['C1', 'C2 sweep at the POI', 'C3', '1H CISD', 'Entry, stop, target']
const FRACTAL_NOTES = [
  'C1 is the daily candle whose high or low the next day will take.',
  'C2 trades beyond C1 into a point of interest (a swing or a gap) and closes back inside. That failed break is the sweep.',
  'C3 is the day the reversal should play out, away from the swept side.',
  'On the hourly chart, a change in the state of delivery (CISD) confirms the turn. The swing it leaves behind is protected.',
  'Entry is at the CISD, the stop sits just beyond the protected level, and the target is the far side of C1, capped at the reward the risk rules allow.',
]

function Fractal({ x }: { x: Explain }) {
  const [step, setStep] = useState(0)
  const s = x.fractal.setup
  const view = fractalStep(s, step)
  return (
    <Stepper name="Fractal Model" steps={FRACTAL_STEPS} step={step} onStep={setStep}>
      <p className="max-w-[65ch]">{FRACTAL_NOTES[step]}</p>
      <ExplainChart
        bars={view.tf === 'htf' ? x.fractal.htf : x.fractal.ltf}
        markers={view.markers}
        lines={view.lines}
        label={`${view.tf === 'htf' ? 'Daily' : 'Hourly'} ${x.symbol} bars around ${x.date}`}
      />
      <ul aria-label="On the chart" className="grid gap-1 font-mono text-[12px]">
        {view.markers.filter((m) => !view.lines.some((l) => l.title === m.text)).map((m) => (
          <li key={`m-${m.text}`}>{`${m.text} marked on the ${view.tf === 'htf' ? 'daily' : 'hourly'} bar`}</li>
        ))}
        {view.lines.map((l) => (
          <li key={`l-${l.title}`}>{`${l.title} ${fmtPrice(l.price)}`}</li>
        ))}
      </ul>
    </Stepper>
  )
}

const REGIME_STEPS = ['Health indicators', 'Forecast', 'What happened']

function Regime({ x }: { x: Explain }) {
  const [step, setStep] = useState(0)
  const g = x.regime
  const top = Object.entries(g.proba).sort((a, b) => b[1] - a[1])[0]
  return (
    <Stepper name="Regime detector" steps={REGIME_STEPS} step={step} onStep={setStep}>
      <PdmDiagram />
      {step === 0 && (
        <>
          <p className="max-w-[65ch]">The indicators for {x.date}, computed from bars up to 08:00 New York time that morning.</p>
          <ul className="grid max-w-md gap-1">
            {Object.entries(g.features).map(([k, v]) => (
              <li key={k} className="flex justify-between border-t py-1">
                <span className="font-mono text-[12px]">{k}</span>
                <span className={num}>{v === null ? '–' : v.toFixed(3)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
      {step >= 1 && (
        <ul aria-label="Regime odds" className="grid max-w-md gap-1.5">
          {Object.entries(g.proba).map(([k, p]) => (
            <li key={k} className="grid grid-cols-[100px_1fr_48px] items-center gap-3">
              <span>{label(k)}</span>
              <span className="h-2.5 rounded-sm bg-soft">
                <span className={`block h-full rounded-sm ${k === top[0] ? 'bg-brand' : 'bg-muted/50'}`} style={{ width: `${p * 100}%` }} />
              </span>
              <span className={`${num} text-right`}>{pct(p)}</span>
            </li>
          ))}
        </ul>
      )}
      {step === 2 && (
        <p className="max-w-[65ch]">
          {`The model's favourite was ${label(top[0])} (${pct(top[1])}). The day was ${label(g.label)}.`}
          {top[0] === g.label ? ' It was right this time.' : ' It was wrong this time, which happens on most days: see the Models page.'}
        </p>
      )}
    </Stepper>
  )
}

const RANGE_STEPS = ['Open', 'Bounds', 'The day', 'Last 60 sessions']

function RangeLine({ r, step }: { r: Explain['range']; step: number }) {
  const lo = Math.min(r.open - r.down_bound, r.low) - 50
  const hi = Math.max(r.open + r.up_bound, r.high) + 50
  const x = (v: number) => 10 + ((v - lo) / (hi - lo)) * 620
  return (
    <svg role="img" aria-label={`Range for the day: open ${fmtPrice(r.open)}, bounds ${fmtPrice(r.open - r.down_bound)} to ${fmtPrice(r.open + r.up_bound)}`} viewBox="0 0 640 90" className="h-auto w-full max-w-3xl">
      <line x1={10} x2={630} y1={45} y2={45} stroke="var(--line)" />
      {step >= 1 && <rect x={x(r.open - r.down_bound)} y={30} width={x(r.open + r.up_bound) - x(r.open - r.down_bound)} height={30} rx={3} fill="color-mix(in oklab, var(--brand) 22%, transparent)" stroke="var(--brand)" />}
      <line x1={x(r.open)} x2={x(r.open)} y1={22} y2={68} stroke="var(--ink)" strokeWidth={2} />
      <text x={x(r.open)} y={16} textAnchor="middle" className="fill-ink font-mono text-[10px]">open</text>
      {step >= 2 &&
        [
          ['low', r.low],
          ['high', r.high],
        ].map(([name, v]) => {
          const out = name === 'low' ? (v as number) < r.open - r.down_bound : (v as number) > r.open + r.up_bound
          return (
            <g key={name}>
              <circle cx={x(v as number)} cy={45} r={5} fill={out ? 'var(--down)' : 'var(--ink)'} />
              <text x={x(v as number)} y={84} textAnchor="middle" className="fill-muted font-mono text-[10px]">{name}</text>
            </g>
          )
        })}
    </svg>
  )
}

function Range({ x }: { x: Explain }) {
  const [step, setStep] = useState(0)
  const r = x.range
  const misses = r.coverage_60.filter((c) => !c.hit_both).length
  const notes = [
    `The session opened at ${fmtPrice(r.open)}.`,
    `Before the open the forecaster set a bound ${Math.round(r.up_bound)} points above and ${Math.round(r.down_bound)} below. They are meant to hold on 90% of days.`,
    `The day's high was ${fmtPrice(r.high)} and its low ${fmtPrice(r.low)}. ${r.hit_both ? 'Both bounds held.' : 'A bound broke.'}`,
    'Each square is one session, oldest first. Red squares are days a bound broke.',
  ]
  return (
    <Stepper name="Range forecaster" steps={RANGE_STEPS} step={step} onStep={setStep}>
      <p className="max-w-[65ch]">{notes[step]}</p>
      {step < 3 ? (
        <RangeLine r={r} step={step} />
      ) : (
        <div>
          <div className="flex max-w-3xl flex-wrap gap-0.5">
            {r.coverage_60.map((c) => (
              <span key={c.date} title={`${c.date}: ${c.hit_both ? 'held' : 'broke'}`} className={`size-3 rounded-[2px] ${c.hit_both ? 'bg-brand/70' : 'bg-down'}`} />
            ))}
          </div>
          <p className="mt-2 font-mono text-[12px]">{`${misses} ${misses === 1 ? 'miss' : 'misses'} in ${r.coverage_60.length} sessions`}</p>
        </div>
      )}
    </Stepper>
  )
}

/** How Apollo works: the tour over the chart screen, and worked examples on one past MNQ day. */
export function Guide({ onTour }: { onTour: () => void }) {
  const res = usePoll(() => api.explain('MNQ'), [], 3_600_000)
  const x = res.data
  return (
    <div>
      <PageHead title="Guide">
        <p>A one-minute tour of the chart screen, then the three models worked through on one real MNQ day{x ? `, ${x.date}` : ''}.</p>
      </PageHead>
      <div className="border-b px-5 py-6">
        <button
          type="button"
          onClick={onTour}
          className="rounded-sm bg-brand px-3 py-2 font-mono text-[10px] font-medium tracking-widest text-brand-fg uppercase"
        >
          Take the tour
        </button>
      </div>
      {res.error && !x ? (
        <Block label="Worked example">
          {res.error.status === 404 ? <Empty>The worked example is not available yet</Empty> : <ErrorLine error={res.error} />}
        </Block>
      ) : !x ? (
        <Block label="Worked example">
          <Skeleton rows={4} />
        </Block>
      ) : (
        <>
          <Block label="Fractal Model" note="TTrades' Fractal Model, codified: a daily setup confirmed on the hourly chart.">
            <Fractal x={x} />
          </Block>
          <Block label="Regime detector">
            <Regime x={x} />
          </Block>
          <Block label="Range forecaster">
            <Range x={x} />
          </Block>
        </>
      )}
    </div>
  )
}
