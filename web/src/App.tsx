import { useEffect, useMemo, useState } from 'react'
import { api } from './api/client'
import { usePoll } from './api/usePoll'
import { Chart } from './components/Chart'
import { Menu, useHashPage, type Page } from './components/Menu'
import { Placeholder } from './components/Placeholder'
import { Sheet } from './components/journal/Sheet'
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

const TITLES: Record<Exclude<Page, 'chart'>, string> = { backtest: 'Backtest', models: 'Models', 'case-study': 'Case study' }

export type SheetState = { open: boolean; mode: 'view' | 'new'; id: number | null }

export default function App() {
  const [page, go] = useHashPage()
  const [sheet, setSheet] = useState<SheetState>({ open: false, mode: 'view', id: null })
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
  // while a trade is open, let the API check later bars for its stop, target or flat time
  const openId = openTrade && openTrade.exit === null ? openTrade.id : null
  const refreshJournal = journal.refresh
  const autoClose = usePoll(
    async () => (openId === null ? { closed: [] } : api.journal.autoClose(symbol)),
    [openId, symbol],
  )
  useEffect(() => {
    if (autoClose.data?.closed.length) refreshJournal()
  }, [autoClose.data, refreshJournal])

  return (
    <div className="grid min-h-[100dvh] grid-rows-[auto_1fr_auto] bg-bg text-ink md:h-[100dvh] md:overflow-hidden">
      <TopBar
        chart={page === 'chart'}
        tf={tf}
        onTf={(t) => (setTf(t), set('apollo.tf', t))}
        trades={trades}
        onTrades={(on) => (setTrades(on), set('apollo.trades', on ? 'on' : 'off'))}
        left={
          <>
            <Menu
              page={page}
              onNavigate={go}
              onJournal={() => setSheet({ open: true, mode: 'view', id: null })}
              onNewEntry={() => setSheet({ open: true, mode: 'new', id: null })}
            />
            <Wordmark />
            <TickerPicker value={symbol} onChange={setSymbol} />
          </>
        }
      />
      {page === 'chart' ? (
        <main className="grid min-h-0 grid-cols-1 md:grid-cols-[1fr_260px]">
          <Chart
            symbol={symbol}
            tf={tf}
            entries={journal.data}
            openTrade={openTrade}
            trades={trades}
            onLastClose={setLastClose}
          onMarkerClick={(id) => setSheet({ open: true, mode: 'view', id })}
          />
          <Rail
            symbol={symbol}
            openTrade={openTrade}
            lastClose={lastClose}
            onTaken={journal.refresh}
            onChanged={journal.refresh}
          />
        </main>
      ) : (
        <main className="overflow-auto">
          <Placeholder title={TITLES[page]} />
        </main>
      )}
      <Sheet
        open={sheet.open}
        mode={sheet.mode}
        selectedId={sheet.id}
        symbol={symbol}
        onOpenChange={(open) => setSheet((s) => ({ ...s, open }))}
        onChanged={journal.refresh}
      />
      <footer className="flex flex-wrap justify-between gap-x-4 border-t px-5 py-2.5 font-mono text-[11px] text-muted">
        <span>Research tool. Not financial advice.</span>
        <span>Data: Yahoo Finance</span>
      </footer>
    </div>
  )
}
