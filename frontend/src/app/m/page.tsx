import type { Metadata } from "next";
import Link from "next/link";

import { Bead } from "@/components/beads";
import { CountUp } from "@/components/count-up";
import { Market, Singing } from "@/components/figurines";
import { Card, PageBody, PageHeader } from "@/components/page-header";
import { meetingWhen, money, month, monthShort } from "@/lib/format";
import { apiGet } from "@/lib/server-api";
import type { MemberPage } from "@/lib/types";

export const metadata: Metadata = { title: "My summary" };

type Summary = Pick<MemberPage, "name" | "member_since" | "loans" | "repayments" | "contributions"> & {
  balance: number;
  next_due_month: string | null;
};

const TYPE: Record<string, string> = { normal: "Normal loan", emergency: "Emergency loan", school_fees: "School-fees loan" };

// MEM-1: the member's own money, in the ledger's words. Nothing about scores
// or other members (MEM-3).
export default async function MySummary() {
  const s = await apiGet<Summary>("/api/my/summary");
  const running = s.loans.filter((l) => l.running);
  const paid = s.contributions.filter((c) => c.paid).length;

  return (
    <PageBody className="max-w-[960px]">
      <PageHeader title={<>Habari, {s.name.split(" ")[0]}</>}
        sub={`${s.name}${s.member_since ? `, in the chama's records since ${s.member_since}` : ""}`}
        art={<Market tone="colour" className="h-[140px]" />} />

      <div className="grid gap-5 md:grid-cols-2">
        <Card tone="cream" className="flex flex-col gap-2">
          <h2 className="text-[20px]">Loan balance</h2>
          <p className="tabular font-display text-[44px] font-extrabold leading-none">
            <CountUp value={s.balance} as="money" />
          </p>
          <p className="text-[16px] text-subtle">
            {running.length === 0 ? "You have no loan running." : `${running.length} ${running.length === 1 ? "loan" : "loans"} running`}
          </p>
          <Link href="/m/loans" className="mt-1 text-[16px] font-bold">
            See all my loans ({s.loans.length})
          </Link>
        </Card>
        <Card tone="ice" className="flex flex-col gap-2">
          <h2 className="text-[20px]">Next due</h2>
          <p className="font-display text-[36px] font-extrabold leading-tight">{s.next_due_month ? month(s.next_due_month) : "Nothing due"}</p>
          <p className="text-[16px] text-subtle">
            {s.contributions.length ? `Contributions paid at ${paid} of the last ${s.contributions.length} meetings` : "No contributions recorded yet"}
          </p>
        </Card>
      </div>

      {running.length > 0 && (
        <Card aria-labelledby="my-loans">
          <h2 id="my-loans" className="mb-3 text-[24px]">My loans running</h2>
          <ul>
            {running.map((l, i) => (
              <li key={i} className="flex flex-wrap items-baseline justify-between gap-3 border-t border-line py-3.5">
                <span className="flex flex-col">
                  <span className="text-[17px] font-bold">{TYPE[l.type] ?? "Loan"}</span>
                  <span className="text-[15px] text-muted">Given {month(l.issued_month)}{l.due_month ? `, due ${month(l.due_month)}` : ""}</span>
                </span>
                <span className="tabular text-[20px] font-bold">{money(l.outstanding)}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card aria-labelledby="my-contrib" className="flex flex-col gap-5">
        <h2 id="my-contrib" className="text-[24px]">My monthly contributions</h2>
        {s.contributions.length ? (
          <div className="overflow-x-auto">
            <ol className="flex min-w-[560px] gap-2">
              {s.contributions.map((c) => (
                <li key={c.page_no} className="flex min-w-11 flex-1 flex-col items-center gap-2">
                  {c.paid ? <Bead colour="sun" size={28} /> : <span aria-hidden="true" className="block h-7 w-7 rounded-full border-[3px] border-dashed border-high" />}
                  <span className={`text-[14px] ${c.paid ? "text-muted" : "font-bold text-high"}`}>
                    {monthShort(c.meeting_month)}{c.paid ? <span className="sr-only">: {money(c.amount)} paid</span> : ", none"}
                  </span>
                </li>
              ))}
            </ol>
          </div>
        ) : (
          <p className="text-[16px] text-muted">No contributions are recorded in the ledger for recent meetings.</p>
        )}
      </Card>

      <Card aria-labelledby="my-repay">
        <h2 id="my-repay" className="mb-3 text-[24px]">My repayments</h2>
        {s.repayments.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-[16px]">
              <thead>
                <tr className="text-[14px] text-muted">
                  <th scope="col" className="border-b border-line px-3 py-2.5 text-left">Meeting</th>
                  <th scope="col" className="border-b border-line px-3 py-2.5 text-right">Balance before</th>
                  <th scope="col" className="border-b border-line px-3 py-2.5 text-right">Repaid</th>
                  <th scope="col" className="border-b border-line px-3 py-2.5 text-right">Balance after</th>
                </tr>
              </thead>
              <tbody>
                {s.repayments.map((r, i) => (
                  <tr key={i}>
                    <td className="border-b border-line px-3 py-3 font-bold">{meetingWhen(r.meeting_date, r.meeting_month)}</td>
                    <td className="tabular border-b border-line px-3 py-3 text-right">{money(r.balance_before)}</td>
                    <td className="tabular border-b border-line px-3 py-3 text-right">{r.missed ? "None" : money(r.repaid)}</td>
                    <td className="tabular border-b border-line px-3 py-3 text-right font-bold">{money(r.balance_after)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-[16px] text-muted">No loan repayments in the records.</p>
        )}
      </Card>

      <Singing className="mx-auto w-[260px] opacity-70" />
    </PageBody>
  );
}
