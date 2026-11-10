import type { Page, Route } from '@playwright/test'

const API = 'http://127.0.0.1:8000'
const t0 = Date.UTC(2026, 10, 9, 14, 30) / 1000
const bars = Array.from({ length: 60 }, (_, i) => {
  const c = 27000 + Math.sin(i / 5) * 40 + i
  return { time: t0 + i * 300, open: c - 3, high: c + 6, low: c - 6, close: c, volume: 100 }
})
const trigger = {
  symbol: 'MNQ', status: 'trigger', direction: 'bull', entry: 27050, entry_ts: '2026-11-09T15:55:00Z', stop: 27030,
  target: 27090, contracts: 2, risk_of_limit: 0.04, account: 'APEX 50k', variant: 'plain', as_of: '2026-11-09T16:00:00Z',
  research_only: true,
  checklist: [
    { step: 'daily_bias', status: 'pass', detail: 'Bull C2 at a swing low' },
    { step: '5m_trigger', status: 'pass', detail: '5m CISD, fill 10:55 ET' },
  ],
}
const symbols = [
  { code: 'MNQ', name: 'Micro E-mini Nasdaq-100', kind: 'future', model_enabled: true },
  { code: 'MES', name: 'Micro E-mini S&P 500', kind: 'future', model_enabled: true },
  { code: 'NVDA', name: 'NVIDIA', kind: 'stock', model_enabled: false },
]
const stats = {
  stats: { by_source: {}, skipped: [], by_tag: {}, by_grade: {}, by_stage: {}, worst_days: [], daily_cap_breaks: [] },
  calendar: [],
}

/** Answer every API call from fixtures. Taking a trade adds an open entry to the journal. */
export async function mockApi(page: Page) {
  const journal: object[] = []
  await page.route(`${API}/**`, async (route: Route) => {
    const url = new URL(route.request().url())
    const method = route.request().method()
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    if (url.pathname === '/symbols') return json(symbols)
    if (url.pathname === '/bars') return json(url.searchParams.get('start') ? [] : bars)
    if (url.pathname === '/signal') return json(journal.length ? { ...trigger, status: 'waiting' } : trigger)
    if (url.pathname === '/forecast') return json({ model_check: { n: 60, range_hit: 0.9, regime_accuracy: 0.4 }, research_only: true })
    if (url.pathname === '/journal/stats') return json(stats)
    if (url.pathname === '/journal/auto-close') return json({ closed: [] })
    if (url.pathname === '/journal/take' && method === 'POST') {
      journal.push({
        id: 9, opened_at: trigger.entry_ts, closed_at: null, symbol: 'MNQ', side: 'long', entry: 27050, stop: 27030,
        initial_stop: 27030, target: 27090, exit: null, size: 2, fees: 2.48, account: 'APEX 50k', stage: 'live',
        strategy: 'Fractal Model (Apollo signal)', grade: null, tags: [], notes: null, screenshot: null, source: 'signal',
        model_snapshot: null, scaled: false, exit_reason: null, needs_confirm: false, 'risk_$': 80, 'pnl_$': null, r: null, win: null,
      })
      return json({ id: 9 })
    }
    if (url.pathname === '/journal') return json(journal)
    return json({ detail: 'not mocked' }, 404)
  })
}
