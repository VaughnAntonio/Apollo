import { Popover } from 'radix-ui'
import { useEffect, useMemo, useState, type KeyboardEvent } from 'react'
import { api } from '../api/client'
import type { Sym } from '../api/types'
import { usePoll } from '../api/usePoll'
import { set } from '../lib/storage'
import { ErrorLine } from './State'

const GROUPS: { kind: Sym['kind']; label: string }[] = [
  { kind: 'future', label: 'Futures' },
  { kind: 'stock', label: 'US stocks' },
]

export function TickerPicker({ value, onChange }: { value: string; onChange: (code: string) => void }) {
  const { data: symbols = [], error } = usePoll(api.symbols, [], 3_600_000)
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [active, setActive] = useState(0)

  useEffect(() => {
    if (symbols.length && !symbols.some((s) => s.code === value)) onChange('MNQ')
  }, [symbols, value, onChange])

  const matches = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return symbols.filter((s) => !needle || s.code.toLowerCase().includes(needle) || s.name.toLowerCase().includes(needle))
  }, [symbols, q])

  const pick = (code: string) => {
    set('apollo.symbol', code)
    onChange(code)
    setOpen(false)
    setQ('')
  }

  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && matches[active]) pick(matches[active].code)
    if (e.key === 'ArrowDown') setActive((i) => Math.min(i + 1, matches.length - 1))
    if (e.key === 'ArrowUp') setActive((i) => Math.max(i - 1, 0))
  }

  const current = symbols.find((s) => s.code === value)
  return (
    <Popover.Root open={open} onOpenChange={(o) => (setOpen(o), setActive(0))}>
      <Popover.Trigger aria-haspopup="listbox" className="flex items-baseline gap-2.5 py-1">
        <b className="text-[15px] font-semibold tracking-tight">{value}</b>
        <span className="hidden font-mono text-muted sm:inline">{current?.name}</span>
        <span aria-hidden="true" className="text-[10px] text-muted">
          ▾
        </span>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={8}
          data-pop
          className="z-40 w-[300px] max-w-[calc(100vw-32px)] rounded-sm border bg-panel text-ink"
        >
          <input
            autoFocus
            value={q}
            onChange={(e) => (setQ(e.target.value), setActive(0))}
            onKeyDown={onKey}
            role="combobox"
            aria-expanded="true"
            aria-controls="symbol-list"
            aria-activedescendant={matches[active] ? `symbol-${matches[active].code}` : undefined}
            placeholder="Search futures or US stocks"
            aria-label="Search symbols"
            className="block w-full border-b bg-transparent px-3 py-2.5 font-mono outline-none"
          />
          <div id="symbol-list" role="listbox" className="max-h-80 overflow-auto pb-1">
            {error && !symbols.length && (
              <div className="px-3 py-3">
                <ErrorLine error={error} />
              </div>
            )}
            {matches.length === 0 && !error && <p className="px-3 py-3 text-muted">{`No symbol matches ${q}`}</p>}
            {GROUPS.map((g) => {
              const rows = matches.filter((s) => s.kind === g.kind)
              if (!rows.length) return null
              return (
                <div key={g.kind}>
                  <div className="px-3 pt-2 pb-0.5 font-mono text-[10px] font-medium tracking-widest text-muted uppercase">{g.label}</div>
                  {rows.map((s) => (
                    <button
                      key={s.code}
                      id={`symbol-${s.code}`}
                      type="button"
                      role="option"
                      aria-selected={matches[active]?.code === s.code}
                      onClick={() => pick(s.code)}
                      className="grid w-full grid-cols-[64px_1fr] gap-2 px-3 py-1.5 text-left hover:bg-soft aria-selected:bg-soft"
                    >
                      <span className="font-mono">{s.code}</span>
                      <span className="truncate text-muted">{s.name}</span>
                    </button>
                  ))}
                </div>
              )
            })}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
