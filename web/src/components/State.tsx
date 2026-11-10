import type { ReactNode } from 'react'
import type { ApiError } from '../api/client'

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading" className="grid gap-2">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-3 animate-pulse rounded-sm bg-soft" style={{ width: `${90 - i * 15}%` }} />
      ))}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-muted">{children}</p>
}

export function ErrorLine({ error }: { error: ApiError }) {
  return (
    <p role="alert" className="font-mono text-[11px] text-down">
      {error.message}
    </p>
  )
}
