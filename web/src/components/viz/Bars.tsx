export type Bin = { label: string; value: number; tone: 'up' | 'down' }
type Props = { bins: Bin[]; label: string; height?: number }

const W = 640
const PAD = { t: 14, b: 20 }
const GAP = 2

/** Vertical bars on one baseline. Each bar has a native tooltip; the counts sit above the bars. */
export function Bars({ bins, label, height = 160 }: Props) {
  const max = Math.max(1, ...bins.map((b) => b.value))
  const slot = W / Math.max(1, bins.length)
  const base = height - PAD.b
  const every = Math.ceil(bins.length / 12) // keep the axis labels from colliding
  const summary = `${label}. ${bins.map((b) => `${b.label}: ${b.value}`).join(', ')}.`
  return (
    <svg role="img" aria-label={summary} viewBox={`0 0 ${W} ${height}`} className="h-auto w-full">
      <line x1={0} x2={W} y1={base} y2={base} stroke="var(--line)" />
      {bins.map((b, i) => {
        const h = (b.value / max) * (base - PAD.t)
        const x = i * slot + GAP / 2
        return (
          <g key={b.label}>
            <rect
              data-bar
              x={x}
              y={base - h}
              width={slot - GAP}
              height={h}
              rx={2}
              fill={b.tone === 'down' ? 'var(--down)' : 'var(--brand)'}
            >
              <title>{`${b.label}: ${b.value}`}</title>
            </rect>
            {b.value > 0 && (
              <text x={x + (slot - GAP) / 2} y={base - h - 3} textAnchor="middle" className="fill-ink font-mono text-[10px]">
                {b.value}
              </text>
            )}
            {i % every === 0 && (
              <text x={x + (slot - GAP) / 2} y={height - 6} textAnchor="middle" className="fill-muted font-mono text-[10px]">
                {b.label}
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}
