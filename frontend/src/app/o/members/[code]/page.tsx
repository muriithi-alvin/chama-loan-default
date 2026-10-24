import type { Metadata } from "next";
import Link from "next/link";
import { ViewTransition } from "react";

import { BandKey } from "@/components/band-key";
import { BandChip, Bead, EffectIcon, NoLoanChip } from "@/components/beads";
import { Card, PageBody } from "@/components/page-header";
import { dayAndTime, meetingWhen, money, month, monthShort } from "@/lib/format";
import { apiGet } from "@/lib/server-api";
import type { MemberPage } from "@/lib/types";

type Params = Promise<{ code: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { code } = await params;
  return { title: `Member ${code.slice(-4).toUpperCase()}` };
}

const LOAN_TYPE: Record<string, string> = {
  normal: "Normal", emergency: "Emergency", school_fees: "School fees", top_up: "Top-up", other: "Other",
};

function status(loan: MemberPage["loans"][number]) {
  if (loan.running && loan.status === "overdue") return { text: "Running, past its due month", bead: "red" as const };
  if (loan.running) return { text: "Running", bead: "cobalt" as const };
  if (loan.status === "topped_up") {
    return { text: loan.rolled_into_month ? `Rolled into the ${month(loan.rolled_into_month)} loan` : "Rolled into a bigger loan", bead: "empty" as const };
  }
  if (loan.status === "lost_track") return { text: "No longer in the records", bead: "empty" as const };
  if (loan.status === "repaid_late") return { text: "Repaid after its due month", bead: "leaf" as const };
  return { text: "Repaid", bead: "leaf" as const };
}

