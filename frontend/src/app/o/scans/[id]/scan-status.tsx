"use client";

import { ArrowRight, Camera, RotateCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import useSWR from "swr";

import { BeadThread } from "@/components/bead-thread";
import { Card } from "@/components/page-header";
import { ServiceError } from "@/components/service-error";
import { api, ApiProblem, fetcher } from "@/lib/client-api";
import type { Upload } from "@/lib/types";

const WORKING = new Set(["queued", "reading"]);

// Updates itself every 2 s and stops when the reading has ended (OFF-9, X8).
export function ScanStatus({ id }: { id: number }) {
  const { data, error, mutate } = useSWR<Upload>(`/api/uploads/${id}`, fetcher, {
    refreshInterval: (latest) => (!latest || WORKING.has(latest.status) ? 2000 : 0),
  });
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!data || !WORKING.has(data.status)) return;
    const start = new Date(data.created_at).getTime();
    const tick = () => setElapsed(Math.max(0, Math.round((Date.now() - start) / 1000)));
    tick();
    const t = window.setInterval(tick, 1000);
    return () => window.clearInterval(t);
  }, [data]);

  if (error && !data) {
    return <ServiceError message={error instanceof ApiProblem ? error.message : "The scan could not be loaded."}
      reference={error instanceof ApiProblem ? error.ref : undefined} retry={() => mutate()} />;
  }
  if (!data) return <p role="status" className="text-[17px] text-muted">Loading the scan…</p>;

  async function retry() {
    setRetrying(true);
    setRetryError(null);
    try {
      await api(`/api/uploads/${id}/retry`, { method: "POST" });
      await mutate();
    } catch (e) {
      setRetryError(e instanceof ApiProblem ? e.message : "Could not try again. Reload the page.");
    } finally {
      setRetrying(false);
    }
  }

  const state = WORKING.has(data.status) ? "working" : data.status === "failed" ? "failed" : "done";
  const label = {
    queued: "Waiting for its turn", reading: "Reading the page", ready: "Ready for review", failed: "Could not read the page",
    accepted: "Accepted", discarded: "Discarded",
  }[data.status];

  return (
    <div className="flex flex-col gap-6">
      <Card className="flex flex-col gap-6">
        <div aria-live="polite" className="flex flex-col gap-1.5">
          <p className="font-display text-[30px] font-extrabold leading-tight">{label}</p>
          <p className="text-[16px] text-muted">
            {WORKING.has(data.status)
              ? `Started ${elapsed} s ago. A page usually takes under a minute.`
              : data.seconds ? `Read in ${data.seconds.toFixed(0)} seconds.` : null}
          </p>
        </div>
        <BeadThread state={state} steps={["Queued", "Reading", state === "failed" ? "Failed" : "Ready for review"]} />
        {data.problem && (
          <p className={`rounded-button px-4 py-3 text-[16px] ${data.status === "failed" ? "bg-high-bg text-high" : "bg-cream"}`}>
            {data.problem}
          </p>
        )}
      </Card>

      <div className="flex flex-wrap gap-3">
        {data.status === "ready" && (
          <Link href={`/o/scans/${id}/review`} className="inline-flex min-h-14 items-center gap-2 rounded-button bg-cobalt px-6 text-[18px] font-bold text-white no-underline hover:bg-cobalt-dark hover:text-white">
            Check the rows <ArrowRight aria-hidden="true" size={20} />
          </Link>
        )}
        {data.status === "failed" && (
          <>
            <button type="button" onClick={retry} disabled={retrying}
              className="inline-flex min-h-14 items-center gap-2 rounded-button bg-cobalt px-6 text-[18px] font-bold text-white hover:bg-cobalt-dark disabled:opacity-60">
              <RotateCw aria-hidden="true" size={20} /> {retrying ? "Trying again" : "Try again"}
            </button>
            <Link href="/o/scan" className="inline-flex min-h-14 items-center gap-2 rounded-button border-2 border-ink px-6 text-[18px] font-bold text-ink no-underline hover:bg-ice hover:text-ink">
              <Camera aria-hidden="true" size={20} /> Take a new photo
            </Link>
          </>
        )}
        {data.status === "accepted" && data.run_id && (
          <Link href={`/o/runs/${data.run_id}`} className="inline-flex min-h-14 items-center gap-2 rounded-button bg-cobalt px-6 text-[18px] font-bold text-white no-underline hover:bg-cobalt-dark hover:text-white">
            See the records being updated <ArrowRight aria-hidden="true" size={20} />
          </Link>
        )}
        {data.status === "discarded" && (
          <button type="button" onClick={retry} disabled={retrying}
            className="inline-flex min-h-14 items-center gap-2 rounded-button border-2 border-ink px-6 text-[18px] font-bold text-ink hover:bg-ice">
            Read this photo again
          </button>
        )}
      </div>
      {retryError && <p role="alert" className="text-[16px] font-bold text-high">{retryError}</p>}
    </div>
  );
}
