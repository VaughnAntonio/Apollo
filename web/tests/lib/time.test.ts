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
