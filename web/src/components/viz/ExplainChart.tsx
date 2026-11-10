import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import { useEffect, useRef } from 'react'
import type { Bar } from '../../api/types'
import { candleColours, palette, snapTo, token } from '../../lib/chart'

export type Mark = { time: number; text: string; position: 'aboveBar' | 'belowBar'; tone: 'ink' | 'brand' | 'down' }
export type Level = { price: number; title: string; tone: 'ink' | 'brand' | 'down' | 'muted'; dashed?: boolean }

type Props = { bars: Bar[]; markers: Mark[]; lines: Level[]; label: string }

/** A static candlestick chart with markers and price lines, redrawn as the explainer steps. */
export function ExplainChart({ bars, markers, lines, label }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const ref = useRef<{ chart: IChartApi; series: ISeriesApi<'Candlestick'>; marks: ISeriesMarkersPluginApi<Time>; lines: IPriceLine[] } | null>(null)

  useEffect(() => {
    if (!box.current) return
    const css = getComputedStyle(document.documentElement)
    const chart = createChart(box.current, {
      autoSize: true,
      handleScroll: false,
      handleScale: false,
      layout: { background: { color: token(css, 'bg') }, textColor: token(css, 'muted'), fontFamily: 'Geist Mono Variable, monospace' },
      grid: { vertLines: { color: token(css, 'line') }, horzLines: { color: token(css, 'line') } },
      timeScale: { timeVisible: true, borderColor: token(css, 'line') },
      rightPriceScale: { borderColor: token(css, 'line') },
    })
    const series = chart.addSeries(CandlestickSeries, candleColours(css))
    ref.current = { chart, series, marks: createSeriesMarkers(series, []), lines: [] }
    return () => {
      chart.remove()
      ref.current = null
    }
  }, [])

  useEffect(() => {
    const c = ref.current
    if (!c) return
    c.series.setData(bars.map((b) => ({ ...b, time: b.time as UTCTimestamp })))
    c.chart.timeScale().fitContent()
  }, [bars])

  useEffect(() => {
    const c = ref.current
    if (!c) return
    const css = getComputedStyle(document.documentElement)
    const pal = { ...palette(css), muted: token(css, 'muted') }
    const times = bars.map((b) => b.time)
    c.marks.setMarkers(
      markers.flatMap((m) => {
        const at = snapTo(times, m.time)
        return at === null
          ? []
          : [{ time: at as UTCTimestamp, text: m.text, position: m.position, color: pal[m.tone], shape: m.position === 'aboveBar' ? ('arrowDown' as const) : ('arrowUp' as const) }]
      }),
    )
    for (const l of c.lines) c.series.removePriceLine(l)
    c.lines = lines.map((l) =>
      c.series.createPriceLine({ price: l.price, title: l.title, color: pal[l.tone], lineWidth: 1, lineStyle: l.dashed ? 2 : 0, axisLabelVisible: true }),
    )
  }, [bars, markers, lines])

  return <div ref={box} role="img" aria-label={label} className="h-[320px] w-full" />
}
