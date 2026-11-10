import { useState, type FormEvent, type ReactNode } from 'react'
import { ApiError } from '../../api/client'
import type { Entry, Grade, JournalIn, JournalPatch, Side, Stage } from '../../api/types'
import { nyDate, nyTime, toNaiveIso, toSec } from '../../lib/time'
import { ErrorLine } from '../State'

export type EntryFormState = {
  opened_at: string
  symbol: string
  side: Side
  entry: string
  stop: string
  target: string
  size: string
  fees: string
  account: string
  stage: Stage | ''
  strategy: string
  grade: Grade | ''
  tags: string
  notes: string
  exit: string
  closed_at: string
}

export const emptyForm = (symbol: string): EntryFormState => ({
  opened_at: '', symbol, side: 'long', entry: '', stop: '', target: '', size: '1', fees: '', account: '',
  stage: '', strategy: '', grade: '', tags: '', notes: '', exit: '', closed_at: '',
})

/** An API time as a `datetime-local` value in ET. */
const localNy = (iso: string | null) => (iso ? `${nyDate(toSec(iso))}T${nyTime(toSec(iso))}` : '')
const str = (x: number | string | null) => (x === null ? '' : String(x))

export const formFrom = (e: Entry): EntryFormState => ({
  opened_at: localNy(e.opened_at), symbol: e.symbol, side: e.side ?? 'long', entry: str(e.entry), stop: str(e.stop),
  target: str(e.target), size: str(e.size), fees: str(e.fees), account: str(e.account), stage: e.stage ?? '',
  strategy: str(e.strategy), grade: e.grade ?? '', tags: e.tags.join(', '), notes: str(e.notes), exit: str(e.exit),
  closed_at: localNy(e.closed_at),
})

const LABELS: Record<string, string> = { entry: 'Entry', stop: 'Stop', target: 'Target', exit: 'Exit', fees: 'Fees' }

function num(field: string, v: string): number | undefined {
  if (v.trim() === '') return undefined
  const n = Number(v)
  if (!Number.isFinite(n)) throw new Error(`${LABELS[field] ?? field} must be a number`)
  return n
}

function size(v: string): number {
  const n = Number(v)
  if (!Number.isInteger(n) || n <= 0) throw new Error('Contracts must be a whole number above 0')
  return n
}

const tagList = (v: string) => v.split(',').map((t) => t.trim()).filter(Boolean)

/** The POST /journal body. Throws an Error with a readable message for bad numbers. */
export function entryBody(f: EntryFormState): JournalIn {
  const body: JournalIn = { opened_at: toNaiveIso(f.opened_at), symbol: f.symbol, side: f.side, size: size(f.size) }
  for (const k of ['entry', 'stop', 'target', 'fees'] as const) {
    const n = num(k, f[k])
    if (n !== undefined) body[k] = n
  }
  if (f.account.trim()) body.account = f.account.trim()
  if (f.stage) body.stage = f.stage
  if (f.strategy.trim()) body.strategy = f.strategy.trim()
  if (f.grade) body.grade = f.grade
  const tags = tagList(f.tags)
  if (tags.length) body.tags = tags
  if (f.notes.trim()) body.notes = f.notes
  return body
}

/** The PATCH body: only fields that changed. A new exit closes the trade by hand. */
export function patchBody(f: EntryFormState, e: Entry): JournalPatch {
  const before = formFrom(e)
  const out: JournalPatch = {}
  const changed = (k: keyof EntryFormState) => f[k] !== before[k]
  if (changed('side')) out.side = f.side
  for (const k of ['entry', 'stop', 'target', 'fees'] as const) if (changed(k)) out[k] = num(k, f[k])
  if (changed('size')) out.size = size(f.size)
  if (changed('account')) out.account = f.account.trim() || undefined
  if (changed('stage')) out.stage = f.stage || undefined
  if (changed('strategy')) out.strategy = f.strategy.trim() || undefined
  if (changed('grade')) out.grade = f.grade || undefined
  if (changed('tags')) out.tags = tagList(f.tags)
  if (changed('notes')) out.notes = f.notes
  if (changed('exit') || changed('closed_at')) {
    out.exit = num('exit', f.exit)
    if (f.closed_at) out.closed_at = toNaiveIso(f.closed_at)
    out.exit_reason = 'manual'
    out.needs_confirm = false
  }
  return out
}

