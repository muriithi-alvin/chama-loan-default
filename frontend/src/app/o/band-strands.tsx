"use client";

import { LayoutGroup, motion } from "motion/react";
import Link from "next/link";

import { BAND, BandChip, Bead } from "@/components/beads";
import type { Band, Overview } from "@/lib/types";

const STRANDS: Band[] = ["high", "medium", "low"];

// Three bead strands, one bead per member with a running loan (section 7).
// A member whose band changed slides to the new strand (600 ms). Each bead is
// a link, labelled with the member's name and band, reachable by keyboard.
export function BandStrands({ data }: { data: Overview }) {
  return (
    <LayoutGroup>
      <div className="flex flex-col gap-1">
        {STRANDS.map((band) => {
          const beads = data.strand.filter((b) => b.band === band);
          return (
            <div key={band} className="grid grid-cols-1 items-center gap-2 py-2.5 sm:grid-cols-[200px_1fr] sm:gap-4">
              <div className="flex flex-col gap-0.5">
                <BandChip band={band} />
                <span className="text-[14px] text-muted">
                  {beads.length} {beads.length === 1 ? "member" : "members"}
                </span>
              </div>
              <div className="relative flex min-h-[44px] flex-wrap items-center gap-x-3 gap-y-2">
                <span aria-hidden="true" className="absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 bg-line" />
                {beads.map((b) => (
                  <motion.div key={b.code} layoutId={`bead-${b.code}`} className="relative"
                    transition={{ type: "spring", stiffness: 140, damping: 16, mass: 0.9 }}>
                    <Link href={`/o/members/${b.code}`} aria-label={`${b.name}, ${BAND[b.band].label}`}
                      className={`group relative block rounded-full ${b.moved_from ? "ring-[3px] ring-ink ring-offset-[3px]" : ""}`}>
                      <Bead colour={BAND[b.band].colour} size={30}
                        className="transition-transform duration-200 group-hover:-translate-y-1 group-focus-visible:-translate-y-1" />
                      <span role="tooltip"
                        className="pointer-events-none absolute bottom-[40px] left-1/2 z-10 -translate-x-1/2 translate-y-1 whitespace-nowrap rounded-lg bg-ink px-2.5 py-1 text-[13px] font-bold text-white opacity-0 transition-all duration-150 group-hover:translate-y-0 group-hover:opacity-100 group-focus-visible:translate-y-0 group-focus-visible:opacity-100">
                        {b.name}
                      </span>
                    </Link>
                  </motion.div>
                ))}
                {beads.length === 0 && <span className="relative bg-white pr-2 text-[14px] text-muted">None</span>}
              </div>
            </div>
          );
        })}
      </div>
    </LayoutGroup>
  );
}
