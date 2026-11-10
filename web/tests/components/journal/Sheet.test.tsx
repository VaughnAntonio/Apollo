import { fireEvent, render, screen, within } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { Sheet } from '../../../src/components/journal/Sheet'
import { entry } from '../../fixtures'
import { ApiFailure, mockApi } from '../../helpers'

const STATS = {
  stats: {
    by_source: { signal: { n: 4, win_rate: 0.5, mean_r: 0.25, sum_r: 1 }, imported: { n: 51, win_rate: 0.41, mean_r: -0.1, sum_r: -5 } },
    skipped: ['2026-11-03', '2026-11-04'],
    by_tag: {}, by_grade: {}, by_stage: {},
    worst_days: [{ date: '2025-10-20', n: 3, r: -4.5, 'pnl_$': -900 }],
    daily_cap_breaks: [],
  },
  calendar: [
    { date: '2026-11-03', n: 1, r: -1, 'pnl_$': -20 },
    { date: '2026-11-04', n: 1, r: 1.5, 'pnl_$': 30 },
  ],
}
const LIST = [
  entry({ id: 2, opened_at: '2026-11-04T15:00:00Z', r: 1.5 }),
  entry({ id: 1, opened_at: '2026-11-03T14:30:00Z', r: -1, source: 'imported', side: null, entry: null, stop: null,
    initial_stop: null, target: null, exit: null, size: null, scaled: true, 'pnl_$': -20, strategy: 'Fractal' }),
]
const props = { open: true, mode: 'view' as const, selectedId: null, onOpenChange: () => {}, onChanged: () => {} }

it('lists trades newest first with R coloured by sign, and opens the detail', async () => {
  mockApi({ '/journal': LIST, '/journal/stats': STATS })
  render(<Sheet {...props} />)
  const list = await screen.findByRole('list', { name: 'Trades' })
  const rows = within(list).getAllByRole('button')
  expect(rows[0].textContent).toContain('+1.50R')
  const r1 = within(rows[1]).getByText('−1.00R')
  expect(r1.className).toContain('text-down')
  fireEvent.click(rows[1])
  expect(screen.getAllByText('Not recorded').length).toBeGreaterThan(0)
  expect(screen.getByText('Scaled')).toBeTruthy()
  expect(screen.getByText('Fees').nextElementSibling?.textContent).toBe('Not recorded') // the case study never recorded fees
  expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull() // imported rows are read-only
})

it('stats strip and calendar render from /journal/stats, and a day filters the list', async () => {
  mockApi({ '/journal': LIST, '/journal/stats': STATS })
  render(<Sheet {...props} />)
  expect((await screen.findByText('Skipped signals')).parentElement?.textContent).toBe('Skipped signals2')
  expect(screen.getByText('2025-10-20')).toBeTruthy()
  const day = screen.getByRole('button', { name: /^2026-11-03, 1 trade,/ })
  expect(day.className).toContain('bg-down')
  fireEvent.click(day)
  expect(within(screen.getByRole('list', { name: 'Trades' })).getAllByRole('button')).toHaveLength(1)
})

it("shows the API's 422 next to the form and keeps what was typed", async () => {
  mockApi({ '/journal': [], '/journal/stats': STATS, 'POST /journal': new ApiFailure(422, 'size must be a positive whole number') })
  render(<Sheet {...props} mode="new" />)
  fireEvent.change(await screen.findByLabelText('Opened (ET)'), { target: { value: '2026-11-10T10:00' } })
  fireEvent.change(screen.getByLabelText('Entry'), { target: { value: '102' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save entry' }))
  expect(await screen.findByText('size must be a positive whole number')).toBeTruthy()
  expect((screen.getByLabelText('Entry') as HTMLInputElement).value).toBe('102')
})

it('deletes only after a confirm', async () => {
  const f = mockApi({ '/journal': LIST, '/journal/stats': STATS, 'DELETE /journal/2': { deleted: true } })
  const onChanged = vi.fn()
  render(<Sheet {...props} selectedId={2} onChanged={onChanged} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
  expect(screen.getByText("Delete this trade? This can't be undone.")).toBeTruthy()
  expect(f.mock.calls.some(([, i]) => i?.method === 'DELETE')).toBe(false)
  fireEvent.click(screen.getByRole('button', { name: 'Yes, delete' }))
  await vi.waitFor(() => expect(onChanged).toHaveBeenCalled())
  expect(f.mock.calls.some(([u, i]) => i?.method === 'DELETE' && String(u).endsWith('/journal/2'))).toBe(true)
})
