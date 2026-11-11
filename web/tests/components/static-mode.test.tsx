import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from '../../src/App'
import { entry } from '../fixtures'
import { mockFiles } from '../helpers'

vi.mock('../../src/components/Chart', () => ({ Chart: () => <div>chart</div> }))

const TRIGGER = {
  symbol: 'MNQ', status: 'trigger', direction: 'bull', entry: 102, entry_ts: null, stop: 99.75, target: 105,
  contracts: 2, risk_of_limit: 0.004, account: 'APEX 50k', variant: 'plain', as_of: '2026-11-10T16:00:00Z',
  checklist: [], research_only: true,
}

beforeEach(() => {
  vi.stubEnv('VITE_MODE', 'static')
  location.hash = ''
  mockFiles({
    '/snapshot/meta.json': { generated: '2026-11-10T23:00:00+00:00', date: '2026-11-10', symbols_ok: ['MNQ'], missing: [] },
    '/snapshot/symbols.json': [{ code: 'MNQ', name: 'Micro Nasdaq', kind: 'future', model_enabled: true }],
    '/snapshot/signal/MNQ.json': TRIGGER,
    '/snapshot/journal.json': [entry({ id: 7, source: 'imported', scaled: true, side: null })],
    '/snapshot/journal_stats.json': { stats: { by_source: {}, skipped: [], by_tag: {}, by_grade: {}, by_stage: {}, worst_days: [], daily_cap_breaks: [] }, calendar: [] },
  })
})
afterEach(() => vi.unstubAllEnvs())

it('static mode hides every write control and shows the snapshot date', async () => {
  render(<App />)
  expect(await screen.findByText('Build 10 Nov, 18:00 ET')).toBeTruthy()
  expect(screen.queryByText('Delayed 10m')).toBeNull()
  await screen.findByText('Long')
  expect(screen.queryByText('Take trade')).toBeNull()
  fireEvent.click(screen.getByLabelText('Open menu'))
  expect(screen.queryByText('New journal entry')).toBeNull()
  fireEvent.click(screen.getByText('Journal'))
  await waitFor(() => expect(screen.getAllByText('Journal').length).toBeGreaterThan(0))
  expect(screen.queryByRole('button', { name: 'New' })).toBeNull()
  expect(screen.queryByText('Edit')).toBeNull()
  expect(screen.queryByText(/Drop a PNG/)).toBeNull()
})
