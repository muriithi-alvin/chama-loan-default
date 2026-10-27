// Loan wording shared by the officials' member page and the members' own
// pages, so a member reads the same words about a loan as the officials do.
import { month } from "./format";
import type { MemberPage } from "./types";

export type Loan = MemberPage["loans"][number];

export const LOAN_TYPE: Record<string, string> = {
  normal: "Normal", emergency: "Emergency", school_fees: "School fees", top_up: "Top-up", other: "Other",
};

export function loanStatus(loan: Loan) {
  if (loan.running && loan.status === "overdue") return { text: "Running, past its due month", bead: "red" as const };
  if (loan.running) return { text: "Running", bead: "cobalt" as const };
  if (loan.status === "topped_up") {
    return { text: loan.rolled_into_month ? `Rolled into the ${month(loan.rolled_into_month)} loan` : "Rolled into a bigger loan", bead: "empty" as const };
  }
  if (loan.status === "lost_track") return { text: "No longer in the records", bead: "empty" as const };
  if (loan.status === "repaid_late") return { text: "Repaid after its due month", bead: "leaf" as const };
  return { text: "Repaid", bead: "leaf" as const };
}
