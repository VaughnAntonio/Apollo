import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { Chart } from '../../src/components/Chart'
import { mockApi } from '../helpers'

vi.mock('lightweight-charts', () => {
  const series = { setData: vi.fn(), update: vi.fn(), applyOptions: vi.fn(), createPriceLine: vi.fn(), removePriceLine: vi.fn(), attachPrimitive: vi.fn(), detachPrimitive: vi.fn() }
  const chart = {
    addSeries: vi.fn(() => series),
    applyOptions: vi.fn(),
    timeScale: vi.fn(() => ({ fitContent: vi.fn(), applyOptions: vi.fn() })),
    subscribeClick: vi.fn(),
    unsubscribeClick: vi.fn(),
    remove: vi.fn(),
  }
  return {
    createChart: vi.fn(() => chart),
    createSeriesMarkers: vi.fn(() => ({ setMarkers: vi.fn(), detach: vi.fn() })),
    CandlestickSeries: {},
    LineStyle: { Solid: 0, Dashed: 2 },
  }
})

it('shows an empty state when there are no bars', async () => {
  mockApi({ '/bars': [] })
  render(<Chart symbol="NVDA" tf="1m" />)
  expect(await screen.findByText('No 1m bars for NVDA yet')).toBeTruthy()
})

it('shows how to start the API when it is down', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
  render(<Chart symbol="MNQ" tf="5m" />)
  expect(await screen.findByText('Start the API: python -m apollo.api.main')).toBeTruthy()
})

it('marks the chart as stale when a later poll fails', async () => {
  mockApi({ '/bars': [{ time: 100, open: 1, high: 1, low: 1, close: 1, volume: 1 }] })
  render(<Chart symbol="MNQ" tf="5m" />)
  await vi.waitFor(() => expect(screen.queryByLabelText('Loading')).toBeNull())
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
  Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
  document.dispatchEvent(new Event('visibilitychange'))
  expect(await screen.findByText('Start the API: python -m apollo.api.main')).toBeTruthy()
})
