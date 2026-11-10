const ROWS = [
  ['Machine vibration', 'Health indicators', 'Failure warning'],
  ['Hourly returns', 'Spectral kurtosis, envelope, crest, RMS', 'Regime warning'],
]

/** The idea behind the regime detector: predictive maintenance applied to a price series. */
export function PdmDiagram() {
  const W = 640
  const box = { w: 180, h: 46 }
  const xs = [0, 230, 460]
  return (
    <figure>
      <svg
        role="img"
        aria-label="Top row: machine vibration, then health indicators, then a failure warning. Bottom row: hourly returns, then spectral kurtosis, envelope, crest factor and RMS, then a regime warning."
        viewBox={`0 0 ${W} 150`}
        className="h-auto w-full max-w-2xl"
      >
        <defs>
          <marker id="pdm-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" orient="auto">
            <path d="M0,0 L8,4 L0,8 z" fill="var(--muted)" />
          </marker>
        </defs>
        {ROWS.map((row, r) =>
          row.map((text, c) => {
            const y = 10 + r * 82
            const strong = r === 1
            return (
              <g key={`${r}-${c}`}>
                <rect
                  x={xs[c] + 1}
                  y={y}
                  width={box.w}
                  height={box.h}
                  rx={4}
                  fill={strong && c === 2 ? 'var(--brand)' : 'var(--panel)'}
                  stroke={strong ? 'var(--brand)' : 'var(--line)'}
                />
                <foreignObject x={xs[c] + 6} y={y + 4} width={box.w - 10} height={box.h - 8}>
                  <div
                    className={`grid h-full place-items-center text-center text-[12px] leading-tight ${strong && c === 2 ? 'text-brand-fg' : strong ? 'text-ink' : 'text-muted'}`}
                  >
                    {text}
                  </div>
                </foreignObject>
                {c < 2 && (
                  <line
                    x1={xs[c] + box.w + 4}
                    x2={xs[c + 1] - 4}
                    y1={y + box.h / 2}
                    y2={y + box.h / 2}
                    stroke="var(--muted)"
                    markerEnd="url(#pdm-arrow)"
                  />
                )}
              </g>
            )
          }),
        )}
      </svg>
      <figcaption className="mt-2 max-w-[70ch] text-[12px] text-muted">
        In a factory, sensors on a bearing feed health indicators that warn before it fails. Apollo treats the market the
        same way: the same indicators, computed on returns, warn when the day is likely to trend, chop or stay normal.
      </figcaption>
    </figure>
  )
}
