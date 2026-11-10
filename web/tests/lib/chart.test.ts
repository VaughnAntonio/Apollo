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
