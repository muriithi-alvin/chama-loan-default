import type { Metadata } from "next";

import { PageBody, PageHeader } from "@/components/page-header";

import { ScanForm } from "./scan-form";

export const metadata: Metadata = { title: "Scan a page" };

export default function ScanPage() {
  return (
    <PageBody className="max-w-[960px]">
      <PageHeader title="Scan a page" tone="ice" sub="Photograph this month's ledger page. You will check every row before it is saved." />
      <ScanForm />
    </PageBody>
  );
}
