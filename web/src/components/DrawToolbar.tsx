import { useEffect, useState, type ReactNode } from 'react'
import type { Tool } from '../lib/draw'

// 16px line icons on a 16 grid, drawn with the current text colour.
const icon = (d: ReactNode) => (
  <svg viewBox="0 0 16 16" aria-hidden="true" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.25">
    {d}
  </svg>
)
const end = (x: number, y: number) => <circle cx={x} cy={y} r="1.5" fill="currentColor" stroke="none" />

const TOOLS: { tool: Tool; label: string; key?: string; svg: ReactNode }[] = [
  { tool: 'cursor', label: 'Cursor', key: 'Esc', svg: icon(<path d="M4 2.5v10l3-3 2 4.5 1.6-.7-2-4.4H13z" strokeLinejoin="round" />) },
  { tool: 'trend', label: 'Trend line', svg: icon(<><path d="M3.5 12.5l9-9" />{end(3.5, 12.5)}{end(12.5, 3.5)}</>) },
  { tool: 'ray', label: 'Ray', svg: icon(<><path d="M3.5 12.5L15 1" />{end(3.5, 12.5)}{end(9, 7)}</>) },
  { tool: 'hline', label: 'Horizontal line', svg: icon(<><path d="M1 8h14" />{end(8, 8)}</>) },
  { tool: 'vline', label: 'Vertical line', svg: icon(<><path d="M8 1v14" />{end(8, 8)}</>) },
  { tool: 'rect', label: 'Rectangle', svg: icon(<rect x="2.5" y="4" width="11" height="8" />) },
  {
    tool: 'fib',
    label: 'Fibonacci retracement',
    svg: icon(<path d="M2 3h12M2 6.5h12M2 9.5h12M2 13h12" />),
  },
]

const btn =
  'grid size-7 place-items-center rounded-sm text-muted hover:bg-ink/[0.06] hover:text-ink aria-pressed:bg-brand/15 aria-pressed:text-brand disabled:pointer-events-none disabled:opacity-35 motion-safe:transition-colors motion-safe:duration-200'

type Props = {
  tool: Tool
  onTool: (t: Tool) => void
  selected: boolean
  count: number
  onDelete: () => void
  onClear: () => void
}

/** The drawing tools, down the left edge of the chart like TradingView's. */
export function DrawToolbar({ tool, onTool, selected, count, onDelete, onClear }: Props) {
  const [confirm, setConfirm] = useState(false)
  useEffect(() => {
    if (!confirm) return
    const t = window.setTimeout(() => setConfirm(false), 3000) // the second click has to come soon
    return () => window.clearTimeout(t)
  }, [confirm])

  return (
    <div
      role="toolbar"
      aria-label="Drawing tools"
      aria-orientation="vertical"
      className="absolute top-2 left-2 z-20 flex flex-col gap-0.5 rounded-sm border bg-bg/90 p-0.5 backdrop-blur-sm"
    >
      {TOOLS.map((t) => (
        <button
          key={t.tool}
          type="button"
          aria-label={t.label}
          aria-pressed={tool === t.tool}
          title={t.key ? `${t.label} (${t.key})` : t.label}
          onClick={() => onTool(t.tool)}
          className={btn}
        >
          {t.svg}
        </button>
      ))}
      <span className="mx-1 my-0.5 h-px bg-line" />
      <button
        type="button"
        aria-label="Delete selected drawing"
        title="Delete selected drawing (Delete)"
        disabled={!selected}
        onClick={onDelete}
        className={btn}
      >
        {icon(<path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 9h5.8l.6-9" strokeLinejoin="round" />)}
      </button>
      <button
        type="button"
        aria-label={confirm ? `Click again to remove all ${count} drawings` : 'Remove all drawings'}
        title={confirm ? 'Click again to remove all' : 'Remove all drawings'}
        disabled={!count}
        onClick={() => (confirm ? (setConfirm(false), onClear()) : setConfirm(true))}
        className={`${btn} ${confirm ? 'bg-down/15 text-down hover:bg-down/20 hover:text-down' : ''}`}
      >
        {icon(<path d="M4 4l8 8M12 4l-8 8" />)}
      </button>
    </div>
  )
}
