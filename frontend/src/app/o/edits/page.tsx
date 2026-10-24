import { Lock } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Card, PageBody, PageHeader } from "@/components/page-header";
import { dayAndTime } from "@/lib/format";
import { apiGet } from "@/lib/server-api";
import type { Edit } from "@/lib/types";

export const metadata: Metadata = { title: "Edit record" };

type Search = Promise<{ upload?: string }>;

const COLUMN: Record<string, string> = {
  line_no: "No.", member_name: "Name", monthly: "Monthly", loan_before: "Balance before", repayment: "Repaid",
  interest: "Interest", loan_after: "Balance after", due: "Due", loan_type: "Type", remarks: "Remarks",
  meeting_date: "Meeting date", contribution_total: "Contributions total", brought_forward: "Brought forward",
  total_collection: "Total collection", cash: "Cash", banked: "Banked", next_meeting: "Next meeting",
  host: "Host", notes: "Notes", column_headers: "Column headings", loan_date: "Date", amount: "Amount", unclear: "Hard to read",
};
const TABLE: Record<string, string> = { statements: "member line", meetings: "page totals", new_loans: "new loan", names: "name" };

function what(e: Edit): string {
  if (e.action === "add_row") return `Added a ${TABLE[e.tbl] ?? "row"}`;
  if (e.action === "delete_row") return `Deleted a ${TABLE[e.tbl] ?? "row"}${e.old_value ? ` (${e.old_value})` : ""}`;
  if (e.action === "match_name") return `Matched “${e.col}”`;
  return `Changed ${COLUMN[e.col ?? ""] ?? e.col} on a ${TABLE[e.tbl] ?? "row"}`;
}

export default async function EditsPage({ searchParams }: { searchParams: Search }) {
  const { upload } = await searchParams;
  const filter = upload && /^\d+$/.test(upload) ? upload : null;
  const { edits } = await apiGet<{ edits: Edit[] }>(`/api/edits${filter ? `?upload=${filter}` : ""}`);
  return (
    <PageBody>
      <PageHeader title="Edit record" sub={filter ? `Changes made while reviewing scan ${filter}` : "Every change made while reviewing scanned pages"}
        action={filter ? <Link href="/o/edits" className="font-bold">Show every scan</Link> : undefined} />
      <p className="flex items-center gap-2 text-[15px] text-muted">
        <Lock aria-hidden="true" size={16} /> Entries can only be added. The database refuses any change or deletion.
      </p>
      {edits.length === 0 ? (
        <Card tone="cream"><p className="text-[17px]">No changes recorded yet. They appear here as officials correct scanned pages.</p></Card>
      ) : (
        <Card className="p-0 sm:p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse text-[15px]">
              <thead>
                <tr className="text-left text-[14px] text-muted">
                  <th scope="col" className="border-b border-line px-4 py-3">When</th>
                  <th scope="col" className="border-b border-line px-3 py-3">Who</th>
                  <th scope="col" className="border-b border-line px-3 py-3">Scan</th>
                  <th scope="col" className="border-b border-line px-3 py-3">What</th>
                  <th scope="col" className="border-b border-line px-3 py-3">From</th>
                  <th scope="col" className="border-b border-line px-3 py-3">To</th>
                </tr>
              </thead>
              <tbody>
                {edits.map((e) => (
                  <tr key={e.id}>
                    <td className="whitespace-nowrap border-b border-line px-4 py-3">{dayAndTime(e.edited_at)}</td>
                    <td className="border-b border-line px-3 py-3 font-bold">{e.edited_by_name}</td>
                    <td className="border-b border-line px-3 py-3"><Link href={`/o/scans/${e.upload_id}`}>Scan {e.upload_id}</Link></td>
                    <td className="border-b border-line px-3 py-3">{what(e)}</td>
                    <td className="border-b border-line px-3 py-3 text-muted">{e.action === "edit" || e.action === "match_name" ? e.old_value ?? "(blank)" : ""}</td>
                    <td className="border-b border-line px-3 py-3 font-bold">{e.action === "edit" || e.action === "match_name" ? e.new_value ?? "(blank)" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </PageBody>
  );
}
