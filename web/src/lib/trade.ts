import type { Entry } from '../api/types'

export const NOT_RECORDED = 'Not recorded'

/** Open R against the stop the trade opened with, so moving the stop can't flatter it. */
export function openR(e: Pick<Entry, 'side' | 'entry' | 'initial_stop'>, last: number): number | null {
  if (e.side === null || e.entry === null || e.initial_stop === null) return null
  const risk = Math.abs(e.entry - e.initial_stop)
  if (!risk) return null
  return ((e.side === 'long' ? 1 : -1) * (last - e.entry)) / risk
}

export const fmtR = (r: number | null) =>
  r === null ? NOT_RECORDED : `${r < 0 ? '−' : '+'}${Math.abs(r).toFixed(2)}R`

const price = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
export const fmtPrice = (x: number | null) => (x === null ? NOT_RECORDED : price.format(x))

export const fmtPct = (x: number | null) => (x === null ? NOT_RECORDED : `${(x * 100).toFixed(1)}%`)

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
export const fmtUsd = (x: number | null) => (x === null ? NOT_RECORDED : money.format(x).replace('-', '−'))
