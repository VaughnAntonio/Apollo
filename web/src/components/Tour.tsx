import { useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react'
import { TOUR_STEPS, markTourDone, type TourStep } from '../lib/tour'

type Props = { open: boolean; onClose: () => void }
type Box = { top: number; left: number; width: number; height: number }

const PAD = 6
const POP_W = 320

function find(step: TourStep): HTMLElement | null {
  const el = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`)
  if (!el || el.closest('[hidden]') || getComputedStyle(el).display === 'none') return null
  return el
}

/** A spotlight tour: dims the page, cuts a hole around each target and explains it in a popover. */
export function Tour({ open, onClose }: Props) {
  // k indexes TOUR_STEPS. Targets are looked up at each move, because some (the model check rows)
  // only appear once their data loads.
  const [k, setK] = useState<number | null>(null)
  const [box, setBox] = useState<Box | null>(null)
  const pop = useRef<HTMLDivElement>(null)
  const step = k === null ? undefined : TOUR_STEPS[k]
  const present = TOUR_STEPS.map((s) => open && find(s) !== null)
  const seek = (from: number, dir: 1 | -1) => {
    for (let j = from; j >= 0 && j < TOUR_STEPS.length; j += dir) if (find(TOUR_STEPS[j])) return j
    return null
  }

  const close = () => {
    markTourDone()
    onClose()
  }

  useLayoutEffect(() => {
    if (!open) return setK(null)
    const first = seek(0, 1)
    setK(first)
    if (first === null) close()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  useLayoutEffect(() => {
    if (!open || !step) return
    const el = find(step)
    if (!el) return
    el.scrollIntoView?.({ block: 'center' })
    const measure = () => {
      const r = el.getBoundingClientRect()
      setBox({ top: r.top - PAD, left: r.left - PAD, width: r.width + PAD * 2, height: r.height + PAD * 2 })
    }
    measure()
    window.addEventListener('resize', measure)
    window.addEventListener('scroll', measure, true)
    pop.current?.querySelector<HTMLButtonElement>('[data-next]')?.focus()
    return () => {
      window.removeEventListener('resize', measure)
      window.removeEventListener('scroll', measure, true)
    }
  }, [open, step])

  if (!open || !step || k === null) return null

  const next = seek(k + 1, 1)
  const back = seek(k - 1, -1)
  const last = next === null
  const at = present.slice(0, k + 1).filter(Boolean).length
  const total = present.filter(Boolean).length
  const keys = (e: KeyboardEvent) => {
    if (e.key === 'Escape') close()
    if (e.key !== 'Tab') return
    const items = [...(pop.current?.querySelectorAll<HTMLButtonElement>('button') ?? [])]
    const at = items.indexOf(document.activeElement as HTMLButtonElement)
    const next = (at + (e.shiftKey ? -1 : 1) + items.length) % items.length
    e.preventDefault()
    items[next]?.focus()
  }

  const vw = window.innerWidth
  const vh = window.innerHeight
  const b = box ?? { top: vh / 2, left: vw / 2, width: 0, height: 0 }
  const below = b.top + b.height + 180 < vh
  const left = Math.max(12, Math.min(b.left, vw - POP_W - 12))
  const top = below ? b.top + b.height + 10 : Math.max(12, b.top - 10)

  return (
    <div className="fixed inset-0 z-[60]">
      <svg aria-hidden="true" className="absolute inset-0 h-full w-full" onClick={close}>
        <defs>
          <mask id="tour-hole">
            <rect width="100%" height="100%" fill="white" />
            <rect x={b.left} y={b.top} width={b.width} height={b.height} rx={4} fill="black" />
          </mask>
        </defs>
        <rect width="100%" height="100%" fill="var(--bg)" opacity={0.6} mask="url(#tour-hole)" />
        <rect x={b.left} y={b.top} width={b.width} height={b.height} rx={4} fill="none" stroke="var(--brand)" />
      </svg>
      <div
        ref={pop}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        onKeyDown={keys}
        className="absolute grid gap-2 rounded-sm border bg-panel p-4 shadow-lg"
        style={{ left, top, width: POP_W, transform: below ? undefined : 'translateY(-100%)' }}
      >
        <span className="font-mono text-[10px] tracking-widest text-muted uppercase">{`${at} of ${total}`}</span>
        <h2 id="tour-title" className="text-[15px] font-semibold">
          {step.title}
        </h2>
        <p className="text-muted">{step.body}</p>
        <div className="mt-1 flex items-center gap-2">
          <button type="button" onClick={close} className="mr-auto font-mono text-[10px] tracking-widest text-muted uppercase hover:text-ink">
            Skip tour
          </button>
          <button
            type="button"
            disabled={back === null}
            onClick={() => back !== null && setK(back)}
            className="rounded-sm border px-3 py-1.5 font-mono text-[10px] font-medium tracking-widest uppercase disabled:opacity-40"
          >
            Back
          </button>
          <button
            type="button"
            data-next
            onClick={() => (next === null ? close() : setK(next))}
            className="rounded-sm bg-brand px-3 py-1.5 font-mono text-[10px] font-medium tracking-widest text-brand-fg uppercase"
          >
            {last ? 'Done' : 'Next'}
          </button>
        </div>
      </div>
    </div>
  )
}
