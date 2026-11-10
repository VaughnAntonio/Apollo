import { useRef, useState, type ReactNode } from 'react'
import { api, ApiError, mediaUrl } from '../../api/client'
import { isStatic } from '../../lib/mode'
import type { Entry } from '../../api/types'
import { nyDateTime } from '../../lib/time'
import { fmtPrice, fmtR, fmtUsd, NOT_RECORDED } from '../../lib/trade'
import { ErrorLine } from '../State'

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="border-b py-3.5">
      <div className="mb-1.5 font-mono text-[10px] font-medium tracking-widest text-muted uppercase">{label}</div>
      <div className="font-mono">{children}</div>
    </div>
  )
}

const text = (x: string | number | null) => (x === null || x === '' ? NOT_RECORDED : String(x))
const btn = 'rounded-sm border px-3 py-1.5 font-mono text-[10px] font-medium tracking-widest uppercase'

type Snapshot = { signal?: Record<string, unknown>; checklist?: { step: string; status: string; detail: string }[] }

type Props = { entry: Entry; onEdit: () => void; onDeleted: () => void; onChanged: () => void }

export function TradeDetail({ entry: e, onEdit, onDeleted, onChanged }: Props) {
  const [confirm, setConfirm] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const file = useRef<HTMLInputElement>(null)
  const editable = e.source !== 'imported' && !isStatic()
  const snap = (e.model_snapshot ?? null) as Snapshot | null

  const run = async (f: () => Promise<unknown>, after: () => void) => {
    setError(null)
    try {
      await f()
      after()
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(String(err), -1))
    }
  }

  const upload = (f: File | undefined) => f && run(() => api.journal.screenshot(e.id, f), onChanged)

  return (
    <article>
      <div className="flex flex-wrap items-baseline gap-6 pt-7 pb-5">
        <h2 className="text-[28px] font-semibold tracking-tight">
          {`${e.side === null ? '' : e.side === 'long' ? 'Long ' : 'Short '}${e.symbol}`}
        </h2>
        <span className={`font-mono text-lg ${e.r === null ? 'text-muted' : e.r >= 0 ? 'text-brand' : 'text-down'}`}>
          {e.r === null ? 'Open' : fmtR(e.r)}
        </span>
        {editable && (
          <span className="ml-auto flex gap-2">
            <button type="button" className={btn} onClick={onEdit}>
              Edit
            </button>
            <button type="button" className={btn} onClick={() => setConfirm(true)}>
              Delete
            </button>
          </span>
        )}
      </div>
      {confirm && (
        <div role="alertdialog" aria-labelledby={`delete-${e.id}`} className="mb-4 flex flex-wrap items-center gap-3 border-y py-3">
          <span id={`delete-${e.id}`}>Delete this trade? This can't be undone.</span>
          <button type="button" autoFocus className={`${btn} border-down text-down`} onClick={() => run(() => api.journal.remove(e.id), onDeleted)}>
            Yes, delete
          </button>
          <button type="button" className={btn} onClick={() => setConfirm(false)}>
            Cancel
          </button>
        </div>
      )}
      <div className="grid grid-cols-2 border-t lg:grid-cols-4">
        <Field label="Entry">{fmtPrice(e.entry)}</Field>
        <Field label="Stop">{fmtPrice(e.stop)}</Field>
        <Field label="Initial stop">{fmtPrice(e.initial_stop)}</Field>
        <Field label="Target">{fmtPrice(e.target)}</Field>
        <Field label="Exit">{fmtPrice(e.exit)}</Field>
        <Field label="Contracts">{text(e.size)}</Field>
        <Field label="Fees">{e.fees === null || e.source === 'imported' ? NOT_RECORDED : fmtUsd(e.fees)}</Field>
        <Field label="P&L">
          {fmtUsd(e['pnl_$'])} {e.scaled && <span className="ml-1 rounded-sm border px-1 text-[10px] text-muted">Scaled</span>}
        </Field>
        <Field label="Account">{text(e.account)}</Field>
        <Field label="Stage">{text(e.stage?.replace('_', ' ') ?? null)}</Field>
        <Field label="Grade">{text(e.grade)}</Field>
        <Field label="Source">{e.source === 'imported' ? 'Case study' : e.source}</Field>
        <Field label="Opened (ET)">{e.source === 'imported' ? `${nyDateTime(e.opened_at).slice(0, 10)} (time not recorded)` : nyDateTime(e.opened_at)}</Field>
        <Field label="Closed (ET)">{e.closed_at ? nyDateTime(e.closed_at) : NOT_RECORDED}</Field>
        <Field label="Exit reason">{text(e.exit_reason?.replace('_auto', ' (auto)') ?? null)}</Field>
        <Field label="Tags">{e.tags.length ? e.tags.join(', ') : NOT_RECORDED}</Field>
      </div>

      {e.screenshot ? (
        <img src={mediaUrl(e.screenshot)} alt="Trade screenshot" className="mt-6 max-h-[420px] rounded-sm border" />
      ) : editable ? (
        <button
          type="button"
          onClick={() => file.current?.click()}
          onDragOver={(ev) => ev.preventDefault()}
          onDrop={(ev) => (ev.preventDefault(), upload(ev.dataTransfer.files[0]))}
          className="mt-6 grid h-40 w-full place-items-center rounded-sm border border-dashed text-muted"
        >
          Drop a PNG or JPEG screenshot, or click to choose one
        </button>
      ) : null}
      <input ref={file} type="file" accept="image/png,image/jpeg" hidden onChange={(ev) => upload(ev.target.files?.[0])} />

      <p className="mt-5 max-w-[65ch] leading-relaxed whitespace-pre-line text-muted">{e.notes || 'No notes'}</p>

      {snap?.checklist?.length ? (
        <section className="mt-6">
          <h3 className="mb-2 font-mono text-[10px] font-medium tracking-widest text-muted uppercase">What the model said at entry</h3>
          <ul className="grid gap-1 font-mono text-[11px]">
            {snap.checklist.map((r) => (
              <li key={r.step} className="flex justify-between gap-4 border-b py-1">
                <span>{r.step.replace('_', ' ')}</span>
                <span className="text-muted">{r.detail}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {error && <ErrorLine error={error} />}
    </article>
  )
}
