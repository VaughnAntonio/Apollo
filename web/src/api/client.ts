import { isStatic } from '../lib/mode'
import { ApiError } from './error'
import { staticApi } from './static'
import type { BacktestRecord, Bar, Entry, Explain, Forecast, JournalIn, JournalPatch, JournalStats, Layer, ModelsReport, Signal, Sym } from './types'

export { ApiError }

export const API = import.meta.env.VITE_API ?? 'http://127.0.0.1:8000'
export const START_API = 'Start the API: python -m apollo.api.main'

type Query = Record<string, string | number | undefined>

async function call<T>(path: string, query: Query = {}, init: RequestInit = {}): Promise<T> {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) if (v !== undefined) qs.set(k, String(v))
  const url = `${API}${path}${qs.size ? `?${qs}` : ''}`
  let res: Response
  try {
    res = await fetch(url, init)
  } catch {
    throw new ApiError(START_API, 0)
  }
  const body = await res.json().catch(() => null)
  if (!res.ok) {
    const detail = body?.detail
    throw new ApiError(typeof detail === 'string' ? detail : `Request failed (${res.status})`, res.status)
  }
  return body as T
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
})

export const liveApi = {
  symbols: () => call<Sym[]>('/symbols'),
  bars: (symbol: string, tf: string, start?: number) =>
    call<Bar[]>('/bars', {
      symbol,
      tf,
      start: start === undefined ? undefined : new Date(start * 1000).toISOString(),
    }),
  signal: (symbol: string) => call<Signal>('/signal', { symbol }),
  forecast: (symbol: string) => call<Forecast>('/forecast', { symbol }),
  backtest: (symbol: string, layer: Layer) => call<BacktestRecord[]>('/backtest/summary', { symbol, layer }),
  models: (symbol: string) => call<ModelsReport>('/models', { symbol }),
  explain: (symbol: string) => call<Explain>('/explain', { symbol }),
  journal: {
    list: () => call<Entry[]>('/journal'),
    get: (id: number) => call<Entry>(`/journal/${id}`),
    create: (body: JournalIn) => call<{ id: number }>('/journal', {}, json('POST', body)),
    patch: (id: number, body: JournalPatch) => call<Entry>(`/journal/${id}`, {}, json('PATCH', body)),
    remove: (id: number) => call<{ deleted: boolean }>(`/journal/${id}`, {}, { method: 'DELETE' }),
    close: (id: number, body: { exit: number; at?: string; reason?: string }) =>
      call<Entry>(`/journal/${id}/close`, {}, json('POST', body)),
    take: (symbol: string, body: { fill?: number; size?: number }) =>
      call<{ id: number }>('/journal/take', { symbol }, json('POST', body)),
    autoClose: (symbol: string) =>
      call<{ closed: number[] }>('/journal/auto-close', { symbol }, { method: 'POST' }),
    screenshot: (id: number, file: File) => {
      const form = new FormData()
      form.append('file', file)
      return call<Entry>(`/journal/${id}/screenshot`, {}, { method: 'POST', body: form })
    },
    stats: () => call<JournalStats>('/journal/stats'),
  },
}

type Api = typeof liveApi
// Picked on every access, so the mode can't go stale and tests can switch it.
const readOnly: Api = staticApi // the type check that both clients have the same shape
export const api: Api = new Proxy(liveApi, {
  get: (_, key: keyof Api) => (isStatic() ? readOnly : liveApi)[key],
})

/** Stored screenshot paths look like `journal_media/<name>`; the API serves them at /media. */
export const mediaUrl = (path: string) => `${API}/media/${path.replace(/^journal_media\//, '')}`
