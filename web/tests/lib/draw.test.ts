import { beforeEach, expect, it } from 'vitest'
import {
  type Drawing,
  type PxDrawing,
  fibPrices,
  handleAt,
  hitTest,
  loadDrawings,
  logicalToTime,
  logicalToX,
  moveAnchor,
  moveDrawing,
  saveDrawings,
  timeToLogical,
} from '../../src/lib/draw'

const T = [100, 200, 300]

it('places a time between bars, and before or after them, as a fractional bar index', () => {
  expect(timeToLogical(T, 200)).toBe(1)
  expect(timeToLogical(T, 250)).toBe(1.5)
  expect(timeToLogical(T, 50)).toBe(-0.5) // before the first bar, at the first bar spacing
  expect(timeToLogical(T, 400)).toBe(3) // after the last, at the last spacing
  expect(timeToLogical([], 100)).toBeNull()
})

it('turns a fractional bar index back into the same time', () => {
  for (const t of [50, 100, 175, 300, 420]) expect(logicalToTime(T, timeToLogical(T, t)!)).toBeCloseTo(t)
  expect(timeToLogical([100], 100)).toBe(0) // one bar: no spacing to extrapolate with
  expect(logicalToTime([100], 0)).toBe(100)
})

it('puts Fibonacci 0 at the second point and 1 at the first, like TradingView', () => {
  const levels = fibPrices({ time: 0, price: 100 }, { time: 1, price: 200 })
  expect(levels.map((l) => l.level)).toEqual([0, 0.236, 0.382, 0.5, 0.618, 0.786, 1])
  expect(levels[0].price).toBe(200)
  expect(levels[3].price).toBe(150)
  expect(levels[6].price).toBe(100)
})

const px = (d: Partial<PxDrawing> & Pick<PxDrawing, 'kind'>): PxDrawing => ({ id: 'x', a: { x: 0, y: 0 }, b: { x: 100, y: 100 }, ...d })

it('finds the drawing under the pointer, within a few pixels', () => {
  const size = { width: 1000, height: 500 }
  expect(hitTest([px({ kind: 'trend' })], 50, 53, size)).toBe('x')
  expect(hitTest([px({ kind: 'trend' })], 50, 70, size)).toBeNull()
  expect(hitTest([px({ kind: 'trend' })], 150, 150, size)).toBeNull() // past the end of a segment
  expect(hitTest([px({ kind: 'ray' })], 150, 151, size)).toBe('x') // a ray keeps going
  expect(hitTest([px({ kind: 'hline', a: { x: 10, y: 40 } })], 900, 43, size)).toBe('x')
  expect(hitTest([px({ kind: 'vline', a: { x: 40, y: 10 } })], 42, 480, size)).toBe('x')
  expect(hitTest([px({ kind: 'rect' })], 50, 50, size)).toBe('x') // anywhere inside a rectangle
  expect(hitTest([px({ kind: 'fib' })], 50, 50.5, size)).toBe('x') // on the 0.5 line
  expect(hitTest([px({ kind: 'fib' })], 50, 45, size)).toBeNull() // between levels
})

it('prefers the drawing on top when two overlap', () => {
  const size = { width: 1000, height: 500 }
  expect(hitTest([px({ kind: 'rect', id: 'under' }), px({ kind: 'rect', id: 'over' })], 50, 50, size)).toBe('over')
})

it('finds an end handle under the pointer', () => {
  const s = px({ kind: 'trend' })
  expect(handleAt(s, 3, -2)).toBe('a')
  expect(handleAt(s, 98, 101)).toBe('b')
  expect(handleAt(s, 50, 50)).toBeNull()
})

it('moves a whole drawing or one of its ends', () => {
  const d: Drawing = { id: '1', kind: 'trend', a: { time: 100, price: 10 }, b: { time: 200, price: 20 } }
  expect(moveDrawing(d, 50, -1)).toEqual({ ...d, a: { time: 150, price: 9 }, b: { time: 250, price: 19 } })
  expect(moveAnchor(d, 'b', { time: 300, price: 30 })).toEqual({ ...d, b: { time: 300, price: 30 } })
})

beforeEach(() => localStorage.clear())

it('keeps drawings per symbol and drops anything malformed', () => {
  const d: Drawing = { id: '1', kind: 'hline', a: { time: 100, price: 10 } }
  saveDrawings('MNQ', [d])
  expect(loadDrawings('MNQ')).toEqual([d])
  expect(loadDrawings('MES')).toEqual([])
  localStorage.setItem('apollo.drawings.MES', '{oops')
  expect(loadDrawings('MES')).toEqual([])
  localStorage.setItem('apollo.drawings.MES', JSON.stringify([d, { id: '2', kind: 'laser', a: {} }, { id: '3', kind: 'trend', a: d.a }]))
  expect(loadDrawings('MES')).toEqual([d]) // an unknown kind, and a trend line missing its second end
})

it('places a time between bars between their pixels: the chart only maps whole bar indexes', () => {
  const coord = (l: number) => (Number.isInteger(l) ? 100 + l * 10 : 0) // what lightweight-charts does
  expect(logicalToX(coord, 3)).toBe(130)
  expect(logicalToX(coord, 3.25)).toBe(132.5)
  expect(logicalToX(coord, -0.5)).toBe(95)
  expect(logicalToX(() => null, 2)).toBeNull()
})
