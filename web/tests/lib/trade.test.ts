import { expect, it } from 'vitest'
import { fmtPct, fmtPrice, fmtR, openR } from '../../src/lib/trade'

it('openR is measured against the opening stop and signed by side', () => {
  expect(openR({ side: 'long', entry: 100, initial_stop: 98 }, 103)).toBe(1.5)
  expect(openR({ side: 'short', entry: 100, initial_stop: 102 }, 103)).toBe(-1.5)
  expect(openR({ side: 'long', entry: null, initial_stop: 98 }, 103)).toBeNull()
  expect(openR({ side: 'long', entry: 100, initial_stop: 100 }, 103)).toBeNull()
})

it('formats R with a real minus sign, prices with separators, and nulls as Not recorded', () => {
  expect(fmtR(-0.5)).toBe('−0.50R')
  expect(fmtR(1.25)).toBe('+1.25R')
  expect(fmtR(null)).toBe('Not recorded')
  expect(fmtPrice(29987)).toBe('29,987.00')
  expect(fmtPrice(null)).toBe('Not recorded')
  expect(fmtPct(0.3842)).toBe('38.4%')
})
