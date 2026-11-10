import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from './client'

type Poll<T> = { data?: T; error?: ApiError; loading: boolean; refresh: () => void }

/** Run `fn` now and every `everyMs` while the tab is visible. A failed poll keeps the last data. */
export function usePoll<T>(fn: () => Promise<T>, deps: unknown[], everyMs = 60_000): Poll<T> {
  const [state, setState] = useState<{ data?: T; error?: ApiError; loading: boolean }>({ loading: true })
  const fnRef = useRef(fn)
  fnRef.current = fn
  const run = useRef(0)

  const refresh = useCallback(() => {
    const mine = ++run.current
    fnRef.current().then(
      (data) => mine === run.current && setState({ data, loading: false }),
      (e) =>
        mine === run.current &&
        setState((s) => ({
          data: s.data,
          loading: false,
          error: e instanceof ApiError ? e : new ApiError(String(e), -1),
        })),
    )
  }, [])

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
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [...deps, everyMs, refresh])

  return { ...state, refresh }
}
