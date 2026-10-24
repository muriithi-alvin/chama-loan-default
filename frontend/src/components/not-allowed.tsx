import Link from "next/link";

import { BeadRow } from "./beads";
import { Meeting } from "./figurines";

/** The friendly "not allowed" page (R4, MEM-3). */
export function NotAllowed({ home, homeLabel }: { home: string; homeLabel: string }) {
  return (
    <main id="main" tabIndex={-1} className="relative mx-auto flex min-h-[70dvh] max-w-[720px] flex-col justify-center gap-5 overflow-hidden px-6 py-16">
      <Meeting tone="ink" className="pointer-events-none absolute -right-6 bottom-0 w-[240px] opacity-[0.12]" />
      <p className="text-[15px] font-bold uppercase tracking-wide text-muted">Not allowed</p>
      <h1 className="text-[40px] sm:text-[48px]">This page is not part of your account</h1>
      <BeadRow />
      <p className="max-w-[34em] text-[18px] text-subtle">
        Each account opens only its own chama&apos;s pages, and members see only their own records. If you think you
        should see this page, ask your chama&apos;s admin.
      </p>
      <div>
        <Link href={home}
          className="inline-flex min-h-[52px] items-center rounded-button bg-cobalt px-6 text-[16px] font-bold text-white no-underline hover:bg-cobalt-dark hover:text-white">
          {homeLabel}
        </Link>
      </div>
    </main>
  );
}
