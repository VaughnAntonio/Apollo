import { get, set } from './storage'

// Chart drawings: trend lines, rays, horizontal and vertical lines, rectangles and Fibonacci
// retracements. Ends are stored as (UTC seconds, price), so a drawing stays put when the
// timeframe changes; between bars, a time maps to a fractional bar index.

export type DrawKind = 'trend' | 'ray' | 'hline' | 'vline' | 'rect' | 'fib'
export type Tool = 'cursor' | DrawKind
export type Anchor = { time: number; price: number }
export type Drawing = { id: string; kind: DrawKind; a: Anchor; b?: Anchor }
export type Px = { x: number; y: number }
/** A drawing in pane pixels. */
export type PxDrawing = { id: string; kind: DrawKind; a: Px; b?: Px }

const KINDS: DrawKind[] = ['trend', 'ray', 'hline', 'vline', 'rect', 'fib']
/** Kinds placed with two clicks (or one drag); the rest need one click. */
export const TWO_POINT = new Set<DrawKind>(['trend', 'ray', 'rect', 'fib'])
export const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
const NEAR = 4 // pixels: how close the pointer must be to a line
const HANDLE = 6 // pixels: how close to an end to grab it

/** Where `t` falls among the bar times, as a fractional bar index. Outside the bars it carries on at the nearest spacing. */
export function timeToLogical(times: number[], t: number): number | null {
  const n = times.length
  if (!n) return null
  if (n === 1) return 0
  if (t <= times[0]) return (t - times[0]) / (times[1] - times[0])
  if (t >= times[n - 1]) return n - 1 + (t - times[n - 1]) / (times[n - 1] - times[n - 2])
  let lo = 0
  let hi = n - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (times[mid] <= t) lo = mid
    else hi = mid
  }
  return lo + (t - times[lo]) / (times[hi] - times[lo])
}

/** The inverse of timeToLogical. */
export function logicalToTime(times: number[], l: number): number | null {
  const n = times.length
  if (!n) return null
  if (n === 1) return times[0]
  if (l <= 0) return times[0] + l * (times[1] - times[0])
  if (l >= n - 1) return times[n - 1] + (l - (n - 1)) * (times[n - 1] - times[n - 2])
  const i = Math.floor(l)
  return times[i] + (l - i) * (times[i + 1] - times[i])
}

/**
 * The pixel x of a fractional bar index. The chart's own logicalToCoordinate only handles whole
 * indexes (it gives 0 for 297.6), so this goes between the two whole bars around it.
 */
export function logicalToX(coord: (l: number) => number | null, l: number): number | null {
  const i = Math.floor(l)
  const x0 = coord(i)
  if (x0 === null || i === l) return x0
  const x1 = coord(i + 1)
  return x1 === null ? null : x0 + (l - i) * (x1 - x0)
}

/** Fibonacci levels from the first end to the second: 0 sits on the second end, 1 on the first. */
export function fibPrices(a: Anchor, b: Anchor): { level: number; price: number }[] {
  return FIB_LEVELS.map((level) => ({ level, price: b.price + (a.price - b.price) * level }))
}

function toSegment(p: Px, a: Px, b: Px, ray: boolean): number {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len2 = dx * dx + dy * dy
  if (!len2) return Math.hypot(p.x - a.x, p.y - a.y)
  let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2
  t = ray ? Math.max(0, t) : Math.min(1, Math.max(0, t))
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy))
}

function hits(d: PxDrawing, p: Px, size: { width: number; height: number }): boolean {
  const { a, b } = d
  switch (d.kind) {
    case 'hline':
      return Math.abs(p.y - a.y) <= NEAR && p.x >= 0 && p.x <= size.width
    case 'vline':
      return Math.abs(p.x - a.x) <= NEAR && p.y >= 0 && p.y <= size.height
    case 'trend':
    case 'ray':
      return !!b && toSegment(p, a, b, d.kind === 'ray') <= NEAR
    case 'rect':
      return (
        !!b &&
        p.x >= Math.min(a.x, b.x) - NEAR &&
        p.x <= Math.max(a.x, b.x) + NEAR &&
        p.y >= Math.min(a.y, b.y) - NEAR &&
        p.y <= Math.max(a.y, b.y) + NEAR
      )
    case 'fib':
      if (!b || p.x < Math.min(a.x, b.x) - NEAR || p.x > Math.max(a.x, b.x) + NEAR) return false
      return FIB_LEVELS.some((l) => Math.abs(p.y - (b.y + (a.y - b.y) * l)) <= NEAR)
  }
}

/** The id of the topmost drawing under (x, y), or null. Later drawings sit on top. */
export function hitTest(list: PxDrawing[], x: number, y: number, size: { width: number; height: number }): string | null {
  for (let i = list.length - 1; i >= 0; i--) if (hits(list[i], { x, y }, size)) return list[i].id
  return null
}

/** Which end of a drawing the pointer is on, if any. */
export function handleAt(d: PxDrawing, x: number, y: number): 'a' | 'b' | null {
  if (Math.hypot(x - d.a.x, y - d.a.y) <= HANDLE) return 'a'
  if (d.b && Math.hypot(x - d.b.x, y - d.b.y) <= HANDLE) return 'b'
  return null
}

export function moveDrawing(d: Drawing, dTime: number, dPrice: number): Drawing {
  const shift = (p: Anchor) => ({ time: p.time + dTime, price: p.price + dPrice })
  return { ...d, a: shift(d.a), ...(d.b ? { b: shift(d.b) } : {}) }
}

export function moveAnchor(d: Drawing, end: 'a' | 'b', to: Anchor): Drawing {
  return { ...d, [end]: to }
}

export const newId = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`

const key = (symbol: string) => `apollo.drawings.${symbol}`
const isAnchor = (p: unknown): p is Anchor =>
  typeof p === 'object' && p !== null && Number.isFinite((p as Anchor).time) && Number.isFinite((p as Anchor).price)

/** The saved drawings for a symbol. Anything unreadable is dropped rather than breaking the chart. */
export function loadDrawings(symbol: string): Drawing[] {
  let raw: unknown
  try {
    raw = JSON.parse(get(key(symbol), '[]'))
  } catch {
    return []
  }
  if (!Array.isArray(raw)) return []
  return raw.filter(
    (d): d is Drawing =>
      typeof d?.id === 'string' &&
      KINDS.includes(d.kind) &&
      isAnchor(d.a) &&
      (!TWO_POINT.has(d.kind) || isAnchor(d.b)),
  )
}

export function saveDrawings(symbol: string, list: Drawing[]): void {
  set(key(symbol), JSON.stringify(list))
}
