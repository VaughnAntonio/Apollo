import { useMemo, useState } from 'react'
import { api } from './api/client'
import { usePoll } from './api/usePoll'
import { Chart } from './components/Chart'
import { Rail } from './components/Rail'
import { TickerPicker } from './components/TickerPicker'
import { TopBar } from './components/TopBar'
import { Wordmark } from './components/Wordmark'
import { TIMEFRAMES, type Tf } from './lib/chart'
import { get, set } from './lib/storage'

const storedTf = (): Tf => {
  const t = get('apollo.tf', '5m') as Tf
  return TIMEFRAMES.some((x) => x.tf === t) ? t : '5m'
}

export default function App() {
  const [symbol, setSymbol] = useState(() => get('apollo.symbol', 'MNQ'))
  const [tf, setTf] = useState<Tf>(storedTf)
  const [trades, setTrades] = useState(() => get('apollo.trades', 'on') !== 'off')
  const [lastClose, setLastClose] = useState<number | null>(null)
  const journal = usePoll(api.journal.list, [])
  // the trade still on the book for this symbol: not closed, or auto-closed and waiting for a confirm
  const openTrade = useMemo(
    () =>
      journal.data?.find(
        (e) => e.symbol === symbol && e.source !== 'imported' && (e.exit === null || e.needs_confirm),
      ) ?? null,
    [journal.data, symbol],
  )

  return (
    <div className="grid min-h-[100dvh] grid-rows-[auto_1fr_auto] bg-bg text-ink md:h-[100dvh] md:overflow-hidden">
      <TopBar
        tf={tf}
        onTf={(t) => (setTf(t), set('apollo.tf', t))}
        trades={trades}
        onTrades={(on) => (setTrades(on), set('apollo.trades', on ? 'on' : 'off'))}
        left={
          <>
            <Wordmark />
            <TickerPicker value={symbol} onChange={setSymbol} />
          </>
        }
      />
      <main className="grid min-h-0 grid-cols-1 md:grid-cols-[1fr_260px]">
        <Chart symbol={symbol} tf={tf} onLastClose={setLastClose} />
        <Rail
          symbol={symbol}
          openTrade={openTrade}
          lastClose={lastClose}
          onTaken={journal.refresh}
          onChanged={journal.refresh}
        />
      </main>
      <footer className="flex justify-between border-t px-5 py-2.5 font-mono text-[11px] text-muted">
        <span>Research tool. Not financial advice.</span>
        <span>Data: Yahoo Finance</span>
      </footer>
    </div>
  )
}
