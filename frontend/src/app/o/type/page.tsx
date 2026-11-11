import type { Metadata } from "next";
import Link from "next/link";

import { FlowSteps } from "@/components/flow-steps";
import { PageBody, PageHeader } from "@/components/page-header";
import { apiGet } from "@/lib/server-api";
import type { TypedInfo } from "@/lib/types";

import { TypeForm } from "./type-form";

export const metadata: Metadata = { title: "Type a page" };

// The treasurer types the month's page straight in (D-038): the ledger opens
// with every member already on a line and the balances carried from the last
// meeting, so only the amounts paid at this meeting are left to type.
export default async function TypePage() {
  const info = await apiGet<TypedInfo>("/api/typed");
  return (
    <PageBody className="max-w-[960px]">
      <PageHeader title="Type a page" tone="cream"
        sub="No photo needed: open this month's ledger with the members already filled in, then type what each one paid."
        crumbs={<><Link href="/o/scan">Scan a page</Link><span aria-hidden="true" className="mx-2">/</span>Type it in</>} />
      <FlowSteps at="send" typed />
      <TypeForm info={info} />
    </PageBody>
  );
}
