import { expect, it } from 'vitest'
import type { Bar } from '../../src/api/types'
import { candleColours, mergeBars } from '../../src/lib/chart'

const bar = (time: number, close: number): Bar => ({ time, open: close, high: close, low: close, close, volume: 1 })

it('mergeBars de-duplicates overlap, keeps order and lets the fresh bar win', () => {
  const a = [bar(1, 10), bar(2, 11), bar(3, 12)]
  const b = [bar(3, 13), bar(4, 14)]
  expect(mergeBars(a, b).map((x) => [x.time, x.close])).toEqual([[1, 10], [2, 11], [3, 13], [4, 14]])
  expect(mergeBars([bar(5, 1)], [bar(4, 2)]).map((x) => x.time)).toEqual([4, 5])
  expect(mergeBars([], [])).toEqual([])
})

it('candle colours come from the tokens', () => {
  document.documentElement.style.setProperty('--brand', '#3d5a4a')
  document.documentElement.style.setProperty('--down', '#a32d2d')
  expect(candleColours(getComputedStyle(document.documentElement))).toMatchObject({
    upColor: '#3d5a4a',
    downColor: '#a32d2d',
    wickUpColor: '#3d5a4a',
    wickDownColor: '#a32d2d',
    borderVisible: false,
  })
})

import { dayDots, snapTo, tradeLines, tradeMarkers } from '../../src/lib/chart'
import { entry } from '../fixtures'

const pal = { ink: '#262933', brand: '#3d5a4a', down: '#a32d2d' }
const t = (iso: string) => Date.parse(iso) / 1000

it('draws entry, dashed stop and dashed target for an open trade', () => {
  const l = tradeLines(entry({ entry: 102, stop: 99.75, target: 105, exit: null }), pal)
  expect(l.map((x) => [x.title, x.price, x.lineStyle])).toEqual([['Entry', 102, 0], ['Stop', 99.75, 2], ['Target', 105, 2]])
  expect(l[0].color).toBe(pal.ink)
  expect(l[1].color).toBe(pal.down)
  expect(l[2].color).toBe(pal.brand)
  expect(tradeLines(entry({ exit: 104 }), pal)).toEqual([])
  expect(tradeLines(entry({ target: null, exit: null }), pal).map((x) => x.title)).toEqual(['Entry', 'Stop'])
})

it('keeps the lines while an auto-close waits for a confirm', () => {
  expect(tradeLines(entry({ exit: 99.75, needs_confirm: true }), pal)).toHaveLength(3)
})

it('markers only on intraday views, for this symbol, never for imported rows', () => {
  const es = [entry({ id: 1 }), entry({ id: 2, symbol: 'MES' }), entry({ id: 3, source: 'imported' })]
  const m = tradeMarkers(es, 'MNQ', '5m', pal)
  expect(m.map((x) => [x.id, x.shape])).toEqual([[1, 'arrowUp'], [1, 'circle']])
  expect(m[0].time).toBe(t('2026-11-03T15:55:00Z'))
  expect(tradeMarkers(es, 'MNQ', '1d', pal)).toEqual([])
  expect(tradeMarkers([entry({ side: 'short', closed_at: null, exit: null })], 'MNQ', '1m', pal).map((x) => x.shape)).toEqual(['arrowDown'])
})

it('day dots are coloured by the day R, link to the first trade, and show only on the daily chart', () => {
  const es = [
    entry({ id: 1, opened_at: '2026-11-03T15:00:00Z', r: -1 }),
    entry({ id: 2, opened_at: '2026-11-04T15:00:00Z', r: 0.5 }),
    entry({ id: 3, opened_at: '2026-11-04T18:00:00Z', r: -0.5 }),
    entry({ id: 4, opened_at: '2026-11-05T15:00:00Z', r: null, exit: null }),
    entry({ id: 5, opened_at: '2026-11-05T15:00:00Z', symbol: 'MES', r: 2 }),
  ]
  const d = dayDots(es, 'MNQ', '1d', pal)
  expect(d.map((x) => [x.id, x.color])).toEqual([[1, pal.down], [2, pal.brand]])
  expect(d[0].time).toBe(t('2026-11-03T17:00:00Z')) // noon ET on the trade's date
  expect(dayDots(es, 'MNQ', '5m', pal)).toEqual([])
})

it('snapTo moves a time onto the bar that contains it', () => {
  expect(snapTo([100, 200, 300], 250)).toBe(200)
  expect(snapTo([100, 200, 300], 300)).toBe(300)
  expect(snapTo([100, 200, 300], 50)).toBeNull()
  expect(snapTo([], 50)).toBeNull()
})
