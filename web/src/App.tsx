import { useState } from 'react'
import { Chart } from './components/Chart'
import { TopBar } from './components/TopBar'
import { TIMEFRAMES, type Tf } from './lib/chart'
import { get, set } from './lib/storage'

const storedTf = (): Tf => {
  const t = get('apollo.tf', '5m') as Tf
  return TIMEFRAMES.some((x) => x.tf === t) ? t : '5m'
}

export default function App() {
  const [symbol] = useState(() => get('apollo.symbol', 'MNQ'))
  const [tf, setTf] = useState<Tf>(storedTf)
  const [trades, setTrades] = useState(() => get('apollo.trades', 'on') !== 'off')

  return (
    <div className="grid h-[100dvh] grid-rows-[auto_1fr_auto] overflow-hidden bg-bg text-ink">
      <TopBar
        tf={tf}
        onTf={(t) => (setTf(t), set('apollo.tf', t))}
        trades={trades}
        onTrades={(on) => (setTrades(on), set('apollo.trades', on ? 'on' : 'off'))}
        left={<span className="text-base font-semibold tracking-tight uppercase">Apollo</span>}
      />
      <main className="grid min-h-0 grid-cols-1 md:grid-cols-[1fr_260px]">
        <Chart symbol={symbol} tf={tf} />
        <aside className="border-t md:border-t-0 md:border-l" />
      </main>
      <footer className="flex justify-between border-t px-5 py-2.5 font-mono text-[11px] text-muted">
        <span>Research tool. Not financial advice.</span>
        <span>Data: Yahoo Finance</span>
      </footer>
    </div>
  )
}
