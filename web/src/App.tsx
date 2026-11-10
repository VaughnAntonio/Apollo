import { useEffect, useMemo, useState } from 'react'
import { api } from './api/client'
import { usePoll } from './api/usePoll'
import { Chart } from './components/Chart'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Menu, useHashPage } from './components/Menu'
import { Backtest } from './components/pages/Backtest'
import { CaseStudy } from './components/pages/CaseStudy'
import { Guide } from './components/pages/Guide'
import { Models } from './components/pages/Models'
import { Sheet } from './components/journal/Sheet'
import { Rail } from './components/Rail'
import { TickerPicker } from './components/TickerPicker'
import { TopBar } from './components/TopBar'
import { Tour } from './components/Tour'
import { Wordmark } from './components/Wordmark'
import { TIMEFRAMES, type Tf } from './lib/chart'
import { isStatic } from './lib/mode'
import { get, set } from './lib/storage'
import { markTourDone, shouldOfferTour } from './lib/tour'

const storedTf = (): Tf => {
  const t = get('apollo.tf', '5m') as Tf
  return TIMEFRAMES.some((x) => x.tf === t) ? t : '5m'
}

export type SheetState = { open: boolean; mode: 'view' | 'new'; id: number | null }

export default function App() {
  const [page, go] = useHashPage()
  const [sheet, setSheet] = useState<SheetState>({ open: false, mode: 'view', id: null })
  const [symbol, setSymbol] = useState(() => get('apollo.symbol', 'MNQ'))
  const [tf, setTf] = useState<Tf>(storedTf)
  const [tour, setTour] = useState(false)
  const [offer, setOffer] = useState(shouldOfferTour)
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
  const openId = openTrade && openTrade.exit === null && !isStatic() ? openTrade.id : null
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
            <span data-tour="ticker">
              <TickerPicker value={symbol} onChange={setSymbol} />
            </span>
          </>
        }
      />
      {page === 'chart' ? (
        <main className="grid min-h-0 grid-cols-1 md:grid-cols-[1fr_260px]">
          <ErrorBoundary label="chart">
            <Chart
              symbol={symbol}
              tf={tf}
              entries={journal.data}
              openTrade={openTrade}
              trades={trades}
              onLastClose={setLastClose}
            onMarkerClick={(id) => setSheet({ open: true, mode: 'view', id })}
            />
          </ErrorBoundary>
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
          {page === 'backtest' ? (
            <Backtest symbol={symbol} />
          ) : page === 'models' ? (
            <Models symbol={symbol} />
          ) : page === 'guide' ? (
            <Guide onTour={() => (go('chart'), setOffer(false), setTour(true))} />
          ) : (
            <CaseStudy />
          )}
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
      <Tour open={tour} onClose={() => setTour(false)} />
      {offer && !tour && page === 'chart' && (
        <aside aria-label="Tour" className="fixed right-4 bottom-12 z-40 grid w-64 gap-3 rounded-sm border bg-panel p-4 shadow-lg">
          <p>New here? Take the 1-minute tour.</p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => (setOffer(false), setTour(true))}
              className="rounded-sm bg-brand px-3 py-1.5 font-mono text-[10px] font-medium tracking-widest text-brand-fg uppercase"
            >
              Start
            </button>
            <button
              type="button"
              onClick={() => (markTourDone(), setOffer(false))}
              className="rounded-sm border px-3 py-1.5 font-mono text-[10px] font-medium tracking-widest uppercase"
            >
              No thanks
            </button>
          </div>
        </aside>
      )}
      <footer className="flex flex-wrap justify-between gap-x-4 border-t px-5 py-2.5 font-mono text-[11px] text-muted">
        <span>Research tool. Not financial advice.</span>
        <span>Data: Yahoo Finance</span>
      </footer>
    </div>
  )
}
