import { Dialog } from 'radix-ui'
import { useEffect, useState, type CSSProperties, type MouseEvent } from 'react'
import { isStatic } from '../lib/mode'
import { useTheme, type Theme } from '../lib/theme'
import { EndMark } from './EndMark'
import { Wordmark } from './Wordmark'

export type Page = 'chart' | 'backtest' | 'models' | 'case-study' | 'guide'
const PAGES: Page[] = ['chart', 'backtest', 'models', 'case-study', 'guide']

const pageFromHash = (): Page => {
  const p = location.hash.replace(/^#\//, '') as Page
  return PAGES.includes(p) ? p : 'chart'
}

export function useHashPage(): [Page, (p: Page) => void] {
  const [page, setPage] = useState<Page>(pageFromHash)
  useEffect(() => {
    const on = () => setPage(pageFromHash())
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  const go = (p: Page) => {
    location.hash = `#/${p}`
    setPage(p)
  }
  return [page, go]
}

type Tile = { n: string; label: string; page?: Page }
const TILES: Tile[] = [
  { n: '01', label: 'Chart', page: 'chart' },
  { n: '02', label: 'Journal' },
  { n: '03', label: 'Backtest', page: 'backtest' },
  { n: '04', label: 'Models', page: 'models' },
  { n: '05', label: 'Case study', page: 'case-study' },
  { n: '06', label: 'Guide', page: 'guide' },
]
const THEMES: { t: Theme; label: string }[] = [
  { t: 'light', label: 'Light' },
  { t: 'dark', label: 'Dark' },
  { t: 'auto', label: 'Auto' },
]

type Props = { page: Page; onNavigate: (p: Page) => void; onJournal: () => void; onNewEntry: () => void }

// Portfoliov2's MobileNav, used at every width: the panel wipes down from the top, then each tile
// slides up out of its box with a slight tilt, staggered. Closing plays it in reverse. The keyframes
// are in index.css ([data-menu]); Radix waits for the exit animation before unmounting.
export function Menu({ page, onNavigate, onJournal, onNewEntry }: Props) {
  const [open, setOpen] = useState(false)
  const [theme, setTheme] = useTheme()
  const count = TILES.length + 2 // tiles + theme + new entry
  const stagger = (i: number) => ({ '--i': i, '--r': count - 1 - i }) as CSSProperties

  const choose = (tile: Tile) => (e: MouseEvent) => {
    e.preventDefault()
    setOpen(false)
    if (tile.page) onNavigate(tile.page)
    else onJournal()
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger
        aria-label="Open menu"
        data-tour="journal"
        className="group flex size-9 shrink-0 flex-col items-center justify-center gap-[5px] rounded-sm border border-ink/70 hover:border-brand hover:text-brand"
      >
        {/* Mecha hamburger: the outer bars shrink to half on hover. */}
        <span className="h-px w-4 bg-current motion-safe:transition-transform motion-safe:duration-500 ease-[cubic-bezier(0.7,0,0.3,1)] group-hover:scale-x-50" />
        <span className="h-px w-4 bg-current" />
        <span className="h-px w-4 bg-current motion-safe:transition-transform motion-safe:duration-500 ease-[cubic-bezier(0.7,0,0.3,1)] group-hover:scale-x-50" />
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Content
          aria-describedby={undefined}
          data-menu
          className="fixed inset-0 z-50 flex h-dvh flex-col bg-soft px-5 text-ink"
        >
          <Dialog.Title className="sr-only">Menu</Dialog.Title>
          <div className="flex items-center justify-between border-b py-3.5">
            <Wordmark />
            <Dialog.Close className="flex items-center gap-3 py-1.5 text-[15px] hover:text-brand">
              Close
              <EndMark className="size-6" />
            </Dialog.Close>
          </div>

          <nav aria-label="Pages" className="mt-auto">
            <ul className="grid grid-cols-2 gap-2 md:grid-cols-6">
              {TILES.map((tile, i) => (
                <li
                  key={tile.label}
                  className="group/tile overflow-hidden border hover:border-brand/50 motion-safe:transition-colors motion-safe:duration-500 has-[a[aria-current]]:border-brand/40"
                >
                  <a
                    href={tile.page ? `#/${tile.page}` : '#journal'}
                    aria-current={tile.page === page ? 'page' : undefined}
                    onClick={choose(tile)}
                    style={stagger(i)}
                    data-menu-item
                    className="relative flex items-baseline gap-2 px-4 py-7 text-[15px] leading-snug hover:text-brand aria-[current]:text-brand motion-safe:transition-colors motion-safe:duration-300"
                  >
                    {/* hover: a faint brand fill rises from the bottom, the label steps right, an arrow slides in */}
                    <span
                      aria-hidden="true"
                      className="pointer-events-none absolute inset-0 origin-bottom scale-y-0 bg-brand/[0.08] group-hover/tile:scale-y-100 motion-safe:transition-transform motion-safe:duration-500 ease-[cubic-bezier(0.7,0,0.3,1)]"
                    />
                    <span className="relative font-mono text-[11px] text-muted group-hover/tile:text-brand motion-safe:transition-colors motion-safe:duration-300">
                      {tile.n}
                    </span>
                    <span className="relative group-hover/tile:translate-x-1 motion-safe:transition-transform motion-safe:duration-500 ease-[cubic-bezier(0.7,0,0.3,1)]">
                      {tile.label}
                    </span>
                    <svg
                      aria-hidden="true"
                      viewBox="0 0 12 12"
                      className="relative ml-auto size-3 self-center -translate-x-2 opacity-0 group-hover/tile:translate-x-0 group-hover/tile:opacity-100 motion-safe:transition-[translate,opacity] motion-safe:duration-500 ease-[cubic-bezier(0.7,0,0.3,1)]"
                    >
                      <path d="M1 6h9M6.5 2.5 10 6l-3.5 3.5" fill="none" stroke="currentColor" strokeWidth="1.2" />
                    </svg>
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <div className="mt-2 mb-5 grid grid-cols-1 gap-2 md:grid-cols-[1fr_2fr]">
            <div className="overflow-hidden">
              <div style={stagger(TILES.length)} data-menu-item className="flex h-36 flex-col justify-between border p-5">
                <span className="font-mono text-[10px] font-medium tracking-widest text-muted uppercase">Theme</span>
                <div className="flex self-start overflow-hidden rounded-sm border">
                  {THEMES.map(({ t, label }) => (
                    <button
                      key={t}
                      type="button"
                      aria-pressed={theme === t}
                      onClick={() => setTheme(t)}
                      className="px-3 py-1.5 font-mono text-[10px] font-medium tracking-wider text-muted uppercase hover:text-ink aria-pressed:bg-ink aria-pressed:text-bg motion-safe:transition-colors motion-safe:duration-300"
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </div>
            {!isStatic() && (
            <div className="overflow-hidden">
              <button
                type="button"
                onClick={() => (setOpen(false), onNewEntry())}
                style={stagger(TILES.length + 1)}
                data-menu-item
                className="flex h-36 w-full flex-col justify-between bg-brand p-5 text-left text-brand-fg hover:bg-brand/90"
              >
                <EndMark className="size-8 self-end" />
                <span className="text-lg">New journal entry</span>
              </button>
            </div>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
