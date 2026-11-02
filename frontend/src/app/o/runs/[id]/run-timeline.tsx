"use client";

import { ArrowRight, RotateCw } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";

import { Card } from "@/components/page-header";
import { ServiceError } from "@/components/service-error";
import { api, ApiProblem, fetcher } from "@/lib/client-api";
import type { Run } from "@/lib/types";

const STEP_LABEL: Record<string, { title: string; what: string }> = {
  ingest: { title: "Saving the page", what: "The checked rows join the chama's records" },
  names: { title: "Matching names", what: "Each name is linked to the right member" },
  anonymise: { title: "Hiding names", what: "Names are swapped for codes before anything is worked out" },
  checks: { title: "Updating the records", what: "Balances, loans and repayments are brought up to date and checked" },
  score: { title: "Finding who to follow up", what: "Each member with a loan gets a colour and the reasons for it" },
};

function seconds(from: string | null, to: string | null): string | null {
  if (!from) return null;
  const s = Math.max(0, Math.round(((to ? new Date(to) : new Date()).getTime() - new Date(from).getTime()) / 1000));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
}

// One bead per step on a string: filled when done, a gentle pulse while
// running, red with "!" and the reason on failure (OFF-11). Polls every 2 s.
export function RunTimeline({ id }: { id: number }) {
  const { data, error, mutate } = useSWR<Run>(`/api/runs/${id}`, fetcher, {
    refreshInterval: (latest) => (!latest || latest.status === "queued" || latest.status === "running" ? 2000 : 0),
  });
  const [retrying, setRetrying] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  if (error && !data) {
    return <ServiceError message={error instanceof ApiProblem ? error.message : "The run could not be loaded."}
      reference={error instanceof ApiProblem ? error.ref : undefined} retry={() => mutate()} />;
  }
  if (!data) return <p role="status" className="text-[17px] text-muted">Loading the run…</p>;

  async function retry() {
    setRetrying(true);
    setProblem(null);
    try {
      await api(`/api/uploads/${data!.upload_id}/retry`, { method: "POST" });
      await mutate();
    } catch (e) {
      setProblem(e instanceof ApiProblem ? e.message : "Could not try again.");
    } finally {
      setRetrying(false);
    }
  }

  const headline = {
    queued: "Waiting for the worker", running: "Running", done: "Done: the records and bands are up to date", failed: "Stopped",
  }[data.status];

  return (
    <div className="flex flex-col gap-6">
      <p aria-live="polite" className="font-display text-[28px] font-extrabold leading-tight">
        {headline}
        {data.page_no ? <span className="block font-sans text-[16px] font-normal text-muted">Ledger page {data.page_no}{data.finished_at && data.started_at ? `, ${seconds(data.started_at, data.finished_at)} in all` : ""}</span> : null}
      </p>
      <Card className="py-2">
        <ol className="relative">
          <span aria-hidden="true" className="absolute bottom-8 left-[21px] top-8 w-0.5 bg-line" />
          {data.steps.map((s) => {
            const label = STEP_LABEL[s.step] ?? { title: s.step, what: "" };
            const time = seconds(s.started_at, s.finished_at);
            return (
              <li key={s.step} className="relative flex items-start gap-4 py-4">
                <span className="relative z-10 flex h-[44px] w-[44px] shrink-0 items-center justify-center">
                  {s.status === "done" && (
                    <motion.span initial={{ scale: 0.4 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 300, damping: 15 }}
                      className="bead bead-leaf" style={{ width: 30, height: 30 }} aria-hidden="true" />
                  )}
                  {s.status === "running" && <span className="bead bead-cobalt bead-pulse" style={{ width: 30, height: 30 }} aria-hidden="true" />}
                  {s.status === "waiting" && <span className="block h-[30px] w-[30px] rounded-full border-[3px] border-dotted border-field bg-white" aria-hidden="true" />}
                  {s.status === "failed" && (
                    <span className="bead bead-red flex items-center justify-center text-[16px] font-extrabold text-white" style={{ width: 30, height: 30 }} aria-hidden="true">!</span>
                  )}
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="text-[18px] font-bold">{label.title}</span>
                    <span className={`text-[15px] font-bold ${s.status === "failed" ? "text-high" : s.status === "done" ? "text-low" : "text-muted"}`}>
                      {{ waiting: "Waiting", running: "Running", done: "Done", failed: "Failed" }[s.status]}{time ? `, ${time}` : ""}
                    </span>
                  </span>
                  <span className="text-[15px] text-muted">{label.what}</span>
                  {s.error_message && <span className="mt-1 rounded-button bg-high-bg px-3 py-2 text-[15px] text-high">{s.error_message}</span>}
                </span>
              </li>
            );
          })}
        </ol>
      </Card>

      {data.status === "failed" && (
        <div className="flex flex-col gap-2">
          <div>
            <button type="button" onClick={retry} disabled={retrying}
              className="inline-flex min-h-14 items-center gap-2 rounded-button bg-cobalt px-6 text-[18px] font-bold text-white hover:bg-cobalt-dark disabled:opacity-60">
              <RotateCw aria-hidden="true" size={20} /> {retrying ? "Starting again" : "Try again"}
            </button>
          </div>
          {problem && <p role="alert" className="text-[16px] font-bold text-high">{problem}</p>}
        </div>
      )}

      {data.status === "done" && (
        <Card tone="ice" className="flex flex-col gap-3">
          <h2 className="text-[22px]">Members on this page</h2>
          <ul className="flex flex-wrap gap-2">
            {data.changed_members.map((m) => (
              <li key={m.code}>
                <Link href={`/o/members/${m.code}`} className="inline-flex min-h-11 items-center rounded-full bg-white px-4 text-[15px] font-bold no-underline hover:bg-cobalt hover:text-white">
                  {m.name}
                </Link>
              </li>
            ))}
          </ul>
          <Link href="/o" className="inline-flex min-h-12 items-center gap-2 self-start rounded-button bg-cobalt px-5 text-[16px] font-bold text-white no-underline hover:bg-cobalt-dark hover:text-white">
            See the new bands <ArrowRight aria-hidden="true" size={18} />
          </Link>
        </Card>
      )}
    </div>
  );
}
