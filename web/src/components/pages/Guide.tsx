import { PageHead } from './parts'

/** How Apollo works: the tour over the chart screen, and worked examples on one past MNQ day. */
export function Guide({ onTour }: { onTour: () => void }) {
  return (
    <div>
      <PageHead title="Guide">
        <p>A one-minute tour of the chart screen, then three worked examples on a real MNQ day.</p>
      </PageHead>
      <div className="border-b px-5 py-6">
        <button
          type="button"
          onClick={onTour}
          className="rounded-sm bg-brand px-3 py-2 font-mono text-[10px] font-medium tracking-widest text-brand-fg uppercase"
        >
          Take the tour
        </button>
      </div>
    </div>
  )
}
