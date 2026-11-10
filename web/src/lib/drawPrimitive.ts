import type { CanvasRenderingTarget2D } from 'fancy-canvas'
import type { IChartApi, ISeriesApi, ISeriesPrimitive, Logical, SeriesAttachedParameter, Time } from 'lightweight-charts'
import { type Anchor, type Drawing, type PxDrawing, fibPrices, logicalToTime, logicalToX, timeToLogical } from './draw'

export type DrawColours = { line: string; text: string; bg: string }

/**
 * Draws the chart drawings on the candle pane, above the candles. It also converts between
 * pane pixels and (time, price), since it is the one piece that holds the chart and series.
 */
export class DrawingsPrimitive implements ISeriesPrimitive<Time> {
  drawings: Drawing[] = []
  preview: Drawing | null = null
  selected: string | null = null
  times: number[] = []
  colours: DrawColours = { line: '#7fa68f', text: '#8b9099', bg: '#17191e' }
  private chart: IChartApi | null = null
  private series: ISeriesApi<'Candlestick'> | null = null
  private request: (() => void) | null = null
  private readonly views = [{ zOrder: () => 'top' as const, renderer: () => ({ draw: (t: CanvasRenderingTarget2D) => this.draw(t) }) }]

  attached(p: SeriesAttachedParameter<Time>) {
    this.chart = p.chart
    this.series = p.series as ISeriesApi<'Candlestick'>
    this.request = p.requestUpdate
  }

  detached() {
    this.chart = this.series = this.request = null
  }

  paneViews() {
    return this.views
  }

  update(patch: Partial<Pick<DrawingsPrimitive, 'drawings' | 'preview' | 'selected' | 'times' | 'colours'>>) {
    Object.assign(this, patch)
    this.request?.()
  }

  /** The pane's size in CSS pixels; clicks outside it (on the price or time axis) are not drawings. */
  pane(): { width: number; height: number } | null {
    if (!this.chart) return null
    const { width, height } = this.chart.paneSize(0)
    return { width, height }
  }

  toAnchor(x: number, y: number): Anchor | null {
    if (!this.chart || !this.series) return null
    const l = this.chart.timeScale().coordinateToLogical(x)
    const price = this.series.coordinateToPrice(y)
    const time = l === null ? null : logicalToTime(this.times, l)
    return time === null || price === null ? null : { time, price }
  }

  toPx(d: Drawing): PxDrawing | null {
    const a = this.point(d.a)
    const b = d.b ? this.point(d.b) : undefined
    return a && b !== null ? { id: d.id, kind: d.kind, a, ...(b ? { b } : {}) } : null
  }

  pixels(): PxDrawing[] {
    return this.drawings.flatMap((d) => this.toPx(d) ?? [])
  }

  private point(p: Anchor) {
    if (!this.chart || !this.series) return null
    const l = timeToLogical(this.times, p.time)
    const ts = this.chart.timeScale()
    const x = l === null ? null : logicalToX((i) => ts.logicalToCoordinate(i as Logical), l)
    const y = this.series.priceToCoordinate(p.price)
    return x === null || y === null ? null : { x, y }
  }

  private draw(target: CanvasRenderingTarget2D) {
    const all = this.preview ? [...this.drawings, this.preview] : this.drawings
    target.useMediaCoordinateSpace(({ context: c, mediaSize }) => {
      const { line, text, bg } = this.colours
      c.lineWidth = 1.25
      c.strokeStyle = line
      c.fillStyle = line
      c.font = '10px "Geist Mono Variable", monospace'
      for (const d of all) {
        const p = this.toPx(d)
        if (!p) continue
        const { a, b } = p
        c.beginPath()
        switch (d.kind) {
          case 'hline':
            c.moveTo(0, a.y)
            c.lineTo(mediaSize.width, a.y)
            c.stroke()
            label(c, d.a.price.toFixed(2), mediaSize.width - 4, a.y - 4, 'right', text)
            break
          case 'vline':
            c.moveTo(a.x, 0)
            c.lineTo(a.x, mediaSize.height)
            c.stroke()
            break
          case 'trend':
            c.moveTo(a.x, a.y)
            c.lineTo(b!.x, b!.y)
            c.stroke()
            break
          case 'ray': {
            const far = extend(a, b!, mediaSize.width, mediaSize.height)
            c.moveTo(a.x, a.y)
            c.lineTo(far.x, far.y)
            c.stroke()
            break
          }
          case 'rect': {
            const x = Math.min(a.x, b!.x)
            const y = Math.min(a.y, b!.y)
            const w = Math.abs(b!.x - a.x)
            const h = Math.abs(b!.y - a.y)
            c.globalAlpha = 0.12
            c.fillRect(x, y, w, h)
            c.globalAlpha = 1
            c.strokeRect(x, y, w, h)
            break
          }
          case 'fib': {
            const x0 = Math.min(a.x, b!.x)
            const x1 = Math.max(a.x, b!.x)
            let lastLabel = -Infinity
            for (const { level, price } of fibPrices(d.a, d.b!)) {
              const y = b!.y + (a.y - b!.y) * level
              c.globalAlpha = level === 0 || level === 1 ? 1 : 0.7
              c.beginPath()
              c.moveTo(x0, y)
              c.lineTo(x1, y)
              c.stroke()
              c.globalAlpha = 1
              if (Math.abs(y - lastLabel) < 12) continue // too close to the last label to read
              label(c, `${level} (${price.toFixed(2)})`, x0 + 4, y - 3, 'left', text)
              lastLabel = y
            }
            break
          }
        }
        if (d.id === this.selected || d === this.preview) {
          for (const h of b ? [a, b] : [a]) {
            c.beginPath()
            c.arc(h.x, h.y, 4, 0, Math.PI * 2)
            c.fillStyle = bg
            c.fill()
            c.stroke()
            c.fillStyle = line
          }
        }
      }
    })
  }
}

function label(c: CanvasRenderingContext2D, s: string, x: number, y: number, align: CanvasTextAlign, colour: string) {
  const fill = c.fillStyle
  c.fillStyle = colour
  c.textAlign = align
  c.fillText(s, x, y)
  c.fillStyle = fill
}

/** Where a ray from a through b leaves the pane. */
function extend(a: { x: number; y: number }, b: { x: number; y: number }, w: number, h: number) {
  const dx = b.x - a.x
  const dy = b.y - a.y
  if (!dx && !dy) return b
  const ts = [dx > 0 ? (w - a.x) / dx : dx < 0 ? -a.x / dx : Infinity, dy > 0 ? (h - a.y) / dy : dy < 0 ? -a.y / dy : Infinity]
  const t = Math.max(1, Math.min(...ts))
  return { x: a.x + t * dx, y: a.y + t * dy }
}
