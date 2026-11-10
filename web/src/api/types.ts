// The Plan 5 API's JSON, field for field.

export type Sym = { code: string; name: string; kind: 'future' | 'stock'; model_enabled: boolean }

/** `time` is the bar's open time in UTC seconds. */
export type Bar = { time: number; open: number; high: number; low: number; close: number; volume: number }

export type CheckRow = { step: string; status: 'pass' | 'wait' | 'fail' | 'no_data'; detail: string }

export type Signal = {
  symbol: string
  status: 'trigger' | 'waiting' | 'flat' | 'no_model'
  direction: 'bull' | 'bear' | null
  entry: number | null
  entry_ts: string | null
  stop: number | null
  target: number | null
  contracts: number | null
  risk_of_limit: number | null
  account: string
  variant: string
  as_of: string
  checklist: CheckRow[]
  research_only: boolean
}

export type ModelCheck = { n: number; range_hit: number | null; regime_accuracy: number | null }

export type Forecast = {
  status?: 'no_model'
  latest?: { date: string; model: string; proba: Record<string, number>; up_bound: number; down_bound: number }
  range?: Record<string, unknown>
  regime_model?: string
  model_check?: ModelCheck
  research_only: boolean
}

export type Side = 'long' | 'short'
export type Stage = 'backtest' | 'forward_test' | 'eval' | 'funded' | 'live'
export type Grade = 'A' | 'B' | 'C' | 'E'

export type Entry = {
  id: number
  opened_at: string
  closed_at: string | null
  symbol: string
  side: Side | null
  entry: number | null
  stop: number | null
  initial_stop: number | null
  target: number | null
  exit: number | null
  size: number | null
  fees: number | null
  account: string | null
  stage: Stage | null
  strategy: string | null
  grade: Grade | null
  tags: string[]
  notes: string | null
  screenshot: string | null
  source: 'signal' | 'manual' | 'imported'
  model_snapshot: Record<string, unknown> | null
  scaled: boolean
  exit_reason: string | null
  needs_confirm: boolean
  'risk_$': number | null
  'pnl_$': number | null
  r: number | null
  win: boolean | null
}

/** What POST /journal accepts. Times have no zone; the API reads them as New York time. */
export type JournalIn = {
  opened_at: string
  symbol: string
  side: Side
  entry?: number
  stop?: number
  target?: number
  size: number
  fees?: number
  account?: string
  stage?: Stage
  strategy?: string
  grade?: Grade
  tags?: string[]
  notes?: string
}

/** null clears a field. */
export type JournalPatch = {
  [K in keyof Omit<JournalIn, 'opened_at' | 'symbol' | 'side' | 'size' | 'tags'>]?: JournalIn[K] | null
} & {
  side?: Side
  size?: number
  tags?: string[]
  closed_at?: string | null
  exit?: number | null
  exit_reason?: string | null
  needs_confirm?: boolean
}

export type Summary = { n: number; win_rate: number | null; mean_r: number | null; sum_r: number }
export type Day = { date: string; n: number; r: number; 'pnl_$': number }

export type JournalStats = {
  stats: {
    by_source: Record<string, Summary>
    skipped: string[]
    by_tag: Record<string, Summary>
    by_grade: Record<string, Summary>
    by_stage: Record<string, Summary>
    worst_days: Day[]
    daily_cap_breaks: { date: string; n: number; r: number; reasons: string[] }[]
  }
  calendar: Day[]
}

export type Layer = 'D-1H' | '1H-5m'
export type Point = { date: string; usd: number }
export type MonteCarlo = { p_pass: number | null; p_breach: number | null; median_trades_to_pass: number | null }

/** One variant of a development (or final) backtest, as reports/backtest_<code>_<layer>.json holds it. */
export type BacktestRecord = {
  code: string
  layer: Layer
  variant: string
  final: boolean
  holdout_from: string
  period: { start: string | null; end: string | null }
  n_setups: number
  skip_counts: Record<string, number>
  expectancy: { n: number; mean: number | null; low: number | null; high: number | null; win_rate: number | null }
  equity: { 'net_$': number; 'max_dd_$': number; max_dd_r: number; profit_factor: number | null; trades_per_month: number }
  monte_carlo: Record<'1%' | '2%', MonteCarlo>
  benchmarks: { 'buy_hold_$'?: number; 'ma_20_50_$'?: number }
  trades?: { session: string; direction: string; r: number | null; 'net_$': number | null; exit_reason: string | null }[]
  curves?: { strategy: Point[]; buy_hold?: Point[]; ma_20_50?: Point[] }
  monthly?: { month: string; n: number; r: number; 'net_$': number }[]
  attempt?: number
}
