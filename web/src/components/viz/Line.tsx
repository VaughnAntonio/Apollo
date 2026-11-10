import { useMemo, useState, type PointerEvent } from 'react'

export type Series = { name: string; color: string; dashed?: boolean; points: { x: string; y: number }[] }
type Ref = { y: number; label: string }
type Props = { series: Series[]; label: string; yFormat: (v: number) => string; height?: number; refs?: Ref[]; zero?: boolean }

const W = 640
const PAD = { l: 8, r: 104, t: 12, b: 24 }

/** The value a series holds at x: its last point at or before x (cumulative curves step). */
function valueAt(points: Series['points'], x: string): number | undefined {
  let v: number | undefined
  for (const p of points) {
    if (p.x > x) break
    v = p.y
  }
  return v
}

/** A small SVG line chart with direct end labels and a hover readout. x values sort as strings. */
export function Line({ series, label, yFormat, height = 220, refs = [], zero = true }: Props) {
  const [hover, setHover] = useState<number | null>(null)
  const H = height
  const xs = useMemo(() => [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort(), [series])
  const ys = [...series.flatMap((s) => s.points.map((p) => p.y)), ...refs.map((f) => f.y), ...(zero ? [0] : [])]
  const lo = Math.min(...ys)
  const hi = Math.max(...ys)
  const plotW = W - PAD.l - PAD.r
  const index = new Map(xs.map((x, i) => [x, i]))
  const px = (i: number) => PAD.l + (xs.length > 1 ? (i / (xs.length - 1)) * plotW : plotW / 2)
  const py = (v: number) => PAD.t + (hi === lo ? 0.5 : (hi - v) / (hi - lo)) * (H - PAD.t - PAD.b)

  // end labels, nudged apart so they never overlap
  const ends = series
    .filter((s) => s.points.length)
    .map((s) => ({ s, y: py(s.points.at(-1)!.y), x: px(index.get(s.points.at(-1)!.x)!) }))
    .sort((a, b) => a.y - b.y)
  for (let i = 1; i < ends.length; i++) ends[i].y = Math.max(ends[i].y, ends[i - 1].y + 13)

  const summary = `${label}. ${series
    .filter((s) => s.points.length)
    .map((s) => `${s.name} ends at ${yFormat(s.points.at(-1)!.y)}.`)
    .join(' ')}`

  const move = (e: PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    const x = ((e.clientX - r.left) / r.width) * W
    if (xs.length) setHover(Math.max(0, Math.min(xs.length - 1, Math.round(((x - PAD.l) / plotW) * (xs.length - 1)))))
  }
  const at = hover === null ? null : xs[hover]

  return (
    <figure className="relative max-w-4xl">
      <svg
        role="img"
        aria-label={summary}
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full touch-none overflow-visible"
        onPointerMove={move}
        onPointerLeave={() => setHover(null)}
      >
        {zero && <line x1={PAD.l} x2={W - PAD.r} y1={py(0)} y2={py(0)} stroke="var(--line)" />}
        {refs.map((f) => (
          <g key={f.label}>
            <line x1={PAD.l} x2={W - PAD.r} y1={py(f.y)} y2={py(f.y)} stroke="var(--muted)" strokeDasharray="2 3" />
            <text x={W - PAD.r + 6} y={py(f.y) + 3} className="fill-muted text-[11px]">
              {f.label}
            </text>
          </g>
        ))}
        <text x={PAD.l} y={PAD.t - 2} className="fill-muted font-mono text-[10px]">
          {yFormat(hi)}
        </text>
        <text x={PAD.l} y={H - PAD.b + 12} className="fill-muted font-mono text-[10px]">
          {xs[0]}
        </text>
        <text x={W - PAD.r} y={H - PAD.b + 12} textAnchor="end" className="fill-muted font-mono text-[10px]">
          {xs.at(-1)}
        </text>
        {series.map((s) => (
          <polyline
            key={s.name}
            fill="none"
            stroke={s.color}
            strokeWidth={2}
            strokeDasharray={s.dashed ? '4 3' : undefined}
            strokeLinejoin="round"
            points={s.points.map((p) => `${px(index.get(p.x)!)},${py(p.y)}`).join(' ')}
          />
        ))}
        {ends.map(({ s, x, y }) => (
          <text key={s.name} x={x + 6} y={y + 3} className="fill-ink text-[11px]">
            {s.name}
          </text>
        ))}
        {hover !== null && <line x1={px(hover)} x2={px(hover)} y1={PAD.t} y2={H - PAD.b} stroke="var(--muted)" />}
      </svg>
      {at !== null && (
        <div className="pointer-events-none absolute top-0 right-0 grid gap-0.5 border bg-panel px-2 py-1 font-mono text-[11px]">
          <span className="text-muted">{at}</span>
          {series.map((s) => {
            const v = valueAt(s.points, at)
            return v === undefined ? null : <span key={s.name}>{`${s.name} ${yFormat(v)}`}</span>
          })}
        </div>
      )}
    </figure>
  )
}
