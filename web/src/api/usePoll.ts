import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './client'

type Poll<T> = { data?: T; error?: ApiError; loading: boolean; refresh: () => void }

const RETRY_MS = 60_000

/**
 * Run `fn` now and every `everyMs` while the tab is visible. A failed poll keeps the last data, and a
 * slow poll that fails retries every minute so the panel recovers soon after the API comes back.
 */
export function usePoll<T>(fn: () => Promise<T>, deps: unknown[], everyMs = 60_000): Poll<T> {
  const [state, setState] = useState<{ data?: T; error?: ApiError; loading: boolean }>({ loading: true })
  const fnRef = useRef(fn)
  fnRef.current = fn
  const run = useRef(0)
  const retry = useRef<number | undefined>(undefined)
  const slow = everyMs > RETRY_MS

  const refresh = useCallback(() => {
    const mine = ++run.current
    window.clearTimeout(retry.current)
    fnRef.current().then(
      (data) => mine === run.current && setState({ data, loading: false }),
      (e) => {
        if (mine !== run.current) return
        setState((s) => ({
          data: s.data,
          loading: false,
          error: e instanceof ApiError ? e : new ApiError(String(e), -1),
        }))
        if (slow && document.visibilityState !== 'hidden') retry.current = window.setTimeout(refresh, RETRY_MS)
      },
    )
  }, [slow])

  useEffect(() => {
    setState({ loading: true })
    refresh()
    let timer = window.setInterval(refresh, everyMs)
    const onVisibility = () => {
      window.clearInterval(timer)
      if (document.visibilityState === 'visible') {
        refresh()
        timer = window.setInterval(refresh, everyMs)
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      window.clearInterval(timer)
      window.clearTimeout(retry.current)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [...deps, everyMs, refresh])

  return { ...state, refresh }
}
