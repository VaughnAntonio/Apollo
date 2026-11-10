import type { Bar, Entry } from '../api/types'
import { nyDate, toSec } from './time'

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

export type Palette = { ink: string; brand: string; down: string }
export const palette = (css: CSSStyleDeclaration): Palette => ({
  ink: token(css, 'ink'),
  brand: token(css, 'brand'),
  down: token(css, 'down'),
})

/** 0 is solid and 2 is dashed, as lightweight-charts' LineStyle numbers them. */
export type PriceLineSpec = { price: number; color: string; lineStyle: 0 | 2; title: string }
export type MarkerSpec = {
  time: number
  position: 'aboveBar' | 'belowBar'
  shape: 'arrowUp' | 'arrowDown' | 'circle'
  color: string
  id: number
}

/** Entry, stop and target lines while a trade is on the book (open, or auto-closed and unconfirmed). */
export function tradeLines(e: Entry, pal: Palette): PriceLineSpec[] {
  if (e.exit !== null && !e.needs_confirm) return []
  const lines: PriceLineSpec[] = []
  if (e.entry !== null) lines.push({ price: e.entry, color: pal.ink, lineStyle: 0, title: 'Entry' })
  if (e.stop !== null) lines.push({ price: e.stop, color: pal.down, lineStyle: 2, title: 'Stop' })
  if (e.target !== null) lines.push({ price: e.target, color: pal.brand, lineStyle: 2, title: 'Target' })
  return lines
}

/** Entry arrows and exit circles at their real times, on intraday charts only. */
export function tradeMarkers(entries: Entry[], symbol: string, tf: Tf, pal: Palette): MarkerSpec[] {
  if (tf === '1d') return []
  const out: MarkerSpec[] = []
  for (const e of entries) {
    if (e.symbol !== symbol || e.source === 'imported') continue // imported rows have no time of day
    const long = e.side !== 'short'
    out.push({
      time: toSec(e.opened_at),
      position: long ? 'belowBar' : 'aboveBar',
      shape: long ? 'arrowUp' : 'arrowDown',
      color: long ? pal.brand : pal.down,
      id: e.id,
    })
    if (e.closed_at && e.exit !== null) {
      out.push({
        time: toSec(e.closed_at),
        position: long ? 'aboveBar' : 'belowBar',
        shape: 'circle',
        color: (e.r ?? 0) >= 0 ? pal.brand : pal.down,
        id: e.id,
      })
    }
  }
  return out.sort((a, b) => a.time - b.time)
}

/** One dot per journal day on the daily chart: brand if the day's R is at least 0. Links to the day's first trade. */
export function dayDots(entries: Entry[], symbol: string, tf: Tf, pal: Palette): MarkerSpec[] {
  if (tf !== '1d') return []
  const days = new Map<string, { r: number; id: number; first: number }>()
  for (const e of entries) {
    if (e.symbol !== symbol || e.r === null) continue
    const at = toSec(e.opened_at)
    const day = nyDate(at)
    const d = days.get(day)
    if (!d) days.set(day, { r: e.r, id: e.id, first: at })
    else {
      d.r += e.r
      if (at < d.first) Object.assign(d, { id: e.id, first: at })
    }
  }
  return [...days.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, d]) => ({
      time: noonNy(day),
      position: 'belowBar' as const,
      shape: 'circle' as const,
      color: d.r >= 0 ? pal.brand : pal.down,
      id: d.id,
    }))
}

/** Noon ET on a date, in UTC seconds; the daily bar for that session contains it. */
function noonNy(day: string): number {
  const utcNoon = Date.parse(`${day}T12:00:00Z`) / 1000
  const nyHour = Number(new Intl.DateTimeFormat('en-GB', { timeZone: 'America/New_York', hour: '2-digit', hourCycle: 'h23' }).format(utcNoon * 1000))
  return utcNoon + (12 - nyHour) * 3600
}

/** The open time of the bar containing `t`: markers must sit on a bar the series has. */
export function snapTo(times: number[], t: number): number | null {
  let lo = 0
  let hi = times.length - 1
  let best: number | null = null
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (times[mid] <= t) {
      best = times[mid]
      lo = mid + 1
    } else hi = mid - 1
  }
  return best
}
