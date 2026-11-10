import type { ReactNode } from 'react'

/** Shared bits for the report pages: a heading, labelled blocks and hairline tables. */

export function PageHead({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header className="border-b px-5 pt-8 pb-5">
      <h1 className="text-[28px] font-semibold tracking-tight">{title}</h1>
      {children && <div className="mt-2 max-w-[70ch] text-muted">{children}</div>}
    </header>
  )
}

export function Block({ label, children, note }: { label: string; children: ReactNode; note?: ReactNode }) {
  return (
    <section className="border-b px-5 py-6">
      <h2 className="mb-4 font-mono text-[10px] font-medium tracking-widest text-muted uppercase">{label}</h2>
      {children}
      {note && <p className="mt-3 max-w-[70ch] text-[12px] text-muted">{note}</p>}
    </section>
  )
}

export const table = 'w-full border-collapse text-left [&_td]:border-t [&_td]:py-1.5 [&_td]:pr-4 [&_th]:pb-2 [&_th]:pr-4 [&_th]:font-mono [&_th]:text-[10px] [&_th]:font-medium [&_th]:tracking-widest [&_th]:text-muted [&_th]:uppercase'
export const num = 'font-mono tabular-nums whitespace-nowrap'

export const dash = '–'
export const r2 = (x: number | null | undefined) =>
  x === null || x === undefined || Number.isNaN(x) ? dash : `${x < 0 ? '−' : '+'}${Math.abs(x).toFixed(2)}R`
export const pct = (x: number | null | undefined, digits = 0) =>
  x === null || x === undefined || Number.isNaN(x) ? dash : `${(x * 100).toFixed(digits)}%`
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
export const usd = (x: number | null | undefined) =>
  x === null || x === undefined || Number.isNaN(x) ? dash : money.format(x).replace('-', '−')

export function Tabs<T extends string>({ value, options, onChange, label }: { value: T; options: T[]; onChange: (v: T) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="flex gap-0.5">
      {options.map((o) => (
        <button
          key={o}
          type="button"
          role="tab"
          aria-selected={o === value}
          onClick={() => onChange(o)}
          className="border-b border-transparent px-2 py-1.5 font-mono text-xs font-medium text-muted aria-selected:border-ink aria-selected:text-ink"
        >
          {o}
        </button>
      ))}
    </div>
  )
}
