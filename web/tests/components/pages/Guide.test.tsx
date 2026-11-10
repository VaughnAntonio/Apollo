import { fireEvent, render, screen, within } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { Explain } from '../../../src/api/types'
import { Guide, fractalStep } from '../../../src/components/pages/Guide'
import { ApiFailure, mockApi } from '../../helpers'

vi.mock('../../../src/components/viz/ExplainChart', () => ({ ExplainChart: () => <div>chart</div> }))

const bar = (time: number) => ({ time, open: 1, high: 2, low: 0, close: 1, volume: 1 })
export const EXPLAIN: Explain = {
  date: '2026-04-22',
  symbol: 'MNQ',
  fractal: {
    htf: [bar(100), bar(200), bar(300)],
    ltf: [bar(300), bar(310), bar(320)],
    setup: {
      direction: 'bear', c1_ts: 100, c2_ts: 200, c2_close: 300, c1_high: 26000, c1_low: 25500, poi_level: 26050,
      poi_kind: 'fvg', cisd_ts: 310, cisd_level: 25900, protected: 26080, entry_ts: 320, entry: 25890, stop: 26085, target: 25500,
    },
  },
  regime: { features: { kurt: 3.2, crest: 4.1, rms: 0.002 }, proba: { trend_up: 0.2, trend_down: 0.4, chop: 0.1, normal: 0.3 }, model: 'logit', label: 'normal' },
  range: {
    open: 25900, up_bound: 300, down_bound: 400, high: 26000, low: 25600, hit_both: true,
    coverage_60: Array.from({ length: 60 }, (_, i) => ({ date: `d${i}`, hit_both: i !== 3 && i !== 40 })),
  },
}

const onChart = () => within(screen.getByRole('list', { name: 'On the chart' })).getAllByRole('listitem').map((li) => li.textContent)

it('the Fractal slider reveals one more element per step', async () => {
  mockApi({ '/explain': EXPLAIN })
  render(<Guide onTour={() => {}} />)
  const slider = await screen.findByRole('slider', { name: 'Fractal Model step' })
  expect(onChart()).toEqual([expect.stringMatching(/^C1/)])
  fireEvent.change(slider, { target: { value: '3' } })
  expect(onChart().some((t) => t?.startsWith('CISD'))).toBe(true)
  expect(onChart().some((t) => t?.startsWith('Entry'))).toBe(false)
  fireEvent.change(slider, { target: { value: '4' } })
  expect(onChart()).toEqual(expect.arrayContaining([expect.stringMatching(/^Entry/), expect.stringMatching(/^Stop/), expect.stringMatching(/^Target/)]))
})

it('the HTF steps draw on the daily bars and the LTF steps on the hourly ones', () => {
  const s = EXPLAIN.fractal.setup
  expect(fractalStep(s, 2).tf).toBe('htf')
  expect(fractalStep(s, 2).markers.map((m) => m.text)).toEqual(['C1', 'C2', 'C3'])
  expect(fractalStep(s, 2).lines.map((l) => l.title)).toEqual(['POI'])
  expect(fractalStep(s, 3).tf).toBe('ltf')
  expect(fractalStep(s, 4).lines.map((l) => l.title)).toEqual(['CISD', 'Protected high', 'Entry', 'Stop', 'Target'])
})

it('the regime section ends on what actually happened', async () => {
  mockApi({ '/explain': EXPLAIN })
  render(<Guide onTour={() => {}} />)
  const slider = await screen.findByRole('slider', { name: 'Regime detector step' })
  expect(screen.getByText('kurt')).toBeTruthy()
  fireEvent.change(slider, { target: { value: '2' } })
  expect(screen.getByText(/The model's favourite was trend down \(40%\)\. The day was normal\./)).toBeTruthy()
})

it('the range section lists misses in the last 60 sessions', async () => {
  mockApi({ '/explain': EXPLAIN })
  render(<Guide onTour={() => {}} />)
  const slider = await screen.findByRole('slider', { name: 'Range forecaster step' })
  fireEvent.change(slider, { target: { value: '3' } })
  expect(screen.getByText('2 misses in 60 sessions')).toBeTruthy()
})

it('the tour button still works when the worked example is missing', async () => {
  mockApi({ '/explain': new ApiFailure(404, 'nope') })
  const onTour = vi.fn()
  render(<Guide onTour={onTour} />)
  expect(await screen.findByText('The worked example is not available yet')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Take the tour' }))
  expect(onTour).toHaveBeenCalled()
})
