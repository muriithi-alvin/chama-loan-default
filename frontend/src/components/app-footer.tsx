import Link from "next/link";

import { dayAndTime, meetingWhen } from "@/lib/format";
import type { RecordsStatus, Role } from "@/lib/types";

import { Logo } from "./beads";

/** One quiet line at the end of every signed-in page: how current the records
 * are, where the privacy rules are, and who to ask for help. */
export function AppFooter({ role, status }: { role: Role; status: RecordsStatus | null }) {
  const official = role !== "member";
  const records = status?.records_to;
  return (
    <footer className="mx-auto w-full max-w-[1200px] px-4 pb-8 pt-2 sm:px-8 lg:px-11">
      <div className="flex flex-col gap-3 border-t border-line pt-5 text-[14px] text-muted md:flex-row md:flex-wrap md:items-start md:justify-between md:gap-x-8">
        <p className="flex items-center gap-2">
          <Logo size={22} />
          <span>
            <strong className="text-ink">Kibaba</strong> · Strathmore University, CS Project II 2026
          </span>
        </p>
        <p className="flex flex-col gap-0.5">
          {records && (
            <span>Records up to ledger page {records.page_no}, {meetingWhen(records.meeting_date, records.meeting_month)}</span>
          )}
          {official && status?.model_label && status.scored_at && (
            <span>Scores from model run {status.model_label}, {dayAndTime(status.scored_at)}</span>
          )}
        </p>
        <p className="flex flex-col gap-0.5 md:items-end">
          {official ? (
            <Link href="/o/about#protected" className="font-bold">How the records are protected</Link>
          ) : (
            <span>Your records are seen only by you and your chama&apos;s officials.</span>
          )}
          <span>Something wrong or can&apos;t sign in? Ask your chama&apos;s {official ? "admin" : "officials"}.</span>
        </p>
      </div>
    </footer>
  );
}
