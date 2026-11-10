import type { Entry } from '../src/api/types'

export function entry(over: Partial<Entry> = {}): Entry {
  return {
    id: 1, opened_at: '2026-11-03T15:55:00Z', closed_at: '2026-11-03T17:00:00Z', symbol: 'MNQ', side: 'long',
    entry: 102, stop: 99.75, initial_stop: 99.75, target: 105, exit: 104, size: 2, fees: 2.48, account: 'APEX 50k',
    stage: 'live', strategy: 'Fractal Model (Apollo signal)', grade: null, tags: [], notes: null, screenshot: null,
    source: 'signal', model_snapshot: null, scaled: false, exit_reason: 'manual', needs_confirm: false,
    'risk_$': 9, 'pnl_$': 5.52, r: 0.61, win: true, ...over,
  }
}
