import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  type IPriceLine,
  type ISeriesMarkersPluginApi,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { Bar, Entry } from '../api/types'
import { usePoll } from '../api/usePoll'
import { candleColours, dayDots, mergeBars, palette, snapTo, token, tradeLines, tradeMarkers, type Tf } from '../lib/chart'
import { crosshairLabel, tickLabel } from '../lib/time'
import { Empty, ErrorLine, Skeleton } from './State'

const sec = (t: Time) => t as number

function colours(chart: IChartApi, series: ISeriesApi<'Candlestick'>) {
  const css = getComputedStyle(document.documentElement)
  chart.applyOptions({
    layout: { background: { color: token(css, 'bg') }, textColor: token(css, 'muted'), fontFamily: 'Geist Mono Variable, monospace' },
    grid: { vertLines: { color: token(css, 'line') }, horzLines: { color: token(css, 'line') } },
    rightPriceScale: { borderColor: token(css, 'line') },
    timeScale: { borderColor: token(css, 'line') },
  })
  series.applyOptions(candleColours(css))
}

type Props = {
  symbol: string
  tf: Tf
  entries?: Entry[]
  openTrade?: Entry | null
  trades?: boolean
  onLastClose?: (close: number | null) => void
  onMarkerClick?: (id: number) => void
}

export function Chart({ symbol, tf, entries = [], openTrade = null, trades = true, onLastClose, onMarkerClick }: Props) {
  const [themeTick, setThemeTick] = useState(0)
  const drawn = useRef<{ lines: IPriceLine[]; markers: ISeriesMarkersPluginApi<Time> | null; ids: Map<number, number> }>({
    lines: [],
    markers: null,
    ids: new Map(),
  })
  const clickRef = useRef(onMarkerClick)
  const tfRef = useRef(tf)
  tfRef.current = tf
  clickRef.current = onMarkerClick
  const box = useRef<HTMLDivElement>(null)
  const chartRef = useRef<{ chart: IChartApi; series: ISeriesApi<'Candlestick'> } | null>(null)
  const bars = useRef<{ key: string; list: Bar[] }>({ key: '', list: [] })
  // what the series holds; only the draw effect writes it
  const drawnTo = useRef<{ key: string; time: number }>({ key: '', time: 0 })
  const seq = useRef(0)
  const key = `${symbol}|${tf}`

  const poll = usePoll(
    async () => {
      const mine = ++seq.current
      const start = bars.current.key === key ? bars.current : { key, list: [] }
      const fresh = await api.bars(symbol, tf, start.list.at(-1)?.time)
      if (mine !== seq.current) return bars.current.list // a newer poll started meanwhile; it wins
      bars.current = { key, list: mergeBars(start.list, fresh) }
      return bars.current.list
    },
    [key],
  )

  useEffect(() => {
    if (!box.current) return
    const chart = createChart(box.current, {
      autoSize: true,
      localization: { timeFormatter: (t: Time) => crosshairLabel(sec(t), tfRef.current) },
      timeScale: {
        timeVisible: true,
        tickMarkFormatter: (t: Time, type: number) => tickLabel(sec(t), type),
      },
    })
    const series = chart.addSeries(CandlestickSeries, {})
    chartRef.current = { chart, series }
    drawn.current.markers = createSeriesMarkers(series, [])
    // a click on a bar that carries a trade marker opens that trade
    chart.subscribeClick((param) => {
      const id = param.time === undefined ? undefined : drawn.current.ids.get(sec(param.time))
      if (id !== undefined) clickRef.current?.(id)
    })
    colours(chart, series)
    const recolour = () => (colours(chart, series), setThemeTick((n) => n + 1))
    const watch = new MutationObserver(recolour)
    watch.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    const media = window.matchMedia?.('(prefers-color-scheme: dark)')
    media?.addEventListener('change', recolour)
    return () => {
      watch.disconnect()
      media?.removeEventListener('change', recolour)
      chart.remove()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    const c = chartRef.current
    const list = poll.data
    if (!c || !list || bars.current.key !== key) return
    const data = list.map((b) => ({ ...b, time: b.time as UTCTimestamp }))
    const last = list.at(-1)?.time ?? 0
    const at = drawnTo.current
    if (at.key !== key || last < at.time) {
      c.series.setData(data) // a new symbol or timeframe, or a shorter list: redraw everything
      if (at.key !== key) c.chart.timeScale().fitContent()
    } else {
      for (const b of data) if (b.time >= at.time) c.series.update(b) // lightweight-charts refuses older times
    }
    drawnTo.current = { key, time: last }
  }, [poll.data, key])

  useEffect(() => {
    const c = chartRef.current
    const list = poll.data
    if (!c || !list) return
    const pal = palette(getComputedStyle(document.documentElement))
    for (const l of drawn.current.lines) c.series.removePriceLine(l)
    drawn.current.lines = (openTrade && openTrade.symbol === symbol ? tradeLines(openTrade, pal) : []).map((l) =>
      c.series.createPriceLine({ ...l, lineWidth: 1, axisLabelVisible: true }),
    )
    const times = list.map((b) => b.time)
    const specs = trades ? [...tradeMarkers(entries, symbol, tf, pal), ...dayDots(entries, symbol, tf, pal)] : []
    const ids = new Map<number, number>()
    const markers = specs.flatMap(({ id, time, ...m }) => {
      const at = snapTo(times, time)
      if (at === null) return []
      ids.set(at, id)
      return [{ ...m, time: at as UTCTimestamp }]
    })
    drawn.current.ids = ids
    drawn.current.markers?.setMarkers(markers.sort((a, b) => a.time - b.time))
  }, [poll.data, entries, openTrade, trades, symbol, tf, themeTick])

  const lastClose = poll.data?.at(-1)?.close ?? null
  useEffect(() => onLastClose?.(lastClose), [lastClose, onLastClose])

  const empty = poll.data !== undefined && poll.data.length === 0
  return (
    <div className="relative min-h-[440px] min-w-0">
      <div ref={box} className="absolute inset-0" />
      {poll.error && !!poll.data?.length && (
        <div className="absolute top-2 left-3 z-10 bg-bg/90 px-2 py-1">
          <ErrorLine error={poll.error} />
        </div>
      )}
      {(poll.loading && !poll.data) || empty || (poll.error && !poll.data?.length) ? (
        <div className="absolute inset-0 z-10 grid place-items-center bg-bg p-6">
          {poll.error && !poll.data?.length ? (
            <ErrorLine error={poll.error} />
          ) : empty ? (
            <Empty>{`No ${tf} bars for ${symbol} yet`}</Empty>
          ) : (
            <div className="w-48">
              <Skeleton rows={3} />
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
