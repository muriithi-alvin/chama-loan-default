import Link from "next/link";

import { BeadRow } from "@/components/beads";

export default function NotFound() {
  return (
    <main id="main" tabIndex={-1} className="mx-auto flex min-h-[70dvh] max-w-[720px] flex-col justify-center gap-5 px-6 py-16">
      <p className="text-[15px] font-bold uppercase tracking-wide text-muted">Not found</p>
      <h1 className="text-[40px] sm:text-[48px]">There is no page at this address</h1>
      <BeadRow />
      <p className="text-[18px] text-subtle">The link may be old, or the record may have been replaced.</p>
      <div>
        <Link href="/" className="inline-flex min-h-[52px] items-center rounded-button bg-cobalt px-6 text-[16px] font-bold text-white no-underline hover:bg-cobalt-dark hover:text-white">
          Go to the start page
        </Link>
      </div>
    </main>
  );
}
