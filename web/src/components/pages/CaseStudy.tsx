import { useMemo, useState } from 'react'
import { api } from '../../api/client'
import type { Day, Entry } from '../../api/types'
import { usePoll } from '../../api/usePoll'
import { nyDate, toSec } from '../../lib/time'
import { Empty, ErrorLine, Skeleton } from '../State'
import { Calendar } from '../journal/Stats'
import { Block, PageHead, num, pct, r2, table, usd } from './parts'

export const REPORT_URL = 'https://vaughnantonio.github.io/mnq-trading-case-study/analysis/report.html'

const FINDINGS = [
  ['No edge proven yet.', 'Every stage made money, but no group had 30 days of trades and most of the confidence ranges crossed zero.'],
  ['Size was a bigger risk than setup choice.', "My worst funded day lost 2.8 times the account's whole drawdown limit. Earlier profits saved the account; a new one would have failed."],
  ['The days I tagged "Gamba" lost heavily.', 'Days traded with ModelV2 made money.'],
  ['The backtest looked too good.', 'Every backtest day was a winner, which points to hindsight.'],
  ['The market helped.', 'In my live window Nasdaq trended up hard, and holding 1 MNQ did as well as me or better per unit of size.'],
  ['The journal had gaps.', 'Only 9% of funded trades were written up, so A, B and C setups could not be compared.'],
]

const QUESTIONS: [string, string, string][] = [
  ['Q1', 'Win rate, average win and loss, expectancy per trade?', 'The Backtest page shows each variant\'s expectancy with a 95% bootstrap range. A positive mean whose range crosses zero reads as unproven.'],
  ['Q2', 'Do A setups beat B and C?', 'Every journal entry can carry a grade, and the journal stats split results by grade once there are enough trades.'],
  ['Q3', 'Which strategy performs best?', 'The journal stats keep trades taken from the signal, trades taken by hand and skipped signals apart.'],
  ['Q4', 'Does performance drop from backtest to live?', 'Each forecast goes into a dated ledger before the session and is scored after it, so the live record cannot be tidied up later.'],
  ['Q5', 'Drawdowns against prop-firm limits?', 'The prop-firm Monte Carlo gives pass and breach odds at 1% and 2% risk, and the risk rules stop trading for the day at the daily cap.'],
  ['Q6', 'Trend days against choppy days?', 'The regime detector forecasts the day type before the open, and the ablation shows whether filtering on it helps.'],
  ['Q7', 'The journal against a simple MA trend rule?', 'Every backtest runs buy & hold and the MA 20/50 rule over the same dates, drawn on the same equity chart.'],
]

type StageRow = { stage: string; n: number; win_rate: number; mean_r: number }

/** Numbers for the case study's own trades only: per stage, the worst day, and a daily calendar. */
export function caseStats(entries: Entry[]): { n: number; byStage: StageRow[]; worst: Day | null; calendar: Day[] } {
  const rows = entries.filter((e) => e.source === 'imported' && e.r !== null)
  const stages = new Map<string, number[]>()
  const days = new Map<string, Day>()
  for (const e of rows) {
    const stage = e.stage ?? '(none)'
    stages.set(stage, [...(stages.get(stage) ?? []), e.r!])
    const date = nyDate(toSec(e.opened_at))
    const d = days.get(date) ?? { date, n: 0, r: 0, 'pnl_$': 0 }
    days.set(date, { date, n: d.n + 1, r: d.r + e.r!, 'pnl_$': d['pnl_$'] + (e['pnl_$'] ?? 0) })
  }
  const byStage = [...stages].map(([stage, rs]) => ({
    stage,
    n: rs.length,
    win_rate: rs.filter((r) => r > 0).length / rs.length,
    mean_r: rs.reduce((a, b) => a + b, 0) / rs.length,
  }))
  const calendar = [...days.values()].sort((a, b) => a.date.localeCompare(b.date))
  const worst = calendar.reduce<Day | null>((w, d) => (w === null || d.r < w.r ? d : w), null)
  return { n: rows.length, byStage, worst, calendar }
}

export function CaseStudy() {
  const list = usePoll(api.journal.list, [], 3_600_000)
  const stats = useMemo(() => caseStats(list.data ?? []), [list.data])
  const [day, setDay] = useState<string | null>(null)

  return (
    <div>
      <PageHead title="Case study">
        <p>
          Before Apollo I analysed 51 of my own MNQ trades in R, from backtest to funded account. Apollo exists to answer
          the questions that analysis left open.{' '}
          <a href={REPORT_URL} target="_blank" rel="noreferrer" className="text-brand underline underline-offset-2">
            Read the full report
          </a>
        </p>
      </PageHead>
      <Block label="What the report found">
        <ul className="grid max-w-[70ch] gap-2.5">
          {FINDINGS.map(([head, rest]) => (
            <li key={head}>
              <span className="font-medium">{head}</span> <span className="text-muted">{rest}</span>
            </li>
          ))}
        </ul>
      </Block>
      <Block label="What Apollo does about it">
        <div className="overflow-x-auto">
          <table aria-label="Questions" className={`${table} [&_td]:align-top`}>
            <thead>
              <tr>
                <th>#</th>
                <th>Question in the report</th>
                <th>Where Apollo answers it</th>
              </tr>
            </thead>
            <tbody>
              {QUESTIONS.map(([q, ask, answer]) => (
                <tr key={q}>
                  <td className={num}>{q}</td>
                  <td className="max-w-[30ch]">{ask}</td>
                  <td className="max-w-[60ch] text-muted">{answer}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Block>
      <Block label="The imported trades" note="Dollar amounts are scaled by one hidden factor, as in the public data. R is unscaled.">
        {list.error && !list.data ? (
          <ErrorLine error={list.error} />
        ) : !list.data ? (
          <Skeleton rows={3} />
        ) : stats.n === 0 ? (
          <Empty>Import the case study with python -m apollo.journal.importer --csv-dir &lt;case study&gt;/data/public</Empty>
        ) : (
          <>
            <p className="mb-4 font-mono">{`${stats.n} trades`}</p>
            <table aria-label="By stage" className={`${table} max-w-xl`}>
              <thead>
                <tr>
                  <th>Stage</th>
                  <th>Trades</th>
                  <th>Win rate</th>
                  <th>Mean R</th>
                </tr>
              </thead>
              <tbody>
                {stats.byStage.map((s) => (
                  <tr key={s.stage}>
                    <td>{s.stage.replace('_', ' ')}</td>
                    <td className={num}>{s.n}</td>
                    <td className={num}>{pct(s.win_rate)}</td>
                    <td className={`${num} ${s.mean_r < 0 ? 'text-down' : ''}`}>{r2(s.mean_r)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {stats.worst && (
              <p className="mt-4 font-mono text-[12px]">
                <span className="text-muted">Worst day </span>
                {`${stats.worst.date} `}
                <span className="text-down">{`${r2(stats.worst.r)}, ${usd(stats.worst['pnl_$'])} scaled`}</span>
              </p>
            )}
            <div className="max-w-sm">
              <Calendar days={stats.calendar} day={day} onDay={setDay} />
            </div>
          </>
        )}
      </Block>
    </div>
  )
}