export default async function MemberDetail({ params }: { params: Params }) {
  const { code } = await params;
  const m = await apiGet<MemberPage>(`/api/members/${encodeURIComponent(code)}`);
  const paid = m.contributions.filter((c) => c.paid).length;
  const amounts = [...new Set(m.contributions.filter((c) => c.paid).map((c) => c.amount))];

  return (
    <PageBody className="gap-6">
      <nav aria-label="Breadcrumb" className="text-[15px] text-muted">
        <Link href="/o/members">Members</Link>
        <span aria-hidden="true" className="mx-2">/</span>
        <span>{m.name}</span>
      </nav>

      <header className="condense sticky top-[61px] z-20 -mx-5 flex flex-col gap-3.5 rounded-b-card bg-white/95 px-5 pb-5 pt-4 backdrop-blur lg:top-0">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
          <ViewTransition name={`member-name-${m.code}`}>
            <h1 className="condense-title text-[40px] sm:text-[60px]">{m.name}</h1>
          </ViewTransition>
          <ViewTransition name={`member-band-${m.code}`}>
            <span className="inline-flex">{m.band ? <BandChip band={m.band} size="lg" /> : <NoLoanChip />}</span>
          </ViewTransition>
        </div>
        <div className="condense-fold flex max-h-[140px] flex-col gap-1.5 overflow-hidden">
          {m.meaning && <p className="max-w-[42em] text-[19px]">{m.meaning}</p>}
          <p className="text-[16px] text-muted">
            {m.note}
            {m.member_since ? ` In the records since ${m.member_since}.` : ""}
          </p>
        </div>
      </header>
      <div aria-hidden="true" className="bead-row" />
      {m.band && <BandKey current={m.band} />}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <Card className="xl:col-span-7" aria-labelledby="mp-reasons">
          <h2 id="mp-reasons" className="mb-1.5 text-[24px] sm:text-[26px]">Top reasons, strongest first</h2>
          {m.reasons.length ? (
            <ol>
              {m.reasons.map((r, i) => {
                const up = r.effect === "raises risk";
                return (
                  <li key={r.feature} className={`flex items-start gap-4 py-4.5 ${i < m.reasons.length - 1 ? "border-b border-line" : ""}`}>
                    <span aria-hidden="true" className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${up ? "bg-high-bg" : "bg-low-bg"}`}>
                      <EffectIcon effect={r.effect} />
                    </span>
                    <span className="flex flex-col gap-1">
                      <span className="text-[18px] font-bold">{r.sentence}</span>
                      <span className={`text-[15px] font-bold capitalize ${up ? "text-high" : "text-low"}`}>{r.effect}</span>
                    </span>
                  </li>
                );
              })}
            </ol>
          ) : (
            <p className="text-[16px] text-muted">
              No early warning: {m.name} has no loan running at the latest meeting.
            </p>
          )}
        </Card>

        <Card tone="ice" className="flex flex-col gap-1 xl:col-span-5" aria-labelledby="mp-source">
          <h2 id="mp-source" className="mb-2.5 text-[24px] sm:text-[26px]">Where this score comes from</h2>
          {m.source ? (
            <>
              <div className="flex flex-col gap-0.5 border-t border-ice-line py-3">
                <span className="text-[14px] text-muted">Based on the meeting of</span>
                <span className="text-[17px] font-bold">
                  {meetingWhen(m.source.meeting_date, m.source.meeting_month)}, ledger page {m.source.page_no}
                </span>
              </div>
              <div className="flex flex-col gap-0.5 border-t border-ice-line py-3">
                <span className="text-[14px] text-muted">Model run</span>
                <span className="text-[17px] font-bold">{m.source.model_label}</span>
              </div>
              <div className="flex flex-col gap-0.5 border-t border-ice-line py-3">
                <span className="text-[14px] text-muted">Scored</span>
                <span className="text-[17px] font-bold">{dayAndTime(m.source.scored_at)}</span>
              </div>
            </>
          ) : (
            <p className="text-[16px]">This chama has not been scored yet.</p>
          )}
          <Link href="/o/about" className="mt-2 text-[15px] font-bold">How the early warning works</Link>
        </Card>

        <Card className="flex flex-col gap-5 xl:col-span-12" aria-labelledby="mp-contrib">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 id="mp-contrib" className="text-[24px] sm:text-[26px]">Monthly contributions</h2>
            {m.contributions.length > 0 && (
              <span className="text-[16px] text-muted">
                Paid at {paid} of the last {m.contributions.length} meetings
                {amounts.length === 1 && amounts[0] ? `, ${money(amounts[0])} each` : ""}
              </span>
            )}
          </div>
          {m.contributions.length ? (
            <div className="relative overflow-x-auto">
              <ol className="relative flex min-w-[640px] gap-2">
                <span aria-hidden="true" className="absolute left-[22px] right-[22px] top-[15px] h-0.5 bg-line" />
                {m.contributions.map((c) => (
                  <li key={c.page_no} className="relative flex min-w-11 flex-1 flex-col items-center gap-2">
                    {c.paid ? (
                      <Bead colour="sun" size={30} />
                    ) : (
                      <span aria-hidden="true" className="block h-[30px] w-[30px] rounded-full border-[3px] border-dashed border-high bg-white" />
                    )}
                    <span className={`text-[14px] ${c.paid ? "text-muted" : "font-bold text-high"}`}>
                      {monthShort(c.meeting_month)}
                      {c.paid ? <span className="sr-only">: paid {money(c.amount)}</span> : ", none"}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          ) : (
            <p className="text-[16px] text-muted">No contributions are recorded in the ledger for recent meetings.</p>
          )}
        </Card>

        <Card className="xl:col-span-12" aria-labelledby="mp-loans">
          <h2 id="mp-loans" className="mb-3 text-[24px] sm:text-[26px]">Loans</h2>
          {m.loans.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[620px] border-collapse text-[16px]">
                <thead>
                  <tr className="text-left text-[14px] text-muted">
                    <th scope="col" className="border-b border-line px-3 py-2.5">Type</th>
                    <th scope="col" className="border-b border-line px-3 py-2.5">Issued</th>
                    <th scope="col" className="border-b border-line px-3 py-2.5">Due</th>
                    <th scope="col" className="border-b border-line px-3 py-2.5">Status</th>
                    <th scope="col" className="border-b border-line px-3 py-2.5 text-right">Outstanding</th>
                  </tr>
                </thead>
                <tbody>
                  {m.loans.map((l, i) => {
                    const s = status(l);
                    return (
                      <tr key={i}>
                        <td className="border-b border-line px-3 py-3.5 font-bold">{LOAN_TYPE[l.type] ?? l.type}</td>
                        <td className="border-b border-line px-3 py-3.5">{month(l.issued_month)}</td>
                        <td className="border-b border-line px-3 py-3.5">{month(l.due_month)}</td>
                        <td className="border-b border-line px-3 py-3.5">
                          <span className="inline-flex items-center gap-2"><Bead colour={s.bead} />{s.text}</span>
                        </td>
                        <td className={`tabular border-b border-line px-3 py-3.5 text-right ${l.running ? "font-bold" : ""}`}>
                          {money(l.outstanding)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-[16px] text-muted">No loans in the records.</p>
          )}
        </Card>

        <Card className="xl:col-span-12" aria-labelledby="mp-timeline">
          <h2 id="mp-timeline" className="mb-3 text-[24px] sm:text-[26px]">Repayments at each meeting</h2>
          {m.repayments.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] border-collapse text-[16px]">
                <thead>
                  <tr className="text-[14px] text-muted">
                    <th scope="col" className="border-b border-line px-3 py-2.5 text-left">Meeting</th>
                    <th scope="col" className="border-b border-line px-3 py-2.5 text-left">Loan</th>
                    <th scope="col" className="border-b border-line px-3 py-2.5 text-right">Balance before</th>
                    <th scope="col" className="border-b border-line px-3 py-2.5 text-right">Repaid</th>
                    <th scope="col" className="border-b border-line px-3 py-2.5 text-right">Interest</th>
                    <th scope="col" className="border-b border-line px-3 py-2.5 text-right">Balance after</th>
                  </tr>
                </thead>
                <tbody>
                  {m.repayments.map((r, i) => (
                    <tr key={i}>
                      <td className="border-b border-line px-3 py-3.5">
                        <span className="inline-flex items-center gap-2.5 font-bold">
                          {r.missed ? (
                            <span aria-hidden="true" className="block h-3.5 w-3.5 rounded-full border-[3px] border-dashed border-high" />
                          ) : (
                            <Bead colour="leaf" size={14} />
                          )}
                          {meetingWhen(r.meeting_date, r.meeting_month)}
                        </span>
                      </td>
                      <td className="border-b border-line px-3 py-3.5">{LOAN_TYPE[r.loan_type] ?? "Normal"}</td>
                      <td className="tabular border-b border-line px-3 py-3.5 text-right">{money(r.balance_before)}</td>
                      <td className={`tabular border-b border-line px-3 py-3.5 text-right ${r.missed ? "font-bold text-high" : ""}`}>
                        {r.missed ? "Missed" : money(r.repaid)}
                      </td>
                      <td className="tabular border-b border-line px-3 py-3.5 text-right">{money(r.interest ?? 0)}</td>
                      <td className="tabular border-b border-line px-3 py-3.5 text-right font-bold">{money(r.balance_after)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-[16px] text-muted">No loan repayments in the records.</p>
          )}
        </Card>
      </div>

      <div className="flex flex-wrap items-center gap-3.5">
        <Link href="/o"
          className="inline-flex min-h-[52px] items-center rounded-button bg-cobalt px-5.5 text-[16px] font-bold text-white no-underline hover:bg-cobalt-dark hover:text-white">
          Back to members to follow up
        </Link>
        {m.source && (
          <Link href={`/o/records/meetings/${m.source.page_no}`}
            className="inline-flex min-h-[52px] items-center rounded-button border-2 border-ink px-5.5 text-[16px] font-bold text-ink no-underline hover:bg-ice hover:text-ink">
            View the meeting of {meetingWhen(m.source.meeting_date, m.source.meeting_month)}
          </Link>
        )}
      </div>
    </PageBody>
  );
}
