import type { Bar } from '../api/types'

export type Tf = '1d' | '4h' | '1h' | '15m' | '5m' | '1m'
export const TIMEFRAMES: { tf: Tf; label: string }[] = [
  { tf: '1d', label: 'D' },
  { tf: '4h', label: '4H' },
  { tf: '1h', label: '1H' },
  { tf: '15m', label: '15m' },
  { tf: '5m', label: '5m' },
  { tf: '1m', label: '1m' },
]

/** Sorted and unique by time; a fresh bar replaces the old one with the same time. */
export function mergeBars(old: Bar[], fresh: Bar[]): Bar[] {
  const byTime = new Map<number, Bar>()
  for (const b of old) byTime.set(b.time, b)
  for (const b of fresh) byTime.set(b.time, b)
  return [...byTime.values()].sort((a, b) => a.time - b.time)
}

export const token = (css: CSSStyleDeclaration, name: string) => css.getPropertyValue(`--${name}`).trim()

export function candleColours(css: CSSStyleDeclaration) {
  const up = token(css, 'brand')
  const down = token(css, 'down')
  return { upColor: up, downColor: down, wickUpColor: up, wickDownColor: down, borderVisible: false }
}
