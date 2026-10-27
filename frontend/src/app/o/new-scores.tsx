"use client";

import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { startTransition, useEffect, useState } from "react";
import useSWR from "swr";

import { BAND } from "@/components/beads";
import { fetcher } from "@/lib/client-api";
import { ago } from "@/lib/format";
import type { Overview } from "@/lib/types";

// The overview checks for new scores every 60 s (X8). When the worker saves
// new ones, a banner slides down once; pressing it loads them, and beads that
// changed band slide to their new strand.
export function NewScores({ data }: { data: Overview }) {
  const router = useRouter();
  const shown = data.scores?.scored_at ?? null;
  const { data: latest } = useSWR<{ scored_at: string | null; page_no: number | null }>(
    "/api/scores/latest", fetcher, { refreshInterval: 60_000, revalidateOnFocus: true, dedupingInterval: 20_000 },
  );
  const [updated, setUpdated] = useState(false);
  const fresh = latest?.scored_at && shown && new Date(latest.scored_at) > new Date(shown);
  const moved = data.strand.filter((b) => b.moved_from);

  useEffect(() => {
    if (!updated) return;
    const t = window.setTimeout(() => setUpdated(false), 12_000);
    return () => window.clearTimeout(t);
  }, [updated]);

  return (
    <div aria-live="polite">
      <AnimatePresence initial={false}>
        {fresh && (
          <motion.div key="banner" initial={{ opacity: 0, y: -14 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            className="flex flex-wrap items-center justify-between gap-4 rounded-card bg-ice px-5 py-4">
            <span className="flex items-center gap-3.5 text-[17px]">
              <span aria-hidden="true" className="bead bead-cobalt bead-pulse" style={{ width: 16, height: 16 }} />
              <span>
                <strong>New scores are ready.</strong>{" "}
                {latest?.page_no ? `Ledger page ${latest.page_no} was scored ${ago(latest.scored_at!)}.` : null}
              </span>
            </span>
            <button type="button"
              onClick={() => startTransition(() => { setUpdated(true); router.refresh(); })}
              className="min-h-12 rounded-button bg-cobalt px-5 text-[16px] font-bold text-white hover:bg-cobalt-dark">
              Show new scores
            </button>
          </motion.div>
        )}
        {!fresh && updated && (
          <motion.div key="done" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex items-center gap-3 rounded-card bg-low-bg px-5 py-4 text-[17px] text-low">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#135C30" strokeWidth="2.6"
              strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
            <span>
              <strong>Showing the newest scores.</strong>{" "}
              {moved.length === 0
                ? "No member changed band."
                : moved.map((m) => `${m.name} moved from ${BAND[m.moved_from!].label} to ${BAND[m.band].label}.`).join(" ")}
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
