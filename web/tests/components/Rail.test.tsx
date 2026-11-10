import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { CheckRow, Entry, Signal } from '../../src/api/types'
import { Rail } from '../../src/components/Rail'
import { ApiFailure, mockApi, setVisibility } from '../helpers'

const row = (step: string, status: CheckRow['status'], detail: string): CheckRow => ({ step, status, detail })
const signal = (over: Partial<Signal> = {}): Signal => ({
  symbol: 'MNQ', status: 'waiting', direction: 'bear', entry: null, entry_ts: null, stop: null, target: null,
  contracts: null, risk_of_limit: null, account: 'APEX 50k', variant: 'plain', as_of: '2026-11-03T16:00:00Z',
  checklist: [], research_only: true, ...over,
})
const trigger = signal({
  status: 'trigger', direction: 'bull', entry: 102, stop: 99.75, target: 105, contracts: 2, risk_of_limit: 0.0036,
  checklist: [row('daily_bias', 'pass', 'Bull C2'), row('5m_trigger', 'pass', '5m CISD, fill 10:55 ET')],
})
const forecast = { model_check: { n: 60, range_hit: 0.883, regime_accuracy: 0.617 }, research_only: true }
const noop = () => {}

it('lists the checklist rows and hides Take trade while waiting', async () => {
  mockApi({ '/signal': signal({ checklist: [row('daily_bias', 'pass', 'Bear C2 at a swing high'), row('5m_trigger', 'wait', 'No 5m trigger')] }), '/forecast': forecast })
  render(<Rail symbol="MNQ" openTrade={null} lastClose={null} onTaken={noop} onChanged={noop} />)
  expect(await screen.findByText('Bear C2 at a swing high')).toBeTruthy()
  expect(screen.getByText('Daily bias')).toBeTruthy()
  expect(screen.getByText('No trade signal')).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Take trade' })).toBeNull()
  expect(await screen.findByText('88.3%')).toBeTruthy()
})

