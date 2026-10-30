import type { Metadata } from "next";

import { Bead } from "@/components/beads";
import { Card, PageBody, PageHeader } from "@/components/page-header";
import { money, month } from "@/lib/format";
import { LOAN_TYPE, loanStatus, type Loan } from "@/lib/loans";
import { apiGet } from "@/lib/server-api";

export const metadata: Metadata = { title: "My loans" };

// MEM-2: the member's open and past loans with their status, in the words the
// officials see. Nothing about scores or other members (MEM-3).
export default async function MyLoans() {
  const { loans } = await apiGet<{ loans: Loan[] }>("/api/my/summary");
  const running = loans.filter((l) => l.running);
  const past = loans.filter((l) => !l.running);

  return (
    <PageBody className="max-w-[960px]">
      <PageHeader title="My loans" tone="ice" sub="Every loan of yours in the chama's records, newest first." />
      <LoanList id="loans-running" title="Running" loans={running} empty="You have no loan running." />
      <LoanList id="loans-past" title="Past loans" loans={past} empty="No past loans in the records." />
    </PageBody>
  );
}

function LoanList({ id, title, loans, empty }: { id: string; title: string; loans: Loan[]; empty: string }) {
  return (
    <Card aria-labelledby={id}>
      <h2 id={id} className="mb-3 text-[24px]">
        {title} <span className="text-[18px] font-bold text-muted">({loans.length})</span>
      </h2>
      {loans.length ? (
        <ul>
          {loans.map((l, i) => {
            const s = loanStatus(l);
            return (
              <li key={i} className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-t border-line py-3.5">
                <span className="flex min-w-0 flex-col gap-1">
                  <span className="text-[17px] font-bold">
                    {LOAN_TYPE[l.type] ?? "Other"} loan{l.amount ? ` of ${money(l.amount)}` : ""}
                  </span>
                  <span className="text-[15px] text-muted">
                    Given {month(l.issued_month)}{l.due_month ? `, due ${month(l.due_month)}` : ""}
                  </span>
                  <span className="inline-flex items-center gap-2 text-[15px]"><Bead colour={s.bead} />{s.text}</span>
                </span>
                {l.running && (
                  <span className="flex flex-col items-end">
                    <span className="tabular text-[20px] font-bold">{money(l.outstanding)}</span>
                    <span className="text-[14px] text-muted">still to repay</span>
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-[16px] text-muted">{empty}</p>
      )}
    </Card>
  );
}
