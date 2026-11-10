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

export type JournalPatch = Partial<Omit<JournalIn, 'opened_at' | 'symbol'>> & {
  closed_at?: string
  exit?: number
  exit_reason?: string
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
