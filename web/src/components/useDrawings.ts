import type { IChartApi, ISeriesApi } from 'lightweight-charts'
import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'
import {
  type Anchor,
  type Drawing,
  type Tool,
  TWO_POINT,
  handleAt,
  hitTest,
  loadDrawings,
  moveAnchor,
  moveDrawing,
  newId,
  saveDrawings,
} from '../lib/draw'
import { DrawingsPrimitive, type DrawColours } from '../lib/drawPrimitive'

type ChartRef = RefObject<{ chart: IChartApi; series: ISeriesApi<'Candlestick'> } | null>
type Drag =
  | { mode: 'create'; x: number; y: number }
  | { mode: 'move'; from: Anchor; orig: Drawing }
  | { mode: 'end'; id: string; end: 'a' | 'b' }

const DRAG_PX = 4 // a press that moves further than this is a drag, not a click

/**
 * Everything between the pointer and the drawings: placing, selecting, moving, deleting and
 * saving them. Sets `busy` while a press belongs to a drawing, so the chart's own click handler
 * (trade markers) can ignore it. Returns what the toolbar needs.
 */
export function useDrawings(
  box: RefObject<HTMLDivElement | null>,
  chartRef: ChartRef,
  symbol: string,
  times: number[],
  colours: DrawColours,
  busy: { current: boolean },
) {
  const [tool, setTool] = useState<Tool>('cursor')
  const [drawings, setDrawings] = useState<Drawing[]>(() => loadDrawings(symbol))
  const [selected, setSelected] = useState<string | null>(null)
  const [preview, setPreview] = useState<Drawing | null>(null)
  const prim = useRef<DrawingsPrimitive | null>(null)
  const live = useRef({ tool, drawings, selected, preview, symbol })
  live.current = { tool, drawings, selected, preview, symbol }

  // a new symbol brings its own drawings
  const [shown, setShown] = useState(symbol)
  if (shown !== symbol) {
    setShown(symbol)
    setDrawings(loadDrawings(symbol))
    setSelected(null)
    setPreview(null)
  }

  const commit = useCallback((list: Drawing[]) => {
    setDrawings(list)
    saveDrawings(live.current.symbol, list)
  }, [])

  useEffect(() => {
    const c = chartRef.current
    if (!c) return
    const p = new DrawingsPrimitive()
    c.series.attachPrimitive(p)
    prim.current = p
    return () => {
      prim.current = null
      try {
        c.series.detachPrimitive(p)
      } catch {
        // the chart was removed first; the primitive went with it
      }
    }
  }, [chartRef])

  useEffect(() => {
    prim.current?.update({ drawings, selected, preview, times, colours })
  }, [drawings, selected, preview, times, colours])

  useEffect(() => {
    const el = box.current
    if (!el) return
    let drag: Drag | null = null

    const local = (e: PointerEvent) => {
      const r = el.getBoundingClientRect()
      return { x: e.clientX - r.left, y: e.clientY - r.top }
    }
    const inPane = (x: number, y: number) => {
      const size = prim.current?.pane()
      return !!size && x >= 0 && y >= 0 && x <= size.width && y <= size.height
    }
    const hold = (on: boolean) => chartRef.current?.chart.applyOptions({ handleScroll: !on, handleScale: !on })
    const finish = (d: Drawing) => {
      commit([...live.current.drawings, d])
      setSelected(d.id)
      setPreview(null)
      setTool('cursor')
    }

    const down = (e: PointerEvent) => {
      const p = prim.current
      if (e.button !== 0 || !p) return
      const { x, y } = local(e)
      busy.current = false
      if (!inPane(x, y)) return
      const { tool, drawings, selected, preview } = live.current
      const at = p.toAnchor(x, y)
      if (tool !== 'cursor') {
        if (!at) return
        busy.current = true
        hold(true)
        if (preview) finish({ ...preview, b: at }) // the second click of a two-click drawing
        else if (TWO_POINT.has(tool)) {
          setPreview({ id: newId(), kind: tool, a: at, b: at })
          drag = { mode: 'create', x, y }
        } else finish({ id: newId(), kind: tool, a: at })
        return
      }
      const px = p.pixels()
      const sel = selected ? px.find((d) => d.id === selected) : undefined
      const end = sel ? handleAt(sel, x, y) : null
      if (sel && end) drag = { mode: 'end', id: sel.id, end }
      else {
        const id = hitTest(px, x, y, p.pane()!)
        setSelected(id)
        const orig = drawings.find((d) => d.id === id)
        if (!orig || !at) return // empty chart: let it pan
        drag = { mode: 'move', from: at, orig }
      }
      busy.current = true
      hold(true)
    }

    const move = (e: PointerEvent) => {
      const p = prim.current
      if (!p) return
      const { x, y } = local(e)
      const { tool, preview, drawings, selected } = live.current
      const at = p.toAnchor(x, y)
      if (preview && at) setPreview({ ...preview, b: at })
      else if (drag?.mode === 'move' && at) {
        const { from, orig } = drag
        const next = moveDrawing(orig, at.time - from.time, at.price - from.price)
        setDrawings(drawings.map((d) => (d.id === orig.id ? next : d)))
      } else if (drag?.mode === 'end' && at) {
        const { id, end } = drag
        setDrawings(drawings.map((d) => (d.id === id ? moveAnchor(d, end, at) : d)))
      }
      // the pointer says what a press would do
      let cursor = ''
      if (tool !== 'cursor') cursor = inPane(x, y) ? 'crosshair' : ''
      else if (drag) cursor = drag.mode === 'end' ? 'grabbing' : 'move'
      else if (inPane(x, y)) {
        const px = p.pixels()
        const sel = selected ? px.find((d) => d.id === selected) : undefined
        if (sel && handleAt(sel, x, y)) cursor = 'grab'
        else if (hitTest(px, x, y, p.pane()!)) cursor = 'move'
      }
      el.style.cursor = cursor
    }

    const up = (e: PointerEvent) => {
      hold(false) // the chart pans and zooms again, whatever the press was
      if (!drag) return
      const { x, y } = local(e)
      const { preview, drawings } = live.current
      if (drag.mode === 'create') {
        // a drag places the second end where it was let go; a click waits for a second click
        const at = prim.current?.toAnchor(x, y)
        if (preview && at && Math.hypot(x - drag.x, y - drag.y) > DRAG_PX) finish({ ...preview, b: at })
      } else commit(drawings) // a move or a dragged end, saved once at the end
      drag = null
    }

    el.addEventListener('pointerdown', down, true)
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    return () => {
      el.removeEventListener('pointerdown', down, true)
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
      hold(false)
    }
  }, [box, chartRef, commit])

  const remove = useCallback(() => {
    const { selected, drawings } = live.current
    if (!selected) return
    commit(drawings.filter((d) => d.id !== selected))
    setSelected(null)
  }, [commit])

  const clear = useCallback(() => {
    commit([])
    setSelected(null)
  }, [commit])

  // Escape drops a half-made drawing and goes back to the cursor; Delete removes the selected one
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (t?.closest('input, textarea, select, [contenteditable="true"], [role="dialog"]')) return
      if (e.key === 'Escape') {
        setPreview(null)
        setSelected(null)
        setTool('cursor')
      } else if ((e.key === 'Delete' || e.key === 'Backspace') && live.current.selected) {
        e.preventDefault()
        remove()
      }
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [remove])

  const pick = useCallback((t: Tool) => {
    setPreview(null)
    setTool(t)
  }, [])

  return { tool, setTool: pick, selected: selected !== null, count: drawings.length, remove, clear }
}
