type Props = { labels: string[]; matrix: number[][]; label: string }

/** A confusion matrix: rows are what happened, columns what the model said. One sequential hue. */
export function Heatmap({ labels, matrix, label }: Props) {
  const max = Math.max(1, ...matrix.flat())
  const name = (l: string) => l.replace('_', ' ')
  return (
    <figure aria-label={label} className="inline-block">
      <div className="grid gap-0.5 font-mono text-[11px]" style={{ gridTemplateColumns: `auto repeat(${labels.length}, minmax(52px, 1fr))` }}>
        <span className="pr-2 text-muted">actual ↓ predicted →</span>
        {labels.map((l) => (
          <span key={l} className="px-1 pb-1 text-center text-muted">
            {name(l)}
          </span>
        ))}
        {matrix.map((row, i) => (
          <div key={labels[i]} className="contents">
            <span className="self-center pr-2 text-muted">{name(labels[i])}</span>
            {row.map((n, j) => {
              const share = Math.round((n / max) * 100)
              return (
                <span
                  key={labels[j]}
                  role="img"
                  aria-label={`actual ${name(labels[i])}, predicted ${name(labels[j])}: ${n}`}
                  title={`actual ${name(labels[i])}, predicted ${name(labels[j])}: ${n}`}
                  className={`grid h-10 place-items-center rounded-sm ${share > 55 ? 'text-brand-fg' : 'text-ink'} ${i === j ? 'ring-1 ring-ink/40' : ''}`}
                  style={{ background: `color-mix(in oklab, var(--brand) ${share}%, var(--soft))` }}
                >
                  {n}
                </span>
              )
            })}
          </div>
        ))}
      </div>
    </figure>
  )
}
