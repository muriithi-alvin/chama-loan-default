"use client";

import { ArrowRight, CalendarDays, Camera, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { Card } from "@/components/page-header";
import { api, ApiProblem } from "@/lib/client-api";
import { meetingWhen } from "@/lib/format";
import type { TypedInfo, Upload } from "@/lib/types";

function newKey() {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID().replaceAll("-", "") : `${Date.now()}${Math.random()}`.replace(".", "");
}

function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** The first day of the month after the later of the last recorded and the last accepted meeting. */
function earliest(info: TypedInfo): string | undefined {
  const dates = [info.last_meeting?.meeting_date ?? info.last_meeting?.meeting_month, info.last_accepted]
    .filter(Boolean).map((d) => new Date(d as string));
  if (!dates.length) return undefined;
  const last = new Date(Math.max(...dates.map((d) => d.getTime())));
  return iso(new Date(last.getFullYear(), last.getMonth() + 1, 1));
}

export function TypeForm({ info }: { info: TypedInfo }) {
  const router = useRouter();
  const id = useId();
  const min = earliest(info);
  const today = iso(new Date());
  const [when, setWhen] = useState("");
  const [key] = useState(newKey);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<ApiProblem | null>(null);
  const waiting = info.waiting > 0;

  async function start(e: React.FormEvent) {
    e.preventDefault();
    if (busy || !when) return;
    setBusy(true);
    setProblem(null);
    try {
      const { upload } = await api<{ upload: Upload }>("/api/typed", { json: { meeting_date: when, idempotency_key: key } });
      router.push(`/o/scans/${upload.id}/review`);
    } catch (err) {
      setProblem(err instanceof ApiProblem ? err : new ApiProblem(0, "unknown", "The page could not be opened. Try again."));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={start} className="flex flex-col gap-6" noValidate>
      <Card className="flex flex-col gap-4">
        <h2 className="flex items-center gap-2.5 text-[22px]"><Users aria-hidden="true" size={22} /> Already filled in for you</h2>
        {info.last_meeting ? (
          <p className="text-[17px]">
            From the last meeting in the records, ledger page {info.last_meeting.page_no} ({meetingWhen(info.last_meeting.meeting_date, info.last_meeting.meeting_month)}):
            {" "}<strong>{info.members.length} members</strong> on a line each
            {info.loans_carried ? <>, and <strong>{info.loans_carried} loan balances</strong> carried over</> : null}.
            You type what was paid at this meeting.
          </p>
        ) : (
          <p className="text-[17px]">There are no meetings in the records yet, so the page opens empty: add each member&apos;s line.</p>
        )}
        {info.members.length > 0 && (
          <ul aria-label="Members on the new page" className="flex flex-wrap gap-2">
            {info.members.map((m, i) => (
              <li key={`${m}-${i}`} className="rounded-full bg-cream px-3 py-1 text-[15px] font-bold">{m}</li>
            ))}
          </ul>
        )}
      </Card>

      <div className="flex flex-col gap-2">
        <label htmlFor={`${id}-date`} className="flex items-center gap-2 text-[17px] font-bold">
          <CalendarDays aria-hidden="true" size={20} /> Date of the meeting
        </label>
        <p id={`${id}-help`} className="text-[15px] text-muted">
          {min ? `Pages are added in order, so it must be on or after ${new Date(min).toLocaleDateString("en-KE", { day: "numeric", month: "long", year: "numeric" })}.` : "The day the chama met."}
        </p>
        <input id={`${id}-date`} type="date" required value={when} min={min} max={today}
          onChange={(e) => setWhen(e.target.value)} aria-describedby={`${id}-help`}
          aria-invalid={problem?.field === "meeting_date"}
          className={`h-[52px] w-full max-w-[280px] rounded-button border-[1.5px] bg-white px-4 text-[17px] ${problem?.field === "meeting_date" ? "border-high" : "border-field"}`} />
      </div>

      <div aria-live="polite">
        {waiting && (
          <p className="rounded-button bg-cream px-4 py-3 text-[16px]">
            The last page is still being added to the records. Wait until it is done, so this page starts from its balances.
          </p>
        )}
        {problem && (
          <p role="alert" className="rounded-button bg-high-bg px-4 py-3 text-[16px] text-high">
            {problem.message} {problem.ref && <span className="text-[14px]">(reference {problem.ref})</span>}
          </p>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <button type="submit" disabled={!when || busy || waiting}
          className="inline-flex min-h-14 items-center gap-3 rounded-button bg-cobalt px-7 text-[18px] font-bold text-white hover:bg-cobalt-dark disabled:opacity-50">
          {busy ? "Opening the ledger" : "Open the ledger"} <ArrowRight aria-hidden="true" size={20} />
        </button>
        <Link href="/o/scan" className="inline-flex items-center gap-2 text-[16px] font-bold">
          <Camera aria-hidden="true" size={18} /> Have a photo? Scan it instead
        </Link>
      </div>
    </form>
  );
}
