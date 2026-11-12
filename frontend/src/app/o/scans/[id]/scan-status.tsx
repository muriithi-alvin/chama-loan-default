"use client";

import { ArrowRight, Camera, Keyboard, RotateCw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import useSWR from "swr";

import { BeadThread } from "@/components/bead-thread";
import { FlowSteps } from "@/components/flow-steps";
import { Card } from "@/components/page-header";
import { ServiceError } from "@/components/service-error";
import { api, ApiProblem, fetcher } from "@/lib/client-api";
import type { Upload } from "@/lib/types";

const WORKING = new Set(["queued", "reading"]);
const FORWARD_MS = 1200;   // long enough to see "Ready", short enough not to wait

// Updates itself every 2 s (OFF-9, X8). Once the page is read it opens the
// review by itself, and an accepted page opens its records update (D-040).
export function ScanStatus({ id }: { id: number }) {
  const router = useRouter();
  const { data, error, mutate } = useSWR<Upload>(`/api/uploads/${id}`, fetcher, {
    refreshInterval: (latest) => (!latest || WORKING.has(latest.status) ? 2000 : 0),
  });
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const forwarded = useRef(false);

  useEffect(() => {
    if (!data || !WORKING.has(data.status)) return;
    const start = new Date(data.created_at).getTime();
    const tick = () => setElapsed(Math.max(0, Math.round((Date.now() - start) / 1000)));
    tick();
    const t = window.setInterval(tick, 1000);
    return () => window.clearInterval(t);
  }, [data]);

  const next = data?.status === "ready" ? `/o/scans/${id}/review`
    : data?.status === "accepted" && data.run_id ? `/o/runs/${data.run_id}` : null;
  useEffect(() => {
    if (!next || forwarded.current) return;
    forwarded.current = true;
    const t = window.setTimeout(() => router.replace(next), FORWARD_MS);
    return () => window.clearTimeout(t);
  }, [next, router]);

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
      forwarded.current = false;
      await mutate();
    } catch (e) {
      setRetryError(e instanceof ApiProblem ? e.message : "Could not try again. Reload the page.");
    } finally {
      setRetrying(false);
    }
  }

  const state = WORKING.has(data.status) ? "working" : data.status === "failed" ? "failed" : "done";
  const several = data.parts > 1;
  const reading = data.step?.startsWith("reading photo") ? `Reading ${data.step.slice("reading ".length)}` : "Reading the page";
  const label = {
    queued: "Waiting for its turn", reading, ready: "Ready: opening the rows to check", failed: "Could not read the page",
    accepted: "Accepted: opening the records update", discarded: "Discarded",
  }[data.status];

  return (
    <div className="flex flex-col gap-6">
      <FlowSteps at={data.status === "accepted" ? "update" : data.status === "ready" ? "check" : "read"}
        typed={data.source === "typed"} failed={data.status === "failed"} />
      <Card className="flex flex-col gap-6">
        <div aria-live="polite" className="flex flex-col gap-1.5">
          <p className="font-display text-[30px] font-extrabold leading-tight">{label}</p>
          <p className="text-[16px] text-muted">
            {WORKING.has(data.status)
              ? `Started ${elapsed} s ago. ${several ? `${data.parts} photos are read one after another, about a minute each.` : "A page usually takes under a minute."}`
              : data.seconds ? `Read in ${data.seconds.toFixed(0)} seconds${several ? `, ${data.parts} photos` : ""}.` : null}
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
        {next && (
          <Link href={next} replace className="inline-flex min-h-14 items-center gap-2 rounded-button bg-cobalt px-6 text-[18px] font-bold text-white no-underline hover:bg-cobalt-dark hover:text-white">
            {data.status === "ready" ? "Check the rows" : "See the records being updated"} <ArrowRight aria-hidden="true" size={20} />
          </Link>
        )}
        {data.status === "failed" && (
          <>
            <button type="button" onClick={retry} disabled={retrying}
              className="inline-flex min-h-14 items-center gap-2 rounded-button bg-cobalt px-6 text-[18px] font-bold text-white hover:bg-cobalt-dark disabled:opacity-60">
              <RotateCw aria-hidden="true" size={20} /> {retrying ? "Trying again" : "Try again"}
            </button>
            <Link href="/o/scan" className="inline-flex min-h-14 items-center gap-2 rounded-button border-2 border-ink px-6 text-[18px] font-bold text-ink no-underline hover:bg-ice hover:text-ink">
              <Camera aria-hidden="true" size={20} /> Take new photos
            </Link>
            <Link href="/o/type" className="inline-flex min-h-14 items-center gap-2 rounded-button border-2 border-ink px-6 text-[18px] font-bold text-ink no-underline hover:bg-ice hover:text-ink">
              <Keyboard aria-hidden="true" size={20} /> Type the page in
            </Link>
          </>
        )}
        {data.status === "discarded" && (
          <button type="button" onClick={retry} disabled={retrying}
            className="inline-flex min-h-14 items-center gap-2 rounded-button border-2 border-ink px-6 text-[18px] font-bold text-ink hover:bg-ice">
            {data.source === "typed" ? "Open this page again" : "Read these photos again"}
          </button>
        )}
      </div>
      {retryError && <p role="alert" className="text-[16px] font-bold text-high">{retryError}</p>}
    </div>
  );
}