it('Take trade sends the edited fill and size', async () => {
  const f = mockApi({ '/signal': trigger, '/forecast': forecast, 'POST /journal/take': { id: 7 } })
  const onTaken = vi.fn()
  render(<Rail symbol="MNQ" openTrade={null} lastClose={null} onTaken={onTaken} onChanged={noop} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Take trade' }))
  fireEvent.change(screen.getByLabelText('Fill'), { target: { value: '102.25' } })
  fireEvent.change(screen.getByLabelText('Contracts'), { target: { value: '1' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save trade' }))
  await vi.waitFor(() => expect(onTaken).toHaveBeenCalledWith(7))
  const take = f.mock.calls.find(([u]) => String(u).includes('/journal/take'))!
  expect(String(take[0])).toContain('symbol=MNQ')
  expect(JSON.parse(String(take[1]!.body))).toEqual({ fill: 102.25, size: 1 })
})

it("shows the API's reason when the signal expired", async () => {
  mockApi({ '/signal': trigger, '/forecast': forecast, 'POST /journal/take': new ApiFailure(422, 'there is no trade signal right now') })
  const onTaken = vi.fn()
  render(<Rail symbol="MNQ" openTrade={null} lastClose={null} onTaken={onTaken} onChanged={noop} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Take trade' }))
  fireEvent.click(screen.getByRole('button', { name: 'Save trade' }))
  expect(await screen.findByText('there is no trade signal right now')).toBeTruthy()
  expect(onTaken).not.toHaveBeenCalled()
})

it("says the model isn't trained for stocks", async () => {
  mockApi({ '/signal': signal({ status: 'no_model' }), '/forecast': { status: 'no_model', research_only: true } })
  render(<Rail symbol="NVDA" openTrade={null} lastClose={null} onTaken={noop} onChanged={noop} />)
  expect(await screen.findByText('Model not trained for this symbol')).toBeTruthy()
})

const open: Entry = {
  id: 7, opened_at: '2026-11-03T15:55:00Z', closed_at: null, symbol: 'MNQ', side: 'long', entry: 102, stop: 99.75,
  initial_stop: 99.75, target: 105, exit: null, size: 2, fees: 2.48, account: 'APEX 50k', stage: 'live',
  strategy: null, grade: null, tags: [], notes: null, screenshot: null, source: 'signal', model_snapshot: null,
  scaled: false, exit_reason: null, needs_confirm: false, 'risk_$': 9, 'pnl_$': null, r: null, win: null,
}

it('shows the open trade with live R and closes it by hand', async () => {
  const f = mockApi({ '/signal': trigger, '/forecast': forecast, 'POST /journal/7/close': { ...open, exit: 104 } })
  const onChanged = vi.fn()
  render(<Rail symbol="MNQ" openTrade={open} lastClose={104.25} onTaken={noop} onChanged={onChanged} />)
  expect(await screen.findByText('+1.00R')).toBeTruthy()
  expect(screen.queryByRole('button', { name: 'Take trade' })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Close trade' }))
  fireEvent.change(screen.getByLabelText('Exit'), { target: { value: '104' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save exit' }))
  await vi.waitFor(() => expect(onChanged).toHaveBeenCalled())
  const close = f.mock.calls.find(([u]) => String(u).includes('/close'))!
  expect(JSON.parse(String(close[1]!.body))).toEqual({ exit: 104, reason: 'manual' })
})

it('confirming an auto-close keeps its reason', async () => {
  const auto = { ...open, exit: 99.75, exit_reason: 'stop_auto', needs_confirm: true, closed_at: '2026-11-03T16:30:00Z' }
  const f = mockApi({ '/signal': trigger, '/forecast': forecast, 'POST /journal/7/close': auto })
  render(<Rail symbol="MNQ" openTrade={auto} lastClose={99} onTaken={noop} onChanged={noop} />)
  expect(await screen.findByText('−1.00R')).toBeTruthy() // R at the exit, not at the last price
  expect(screen.getByText('R at exit')).toBeTruthy()
  fireEvent.click(await screen.findByRole('button', { name: 'Confirm exit' }))
  await vi.waitFor(() => expect(f.mock.calls.some(([u]) => String(u).includes('/close'))).toBe(true))
  const close = f.mock.calls.find(([u]) => String(u).includes('/close'))!
  expect(JSON.parse(String(close[1]!.body))).toEqual({ exit: 99.75, at: '2026-11-03T16:30:00Z', reason: 'stop_auto' })
})

it('a blank fill keeps the signal price, and text in Fill or Contracts is refused before any request', async () => {
  const f = mockApi({ '/signal': trigger, '/forecast': forecast, 'POST /journal/take': { id: 7 } })
  render(<Rail symbol="MNQ" openTrade={null} lastClose={null} onTaken={noop} onChanged={noop} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Take trade' }))
  fireEvent.change(screen.getByLabelText('Fill'), { target: { value: 'abc' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save trade' }))
  expect(await screen.findByText('Fill must be a number')).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Fill'), { target: { value: '' } })
  fireEvent.change(screen.getByLabelText('Contracts'), { target: { value: '0' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save trade' }))
  expect(await screen.findByText('Contracts must be a whole number above 0')).toBeTruthy()
  expect(f.mock.calls.some(([u]) => String(u).includes('/journal/take'))).toBe(false)
  fireEvent.change(screen.getByLabelText('Contracts'), { target: { value: '' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save trade' }))
  await vi.waitFor(() => expect(f.mock.calls.some(([u]) => String(u).includes('/journal/take'))).toBe(true))
  const take = f.mock.calls.find(([u]) => String(u).includes('/journal/take'))!
  expect(JSON.parse(String(take[1]!.body))).toEqual({}) // the API uses the signal's own fill and size
})

it('a blank exit is refused instead of closing at 0', async () => {
  const f = mockApi({ '/signal': trigger, '/forecast': forecast })
  render(<Rail symbol="MNQ" openTrade={open} lastClose={null} onTaken={noop} onChanged={noop} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Close trade' }))
  fireEvent.click(screen.getByRole('button', { name: 'Save exit' }))
  expect(await screen.findByText('Exit must be a number')).toBeTruthy()
  expect(f.mock.calls.some(([u]) => String(u).includes('/close'))).toBe(false)
})

it('says the API is down under a stale signal instead of hiding it', async () => {
  mockApi({ '/signal': trigger, '/forecast': forecast })
  render(<Rail symbol="MNQ" openTrade={null} lastClose={null} onTaken={noop} onChanged={noop} />)
  expect(await screen.findByRole('button', { name: 'Take trade' })).toBeTruthy()
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
  setVisibility('hidden')
  setVisibility('visible') // the next poll fails
  expect((await screen.findAllByText('Start the API: python -m apollo.api.main')).length).toBeGreaterThan(0)
  expect(screen.getByText('Bull C2')).toBeTruthy() // the last data stays, marked as stale
  expect(screen.queryByRole('button', { name: 'Take trade' })).toBeNull() // no taking a trade off stale data
})
