import { vi } from 'vitest'

/** Make the next fetch answer with this status and JSON body. */
export function fetchMock(status: number, body: unknown) {
  const res = new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
  const fn = vi.fn().mockResolvedValue(res)
  vi.stubGlobal('fetch', fn)
  return fn
}

/** Route fetches by path ("/signal", "/journal/take", ...) to bodies, or to Errors for failures. */
export function mockApi(routes: Record<string, unknown>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input))
    const key = `${init?.method ?? 'GET'} ${url.pathname}`
    const hit = key in routes ? routes[key] : routes[url.pathname]
    if (hit === undefined) return new Response(JSON.stringify({ detail: 'not mocked' }), { status: 404 })
    if (hit instanceof ApiFailure) {
      return new Response(JSON.stringify({ detail: hit.detail }), { status: hit.status })
    }
    return new Response(JSON.stringify(hit), { status: 200, headers: { 'content-type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

export class ApiFailure {
  status: number
  detail: string
  constructor(status: number, detail: string) {
    this.status = status
    this.detail = detail
  }
}

export function setVisibility(state: 'visible' | 'hidden') {
  Object.defineProperty(document, 'visibilityState', { value: state, configurable: true })
  document.dispatchEvent(new Event('visibilitychange'))
}
