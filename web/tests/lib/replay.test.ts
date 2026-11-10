import { expect, it } from 'vitest'
import type { Bar } from '../../src/api/types'
import { closedBars } from '../../src/lib/replay'

const bar = (time: number, close_time?: number): Bar => ({ time, close_time, open: 1, high: 2, low: 0, close: 1, volume: 1 })

it('reveals a candle only at its close and ignores candles with unknown close times', () => {
  const bars = [bar(0, 60), bar(60, 120), bar(120)]
  expect(closedBars(bars, 59)).toEqual([])
  expect(closedBars(bars, 60)).toEqual(bars.slice(0, 1))
  expect(closedBars(bars, 200)).toEqual(bars.slice(0, 2))
})
