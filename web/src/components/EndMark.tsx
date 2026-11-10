// The "⊣" mark used on Close and the New journal entry tile, as in Portfoliov2.
export function EndMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className} fill="none" stroke="currentColor" strokeWidth="1.25">
      <path d="M2 12h18M20 4v16" />
    </svg>
  )
}
