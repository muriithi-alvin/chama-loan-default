import { ArrowRight } from "lucide-react";
import Link from "next/link";

import type { Band } from "@/lib/types";

import { BAND, BandChip } from "./beads";

const ORDER: Band[] = ["high", "medium", "low"];

/** What each band means, in one sentence each, wherever bands appear. */
export function BandKey({ current, className = "" }: { current?: Band | null; className?: string }) {
  return (
    <aside aria-label="What the colours mean" className={`flex flex-col gap-3 rounded-card bg-ice px-5 py-4 ${className}`}>
      <p className="text-[15px] font-bold">What the colours mean</p>
      <ul className="flex flex-col gap-2.5">
        {ORDER.map((band) => (
          <li key={band} className={`flex flex-wrap items-center gap-x-3 gap-y-1 text-[15px] ${current && current !== band ? "opacity-60" : ""}`}>
            <BandChip band={band} size="sm" />
            <span>{BAND[band].meaning}</span>
          </li>
        ))}
      </ul>
      <p className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[14px] text-subtle">
        <span>Kibaba suggests who to talk to. Officials decide.</span>
        <Link href="/o/about" className="inline-flex items-center gap-1 font-bold">
          How Kibaba decides <ArrowRight aria-hidden="true" size={15} />
        </Link>
      </p>
    </aside>
  );
}