const input = 'w-full rounded-sm border bg-transparent px-2 py-1.5 font-mono'

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-1 text-muted">
      {label}
      {children}
    </label>
  )
}

type Props = {
  initial: EntryFormState
  editing: boolean
  symbols: string[]
  onSave: (f: EntryFormState) => Promise<void>
  onCancel: () => void
}

export function EntryForm({ initial, editing, symbols, onSave, onCancel }: Props) {
  const [f, setF] = useState(initial)
  const [error, setError] = useState<ApiError | null>(null)
  const [busy, setBusy] = useState(false)
  const bind = (k: keyof EntryFormState) => ({
    value: f[k],
    onChange: (e: { target: { value: string } }) => setF({ ...f, [k]: e.target.value }),
  })

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onSave(f)
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(err instanceof Error ? err.message : String(err), -1))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="grid max-w-3xl gap-4 pt-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Field label="Opened (ET)">
          <input type="datetime-local" required disabled={editing} className={input} {...bind('opened_at')} />
        </Field>
        <Field label="Symbol">
          <select disabled={editing} className={input} {...bind('symbol')}>
            {symbols.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </Field>
        <Field label="Side">
          <select className={input} {...bind('side')}>
            <option value="long">Long</option>
            <option value="short">Short</option>
          </select>
        </Field>
        <Field label="Contracts">
          <input inputMode="numeric" className={input} {...bind('size')} />
        </Field>
        <Field label="Entry">
          <input inputMode="decimal" className={input} {...bind('entry')} />
        </Field>
        <Field label="Stop">
          <input inputMode="decimal" className={input} {...bind('stop')} />
        </Field>
        <Field label="Target">
          <input inputMode="decimal" className={input} {...bind('target')} />
        </Field>
        <Field label="Fees">
          <input inputMode="decimal" className={input} {...bind('fees')} />
        </Field>
        {editing && (
          <>
            <Field label="Exit">
              <input inputMode="decimal" className={input} {...bind('exit')} />
            </Field>
            <Field label="Closed (ET)">
              <input type="datetime-local" className={input} {...bind('closed_at')} />
            </Field>
          </>
        )}
        <Field label="Account">
          <input className={input} {...bind('account')} />
        </Field>
        <Field label="Stage">
          <select className={input} {...bind('stage')}>
            <option value="">None</option>
            <option value="backtest">Backtest</option>
            <option value="forward_test">Forward test</option>
            <option value="eval">Eval</option>
            <option value="funded">Funded</option>
            <option value="live">Live</option>
          </select>
        </Field>
        <Field label="Strategy">
          <input className={input} {...bind('strategy')} />
        </Field>
        <Field label="Grade">
          <select className={input} {...bind('grade')}>
            <option value="">None</option>
            {['A', 'B', 'C', 'E'].map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Tags, comma-separated">
        <input className={input} {...bind('tags')} />
      </Field>
      <Field label="Notes">
        <textarea rows={5} className={`${input} font-sans`} {...bind('notes')} />
      </Field>
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="rounded-sm bg-brand px-3 py-1.5 font-mono text-[10px] font-medium tracking-widest text-brand-fg uppercase">
          Save entry
        </button>
        <button type="button" onClick={onCancel} className="rounded-sm border px-3 py-1.5 font-mono text-[10px] font-medium tracking-widest uppercase">
          Cancel
        </button>
      </div>
      {error && <ErrorLine error={error} />}
    </form>
  )
}
