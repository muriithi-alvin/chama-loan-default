import { ArrowRight } from "lucide-react";
import Link from "next/link";

import type { Band } from "@/lib/types";

import { BandChip } from "./beads";

// What each band meant in testing (Milestone 2 report, section 14.2), shown
// wherever bands appear, with the way to the full explanation.
const MEANING: { band: Band; text: string }[] = [
  { band: "high", text: "about 1 in 3 missed a repayment within the next 3 meetings" },
  { band: "medium", text: "about 1 in 4 did" },
  { band: "low", text: "about 1 in 8 did" },
];

export function BandKey({ current, className = "" }: { current?: Band | null; className?: string }) {
  return (
    <aside aria-label="What the bands mean" className={`flex flex-col gap-3 rounded-card bg-ice px-5 py-4 ${className}`}>
      <p className="text-[15px] font-bold">What the bands mean, from testing on the chama&apos;s past records</p>
      <ul className="flex flex-col gap-2 md:flex-row md:flex-wrap md:gap-x-6">
        {MEANING.map((m) => (
          <li key={m.band} className={`flex items-center gap-2.5 text-[15px] ${current && current !== m.band ? "opacity-60" : ""}`}>
            <BandChip band={m.band} size="sm" />
            <span>{m.text}</span>
          </li>
        ))}
      </ul>
      <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[14px] text-subtle">
        <span>A band is a prompt to follow up, not a decision.</span>
        <Link href="/o/about" className="inline-flex items-center gap-1 font-bold">
          How the early warning works <ArrowRight aria-hidden="true" size={15} />
        </Link>
      </p>
    </aside>
  );
}
