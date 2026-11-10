import { expect, it } from 'vitest'
import { nyDate, nyDateTime, nyTime, toNaiveIso } from '../../src/lib/time'

const sec = (...a: [number, number, number, number, number]) => Date.UTC(...a) / 1000

it('shows ET in the US/EU DST gap', () => {
  expect(nyTime(sec(2026, 2, 10, 13, 30))).toBe('09:30') // US on EDT, Madrid still on CET
  expect(nyTime(sec(2026, 9, 28, 13, 30))).toBe('09:30') // Madrid back on CET, US still on EDT
  expect(nyTime(sec(2026, 10, 3, 14, 30))).toBe('09:30') // both on standard time
})

it('dates are ET dates', () => {
  expect(nyDate(sec(2026, 10, 3, 3, 0))).toBe('2026-11-02')
  expect(nyDateTime('2026-11-03T15:00:00Z')).toBe('2026-11-03 10:00')
})

it('toNaiveIso keeps the wall-clock time and adds no zone', () => {
  expect(toNaiveIso('2026-11-10T10:00')).toBe('2026-11-10T10:00:00')
  expect(toNaiveIso('2026-11-10T10:00:30')).toBe('2026-11-10T10:00:30')
})

import { tickLabel } from '../../src/lib/time'

it('axis ticks show the year, the month, the day or the time by tick type', () => {
  const s = Date.UTC(2026, 0, 1, 15, 0) / 1000
  expect(tickLabel(s, 0)).toBe('2026')
  expect(tickLabel(s, 1)).toBe('Jan')
  expect(tickLabel(s, 2)).toBe('1 Jan')
  expect(tickLabel(s, 3)).toBe('10:00')
})

import { crosshairLabel } from '../../src/lib/time'

it('the daily crosshair shows the session date, not the 18:00 ET open of the evening before', () => {
  const openPrevEvening = Date.UTC(2024, 9, 7, 22, 0) / 1000 // 18:00 ET on 7 Oct opens the 8 Oct session
  expect(crosshairLabel(openPrevEvening, '1d')).toBe('2024-10-08')
  expect(crosshairLabel(Date.UTC(2024, 9, 8, 4, 0) / 1000, '1d')).toBe('2024-10-08') // a stock bar at midnight ET
  expect(crosshairLabel(openPrevEvening, '1h')).toBe('2024-10-07 18:00')
})
