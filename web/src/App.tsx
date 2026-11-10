export default function App() {
  return (
    <div className="grid min-h-[100dvh] grid-rows-[auto_1fr_auto] bg-bg text-ink">
      <header className="flex items-center gap-6 border-b px-5 py-3">
        <span className="text-base font-semibold tracking-tight uppercase">Apollo</span>
      </header>
      <main />
      <footer className="flex justify-between border-t px-5 py-2.5 font-mono text-[11px] text-muted">
        <span>Research tool. Not financial advice.</span>
        <span>Data: Yahoo Finance</span>
      </footer>
    </div>
  )
}
