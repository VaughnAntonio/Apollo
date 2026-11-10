import { act, render } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { Chart } from '../../src/components/Chart'
import { setVisibility } from '../helpers'

// A series that behaves like lightweight-charts: updating with an older time throws.
const state = vi.hoisted(() => ({ last: 0, errors: [] as string[] }))
vi.mock('lightweight-charts', () => {
  const series = {
    setData: vi.fn((d: { time: number }[]) => {
      state.last = d.at(-1)?.time ?? 0
    }),
    update: vi.fn((b: { time: number }) => {
      if (b.time < state.last) {
        state.errors.push(`older ${b.time} < ${state.last}`)
        throw new Error('Cannot update oldest data')
      }
      state.last = b.time
    }),
    applyOptions: vi.fn(),
    createPriceLine: vi.fn(),
    removePriceLine: vi.fn(), attachPrimitive: vi.fn(), detachPrimitive: vi.fn(),
  }
  const chart = {
    addSeries: vi.fn(() => series),
    applyOptions: vi.fn(),
    timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
    subscribeClick: vi.fn(),
    remove: vi.fn(),
  }
  return { createChart: vi.fn(() => chart), createSeriesMarkers: vi.fn(() => ({ setMarkers: vi.fn(), detach: vi.fn() })), CandlestickSeries: {} }
})

const bar = (t: number) => ({ time: t, open: 1, high: 1, low: 1, close: 1, volume: 1 })

afterEach(() => {
  vi.useRealTimers()
  setVisibility('visible')
  state.last = 0
  state.errors = []
})

it('a poll that lands late never draws an older bar after a newer one', async () => {
  vi.useFakeTimers()
  const pending: ((b: unknown) => void)[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn(() => new Promise((res) => pending.push((b) => res(new Response(JSON.stringify(b), { status: 200 }))))),
  )
  render(<Chart symbol="MNQ" tf="5m" />)
  await act(() => vi.advanceTimersByTimeAsync(0))
  pending[0]([bar(100), bar(200), bar(300)])
  await act(() => vi.advanceTimersByTimeAsync(0))
  await act(() => vi.advanceTimersByTimeAsync(60_000)) // poll 1 starts and stays pending
  act(() => setVisibility('hidden'))
  act(() => setVisibility('visible')) // the tab wakes: poll 2
  await act(() => vi.advanceTimersByTimeAsync(0))
  pending[2]([bar(300), bar(400)])
  await act(() => vi.advanceTimersByTimeAsync(0))
  pending[1]([bar(300)]) // poll 1 lands late
  await act(() => vi.advanceTimersByTimeAsync(0))
  await act(() => vi.advanceTimersByTimeAsync(60_000)) // poll 3
  pending[3]([bar(400), bar(500)])
  await act(() => vi.advanceTimersByTimeAsync(0))
  expect(state.errors).toEqual([])
  expect(state.last).toBe(500)
})
