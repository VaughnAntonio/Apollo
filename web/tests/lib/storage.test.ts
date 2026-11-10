import { afterEach, expect, it, vi } from 'vitest'
import { get, set } from '../../src/lib/storage'

afterEach(() => localStorage.clear())

it('reads back what it stored', () => {
  set('apollo.symbol', 'MES')
  expect(get('apollo.symbol', 'MNQ')).toBe('MES')
})

it('falls back when localStorage throws', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  expect(get('apollo.symbol', 'MNQ')).toBe('MNQ')
  expect(() => set('apollo.symbol', 'MES')).not.toThrow()
})
