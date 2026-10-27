import { AlertTriangle, ChevronLeft, ChevronRight, ImageOff } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Card, PageBody, PageHeader } from "@/components/page-header";
import { PhotoViewer } from "@/components/photo-viewer";
import { meetingWhen, money, month } from "@/lib/format";
import { apiGet } from "@/lib/server-api";
import type { MeetingPage } from "@/lib/types";

type Params = Promise<{ id: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { id } = await params;
  return { title: `Ledger page ${id}` };
}

const FOOTER: [keyof MeetingPage["footer"], string][] = [
  ["contribution_total", "Contributions"],
  ["brought_forward", "Brought forward"],
  ["total_collection", "Total collection"],
  ["cash", "Cash"],
  ["banked", "Banked"],
];

const TYPE: Record<string, string> = { emergency: "Em", school_fees: "SF", top_up: "Top-up", other: "?" };

export default async function MeetingDetail({ params }: { params: Params }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const m = await apiGet<MeetingPage>(`/api/meetings/${id}`);
  const when = m.date_estimated ? month(m.meeting_month) : meetingWhen(m.meeting_date, m.meeting_month);

  return (
    <PageBody>
      <PageHeader
        crumbs={<><Link href="/o/records/meetings">Records</Link><span aria-hidden="true" className="mx-2">/</span>Page {m.page_no}</>}
        title={`Meeting of ${when}`}
        sub={`Ledger page ${m.page_no}, ${m.source === "scanned" ? "scanned and checked here" : "typed from the ledger"}${m.date_estimated ? "; the month is worked out from the pages around it" : ""}`}
        action={
          <div className="flex gap-2">
            {m.previous && (
              <Link href={`/o/records/meetings/${m.previous}`} className="inline-flex min-h-11 items-center gap-1 rounded-button border-[1.5px] border-ink px-3.5 font-bold text-ink no-underline hover:bg-ice hover:text-ink">
                <ChevronLeft aria-hidden="true" size={18} /> Page {m.previous}
              </Link>
            )}
            {m.next && (
              <Link href={`/o/records/meetings/${m.next}`} className="inline-flex min-h-11 items-center gap-1 rounded-button border-[1.5px] border-ink px-3.5 font-bold text-ink no-underline hover:bg-ice hover:text-ink">
                Page {m.next} <ChevronRight aria-hidden="true" size={18} />
              </Link>
            )}
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <div className="xl:col-span-5">
          {m.photo.available ? (
            <PhotoViewer src={`/api/meetings/${m.page_no}/photo`} alt={`Photo of ledger page ${m.page_no}`} className="h-[420px] xl:sticky xl:top-6 xl:h-[640px]" />
          ) : (
            <Card tone="cream" className="flex h-full min-h-[200px] flex-col items-start justify-center gap-3">
              <ImageOff aria-hidden="true" size={28} />
              <p className="text-[16px]">{m.photo.reason}</p>
            </Card>
          )}
        </div>

        <div className="flex flex-col gap-5 xl:col-span-7">
          <Card className="p-0 sm:p-0" aria-labelledby="mt-lines">
            <h2 id="mt-lines" className="px-6 pt-6 text-[24px] sm:px-7">Member lines</h2>
            <div className="overflow-x-auto px-2 pb-4 pt-2">
              <table className="w-full min-w-[700px] border-collapse text-[15px]">
                <thead>
                  <tr className="text-[14px] text-muted">
                    <th scope="col" className="border-b border-line px-2.5 py-2 text-right">#</th>
                    <th scope="col" className="border-b border-line px-2.5 py-2 text-left">Member</th>
                    <th scope="col" className="border-b border-line px-2.5 py-2 text-right">Monthly</th>
                    <th scope="col" className="border-b border-line px-2.5 py-2 text-right">Balance before</th>
                    <th scope="col" className="border-b border-line px-2.5 py-2 text-right">Repaid</th>
                    <th scope="col" className="border-b border-line px-2.5 py-2 text-right">Interest</th>
                    <th scope="col" className="border-b border-line px-2.5 py-2 text-right">Balance after</th>
                    <th scope="col" className="border-b border-line px-2.5 py-2 text-left">Due</th>
                  </tr>
                </thead>
                <tbody>
                  {m.lines.map((l, i) => (
                    <tr key={i} className={l.unclear || l.issues ? "bg-cream/60" : ""}>
                      <td className="tabular border-b border-line px-2.5 py-2.5 text-right text-muted">{l.line}</td>
                      <td className="border-b border-line px-2.5 py-2.5 font-bold">
                        {l.code ? <Link href={`/o/members/${l.code}`} className="text-ink">{l.name}</Link> : l.name}
                        {l.loan_type && TYPE[l.loan_type] && <span className="ml-1.5 text-[13px] font-normal text-muted">({TYPE[l.loan_type]})</span>}
                        {(l.unclear || l.issues) && (
                          <span className="ml-2 inline-flex items-center gap-1 text-[13px] font-bold text-medium">
                            <AlertTriangle aria-hidden="true" size={13} />{l.unclear ? "Hard to read" : "Check"}
                          </span>
                        )}
                      </td>
                      <td className="tabular border-b border-line px-2.5 py-2.5 text-right">{l.monthly ? money(l.monthly) : l.monthly_note ?? "–"}</td>
                      <td className="tabular border-b border-line px-2.5 py-2.5 text-right">{l.balance_before ? money(l.balance_before) : "–"}</td>
                      <td className="tabular border-b border-line px-2.5 py-2.5 text-right">{l.repaid ? money(l.repaid) : "–"}</td>
                      <td className="tabular border-b border-line px-2.5 py-2.5 text-right">{typeof l.interest === "number" ? money(l.interest) : l.interest ?? "–"}</td>
                      <td className="tabular border-b border-line px-2.5 py-2.5 text-right font-bold">{l.balance_after ? money(l.balance_after) : "–"}</td>
                      <td className="border-b border-line px-2.5 py-2.5">{l.due_month ? month(l.due_month) : "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="grid gap-5 md:grid-cols-2">
            <Card tone="cream" aria-labelledby="mt-footer">
              <h2 id="mt-footer" className="mb-2 text-[22px]">Page totals</h2>
              <dl>
                {FOOTER.map(([key, label]) => (
                  <div key={key} className="flex justify-between gap-3 border-t border-cream-line py-2.5">
                    <dt className="text-[15px] text-subtle">{label}</dt>
                    <dd className="tabular text-[16px] font-bold">{money(m.footer[key])}</dd>
                  </div>
                ))}
              </dl>
            </Card>
            <Card aria-labelledby="mt-loans">
              <h2 id="mt-loans" className="mb-2 text-[22px]">Loans given at this meeting</h2>
              {m.new_loans.length ? (
                <ul>
                  {m.new_loans.map((n, i) => (
                    <li key={i} className="flex justify-between gap-3 border-t border-line py-2.5 text-[16px]">
                      <span className="font-bold">{n.name}{n.loan_type !== "normal" && <span className="ml-1.5 text-[13px] font-normal text-muted">({n.loan_type.replace("_", " ")})</span>}</span>
                      <span className="tabular">{money(n.amount)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="border-t border-line pt-3 text-[15px] text-muted">None listed on this page.</p>
              )}
            </Card>
          </div>
        </div>
      </div>
    </PageBody>
  );
}
