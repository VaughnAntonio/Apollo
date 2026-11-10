import {
  CandlestickSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import { useEffect, useRef } from 'react'
import { api } from '../api/client'
import type { Bar } from '../api/types'
import { usePoll } from '../api/usePoll'
import { candleColours, mergeBars, token, type Tf } from '../lib/chart'
import { nyDate, nyDay, nyTime } from '../lib/time'
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

type Props = { symbol: string; tf: Tf; onLastClose?: (close: number | null) => void }

export function Chart({ symbol, tf, onLastClose }: Props) {
  const box = useRef<HTMLDivElement>(null)
  const chartRef = useRef<{ chart: IChartApi; series: ISeriesApi<'Candlestick'> } | null>(null)
  const bars = useRef<{ key: string; list: Bar[]; drawn: number }>({ key: '', list: [], drawn: 0 })
  const key = `${symbol}|${tf}`

  const poll = usePoll(
    async () => {
      const mine = bars.current.key === key ? bars.current : { key, list: [], drawn: 0 }
      const last = mine.list.at(-1)?.time
      const fresh = await api.bars(symbol, tf, last)
      bars.current = { ...mine, list: mergeBars(mine.list, fresh) }
      return bars.current.list
    },
    [key],
  )

  useEffect(() => {
    if (!box.current) return
    const chart = createChart(box.current, {
      autoSize: true,
      localization: { timeFormatter: (t: Time) => `${nyDate(sec(t))} ${nyTime(sec(t))}` },
      timeScale: {
        timeVisible: true,
        // tick types 0–2 are year, month and day; the rest are times of day
        tickMarkFormatter: (t: Time, type: number) => (type <= 2 ? nyDay(sec(t)) : nyTime(sec(t))),
      },
    })
    const series = chart.addSeries(CandlestickSeries, {})
    chartRef.current = { chart, series }
    colours(chart, series)
    const recolour = () => colours(chart, series)
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
    if (bars.current.drawn === 0) {
      c.series.setData(data)
      c.chart.timeScale().fitContent()
    } else {
      const from = bars.current.drawn
      for (const b of data) if (b.time >= from) c.series.update(b) // lightweight-charts refuses older times
    }
    bars.current.drawn = list.at(-1)?.time ?? 0
  }, [poll.data, key])

  const lastClose = poll.data?.at(-1)?.close ?? null
  useEffect(() => onLastClose?.(lastClose), [lastClose, onLastClose])

  const empty = poll.data !== undefined && poll.data.length === 0
  return (
    <div className="relative min-h-[440px] min-w-0">
      <div ref={box} className="absolute inset-0" />
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
