/** Loading state: a thread of beads travelling while the page's data arrives (X3). */
export function PageLoading({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="mx-auto flex max-w-[1200px] flex-col gap-6 px-5 py-10 sm:px-11">
      <span className="sr-only">{label}</span>
      <div aria-hidden="true" className="h-12 w-64 animate-pulse rounded-button bg-ice" />
      <svg aria-hidden="true" viewBox="0 0 240 12" className="w-[240px]">
        <line x1="6" y1="6" x2="234" y2="6" className="wire" stroke="#2547A8" />
      </svg>
      <div aria-hidden="true" className="grid gap-5 md:grid-cols-12">
        <div className="h-64 animate-pulse rounded-card bg-ice md:col-span-7" />
        <div className="h-64 animate-pulse rounded-card bg-cream md:col-span-5" />
      </div>
    </div>
  );
}
