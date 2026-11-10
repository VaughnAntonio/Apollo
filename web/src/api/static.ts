import { useEffect, useState } from 'react'
import { ApiError } from './error'
import type { BacktestRecord, Bar, Entry, Explain, Forecast, JournalStats, Layer, ModelsReport, Signal, Sym } from './types'

export const MISSING = 'Snapshot file missing'
const READ_ONLY = 'This is a read-only snapshot'

/** Snapshot files sit under the site's base path, e.g. /Apollo/snapshot/... on GitHub Pages. */
export const snapshotUrl = (path: string) => `${import.meta.env.BASE_URL}snapshot/${path}`

async function file<T>(path: string): Promise<T | undefined> {
  let res: Response
  try {
    res = await fetch(snapshotUrl(path))
  } catch {
    throw new ApiError(MISSING, 0)
  }
  if (res.status === 404) return undefined
  const body = await res.json().catch(() => undefined)
  if (!res.ok || body === undefined) throw new ApiError(MISSING, res.status)
  return body as T
}

async function need<T>(path: string): Promise<T> {
  const body = await file<T>(path)
  if (body === undefined) throw new ApiError(MISSING, 404)
  return body
}

const refuse = async (..._args: unknown[]): Promise<never> => {
  throw new ApiError(READ_ONLY, 405)
}

const NO_SIGNAL = (symbol: string): Signal => ({
  symbol, status: 'no_model', direction: null, entry: null, entry_ts: null, stop: null, target: null,
  contracts: null, risk_of_limit: null, account: '', variant: '', as_of: '', checklist: [], research_only: true,
})

export const staticApi = {
  symbols: () => need<Sym[]>('symbols.json'),
  bars: async (symbol: string, tf: string, start?: number) => {
    const all = (await file<Bar[]>(`bars/${symbol}_${tf}.json`)) ?? []
    return start === undefined ? all : all.filter((b) => b.time >= start)
  },
  signal: async (symbol: string) => (await file<Signal>(`signal/${symbol}.json`)) ?? NO_SIGNAL(symbol),
  forecast: async (symbol: string): Promise<Forecast> =>
    (await file<Forecast>(`forecast/${symbol}.json`)) ?? { status: 'no_model', research_only: true },
  backtest: (symbol: string, layer: Layer) => need<BacktestRecord[]>(`backtest/${symbol}_${layer}.json`),
  models: (symbol: string) => need<ModelsReport>(`models/${symbol}.json`),
  explain: (symbol: string) => need<Explain>(`explain/${symbol}.json`),
  journal: {
    list: async () => (await file<Entry[]>('journal.json')) ?? [],
    get: async (id: number) => {
      const hit = ((await file<Entry[]>('journal.json')) ?? []).find((e) => e.id === id)
      if (!hit) throw new ApiError('no such entry', 404)
      return hit
    },
    create: refuse,
    patch: refuse,
    remove: refuse,
    close: refuse,
    take: refuse,
    autoClose: refuse,
    screenshot: refuse,
    stats: () => need<JournalStats>('journal_stats.json'),
  },
}

/** The day the snapshot was taken, from meta.json; null until it loads or if it's missing. */
export function useSnapshotDate(): string | null {
  const [date, setDate] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    file<{ date: string }>('meta.json')
      .then((m) => live && setDate(m?.date ?? null))
      .catch(() => {})
    return () => {
      live = false
    }
  }, [])
  return date
}
