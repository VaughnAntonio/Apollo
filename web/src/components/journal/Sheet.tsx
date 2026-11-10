import { Dialog } from 'radix-ui'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import { usePoll } from '../../api/usePoll'
import { isStatic } from '../../lib/mode'
import { nyDate, toSec } from '../../lib/time'
import { EndMark } from '../EndMark'
import { ErrorLine, Skeleton } from '../State'
import { emptyForm, EntryForm, entryBody, formFrom, patchBody } from './EntryForm'
import { Stats } from './Stats'
import { TradeDetail } from './TradeDetail'
import { TradeList } from './TradeList'

type Props = {
  open: boolean
  mode: 'view' | 'new'
  selectedId: number | null
  symbol?: string
  onOpenChange: (open: boolean) => void
  onChanged: () => void
}

type View = { kind: 'overview' } | { kind: 'trade'; id: number } | { kind: 'new' } | { kind: 'edit'; id: number }

const initialView = (mode: Props['mode'], id: number | null): View =>
  mode === 'new' ? { kind: 'new' } : id !== null ? { kind: 'trade', id } : { kind: 'overview' }

export function Sheet({ open, mode, selectedId, symbol = 'MNQ', onOpenChange, onChanged }: Props) {
  const list = usePoll(api.journal.list, [open], 60_000)
  const stats = usePoll(api.journal.stats, [open], 60_000)
  const symbols = usePoll(api.symbols, [], 3_600_000)
  const [view, setView] = useState<View>(() => initialView(mode, selectedId))
  const [day, setDay] = useState<string | null>(null)

  useEffect(() => setView(initialView(mode, selectedId)), [mode, selectedId, open])

  const entries = useMemo(
    () => (list.data ?? []).filter((e) => day === null || nyDate(toSec(e.opened_at)) === day),
    [list.data, day],
  )
  const current = view.kind === 'trade' || view.kind === 'edit' ? list.data?.find((e) => e.id === view.id) : undefined

  const changed = (next: View) => {
    list.refresh()
    stats.refresh()
    onChanged()
    setView(next)
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Content
          aria-describedby={undefined}
          data-menu
          className="fixed inset-0 z-50 grid grid-rows-[40dvh_1fr] bg-panel text-ink md:grid-cols-[minmax(260px,360px)_1fr] md:grid-rows-1"
        >
          <Dialog.Title className="sr-only">Journal</Dialog.Title>
          <div className="min-h-0 overflow-auto border-b md:h-dvh md:border-r md:border-b-0">
            <div className="sticky top-0 z-10 flex items-center justify-between border-b bg-panel px-5 py-4">
              <button type="button" className="font-semibold" onClick={() => (setDay(null), setView({ kind: 'overview' }))}>
                Journal
              </button>
              {!isStatic() && (
              <button
                type="button"
                onClick={() => setView({ kind: 'new' })}
                className="rounded-sm bg-brand px-2.5 py-1.5 font-mono text-[10px] font-medium tracking-widest text-brand-fg uppercase"
              >
                New
              </button>
              )}
            </div>
            {day && (
              <button type="button" onClick={() => setDay(null)} className="w-full border-b px-5 py-2 text-left font-mono text-[11px] text-muted">
                {`Showing ${day} · clear`}
              </button>
            )}
            {list.data ? (
              <TradeList entries={entries} selected={current?.id ?? null} onSelect={(id) => setView({ kind: 'trade', id })} />
            ) : list.error ? (
              <div className="px-5 py-4">
                <ErrorLine error={list.error} />
              </div>
            ) : (
              <div className="px-5 py-4">
                <Skeleton rows={6} />
              </div>
            )}
          </div>

          <div className="min-h-0 overflow-auto px-4 pt-4 pb-10 md:h-dvh md:px-8">
            <div className="flex items-center justify-between border-b pb-4">
              <span className="font-mono text-[10px] font-medium tracking-widest text-muted uppercase">
                {view.kind === 'new' ? 'New entry' : view.kind === 'edit' ? 'Edit entry' : view.kind === 'trade' ? 'Trade' : 'Overview'}
              </span>
              <Dialog.Close className="flex items-center gap-2.5 hover:text-brand">
                Close
                <EndMark className="size-[22px]" />
              </Dialog.Close>
            </div>

            {view.kind === 'overview' &&
              (stats.data ? (
                <div className="pt-6">
                  <Stats stats={stats.data} day={day} onDay={setDay} />
                </div>
              ) : stats.error ? (
                <ErrorLine error={stats.error} />
              ) : (
                <div className="pt-6">
                  <Skeleton rows={4} />
                </div>
              ))}

            {view.kind === 'trade' && current && (
              <TradeDetail
                entry={current}
                onEdit={() => setView({ kind: 'edit', id: current.id })}
                onDeleted={() => changed({ kind: 'overview' })}
                onChanged={() => changed(view)}
              />
            )}

            {view.kind === 'new' && (
              <EntryForm
                key="new"
                initial={emptyForm(symbol)}
                editing={false}
                symbols={symbols.data?.map((s) => s.code) ?? [symbol]}
                onSave={async (f) => {
                  const { id } = await api.journal.create(entryBody(f))
                  changed({ kind: 'trade', id })
                }}
                onCancel={() => setView({ kind: 'overview' })}
              />
            )}

            {view.kind === 'edit' && current && (
              <EntryForm
                key={`edit-${current.id}`}
                initial={formFrom(current)}
                editing
                symbols={[current.symbol]}
                onSave={async (f) => {
                  const body = patchBody(f, current)
                  if (Object.keys(body).length) await api.journal.patch(current.id, body)
                  changed({ kind: 'trade', id: current.id })
                }}
                onCancel={() => setView({ kind: 'trade', id: current.id })}
              />
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
