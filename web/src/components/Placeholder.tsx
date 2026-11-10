export function Placeholder({ title }: { title: string }) {
  return (
    <section className="grid content-center gap-2 px-5 py-16">
      <h1 className="text-[28px] font-semibold tracking-tight">{title}</h1>
      <p className="text-muted">This page arrives in the next build.</p>
    </section>
  )
}
