import { Camera, ChevronRight, FileSpreadsheet, Keyboard } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Card, PageBody, PageHeader } from "@/components/page-header";
import { meetingWhen, money, month } from "@/lib/format";
import { apiGet } from "@/lib/server-api";
import type { MeetingRow } from "@/lib/types";

export const metadata: Metadata = { title: "Records: meetings" };

function When({ m }: { m: MeetingRow }) {
  return (
    <>
      {m.date_estimated ? month(m.meeting_month) : meetingWhen(m.meeting_date, m.meeting_month)}
      {m.date_estimated && <span className="ml-1.5 text-[13px] font-normal text-muted">(month worked out)</span>}
    </>
  );
}

function Source({ source }: { source: MeetingRow["source"] }) {
  if (source === "entered") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-low-bg px-2.5 py-0.5 text-[14px] font-bold text-low">
        <Keyboard aria-hidden="true" size={14} /> Entered here
      </span>
    );
  }
  return source === "scanned" ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-ice px-2.5 py-0.5 text-[14px] font-bold text-cobalt">
      <Camera aria-hidden="true" size={14} /> Scanned
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-cream px-2.5 py-0.5 text-[14px] font-bold text-subtle">
      <FileSpreadsheet aria-hidden="true" size={14} /> Typed
    </span>
  );
}

export default async function MeetingsPage() {
  const { meetings } = await apiGet<{ meetings: MeetingRow[] }>("/api/meetings");
  const scanned = meetings.filter((m) => m.source !== "typed").length;

  return (
    <PageBody>
      <PageHeader title="Records" sub={`${meetings.length} meetings, one ledger page each. ${scanned} scanned or typed in here, the rest typed from the ledger.`}
        action={
          <Link href="/o/scan" className="inline-flex min-h-12 items-center gap-2 rounded-button bg-cobalt px-5 text-[16px] font-bold text-white no-underline hover:bg-cobalt-dark hover:text-white">
            <Camera aria-hidden="true" size={18} /> Scan the next page
          </Link>
        } />

      {meetings.length === 0 ? (
        <Card tone="cream"><p className="text-[17px]">No meetings recorded yet. Scan your first ledger page.</p></Card>
      ) : (
        <>
          <Card className="hidden p-0 sm:block sm:p-0">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-[16px]">
                <caption className="sr-only">Meetings, newest first</caption>
                <thead>
                  <tr className="text-[14px] text-muted">
                    <th scope="col" className="border-b border-line px-4 py-3 text-left">Meeting</th>
                    <th scope="col" className="border-b border-line px-3 py-3 text-right">Page</th>
                    <th scope="col" className="border-b border-line px-3 py-3 text-right">Contributions</th>
                    <th scope="col" className="border-b border-line px-3 py-3 text-right">Total collection</th>
                    <th scope="col" className="border-b border-line px-3 py-3 text-right">Lines</th>
                    <th scope="col" className="border-b border-line px-3 py-3 text-left">Source</th>
                    <th scope="col" className="border-b border-line px-3 py-3"><span className="sr-only">Open</span></th>
                  </tr>
                </thead>
                <tbody>
                  {meetings.map((m) => (
                    <tr key={m.page_no} className="hover:bg-ice/60">
                      <td className="border-b border-line px-4 py-3 font-bold"><When m={m} /></td>
                      <td className="tabular border-b border-line px-3 py-3 text-right">{m.page_no}</td>
                      <td className="tabular border-b border-line px-3 py-3 text-right">{money(m.contribution_total)}</td>
                      <td className="tabular border-b border-line px-3 py-3 text-right">{money(m.total_collection)}</td>
                      <td className="tabular border-b border-line px-3 py-3 text-right">
                        {m.lines}{m.new_loans ? <span className="text-muted"> + {m.new_loans} new {m.new_loans === 1 ? "loan" : "loans"}</span> : null}
                      </td>
                      <td className="border-b border-line px-3 py-3"><Source source={m.source} /></td>
                      <td className="border-b border-line px-3 py-3 text-right">
                        <Link href={`/o/records/meetings/${m.page_no}`} className="inline-flex min-h-11 items-center gap-1 rounded-[10px] px-3 font-bold no-underline hover:bg-ice">
                          Open<span className="sr-only"> page {m.page_no}</span><ChevronRight aria-hidden="true" size={16} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          <ul className="flex flex-col gap-3 sm:hidden">
            {meetings.map((m) => (
              <li key={m.page_no}>
                <Link href={`/o/records/meetings/${m.page_no}`} className="flex flex-col gap-2 rounded-card border border-line bg-white p-5 text-ink no-underline active:bg-ice">
                  <span className="flex items-center justify-between gap-3">
                    <span className="text-[17px] font-bold"><When m={m} /></span>
                    <Source source={m.source} />
                  </span>
                  <span className="text-[15px] text-muted">Page {m.page_no} · {m.lines} lines · {money(m.total_collection)} collected</span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </PageBody>
  );
}
