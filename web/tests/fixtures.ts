import type { BacktestRecord, Entry } from '../src/api/types'

export function entry(over: Partial<Entry> = {}): Entry {
  return {
    id: 1, opened_at: '2026-11-03T15:55:00Z', closed_at: '2026-11-03T17:00:00Z', symbol: 'MNQ', side: 'long',
    entry: 102, stop: 99.75, initial_stop: 99.75, target: 105, exit: 104, size: 2, fees: 2.48, account: 'APEX 50k',
    stage: 'live', strategy: 'Fractal Model (Apollo signal)', grade: null, tags: [], notes: null, screenshot: null,
    source: 'signal', model_snapshot: null, scaled: false, exit_reason: 'manual', needs_confirm: false,
    'risk_$': 9, 'pnl_$': 5.52, r: 0.61, win: true, ...over,
  }
}

export function rec(variant: string, mean: number, over: Partial<BacktestRecord> = {}): BacktestRecord {
  return {
    code: 'MNQ', layer: 'D-1H', variant, final: false, holdout_from: '2026-08-06',
    period: { start: '2024-11-13', end: '2026-07-27' }, n_setups: 72, skip_counts: { traded: 14 },
    expectancy: { n: 14, mean, low: -0.74, high: 0.07, win_rate: 0.21 },
    equity: { 'net_$': -2116.08, 'max_dd_$': -2116.08, max_dd_r: -5.06, profit_factor: 0.37, trades_per_month: 0.8 },
    monte_carlo: {
      '1%': { p_pass: 0.002, p_breach: 1, median_trades_to_pass: 16 },
      '2%': { p_pass: 0.029, p_breach: 1, median_trades_to_pass: 6 },
    },
    benchmarks: { 'buy_hold_$': 14001, 'ma_20_50_$': 11901 },
    trades: [
      { session: '2025-01-06', direction: 'bull', r: -1.04, 'net_$': -522.4, exit_reason: 'stop' },
      { session: '2025-02-03', direction: 'bear', r: 2.1, 'net_$': 400, exit_reason: 'target' },
    ],
    curves: {
      strategy: [{ date: '2025-01-06', usd: -522.4 }, { date: '2025-02-03', usd: -122.4 }],
      buy_hold: [{ date: '2025-01-06', usd: 10 }, { date: '2025-02-03', usd: 50 }],
      ma_20_50: [{ date: '2025-01-06', usd: 0 }, { date: '2025-02-03', usd: 20 }],
    },
    monthly: [
      { month: '2025-01', n: 1, r: -1.04, 'net_$': -522.4 },
      { month: '2025-02', n: 1, r: 2.1, 'net_$': 400 },
    ],
    attempt: 38,
    ...over,
  }
}
