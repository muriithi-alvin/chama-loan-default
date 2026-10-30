import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PageBody, PageHeader } from "@/components/page-header";

import { ScanStatus } from "./scan-status";

type Params = Promise<{ id: string }>;

export const metadata: Metadata = { title: "Scan status" };

export default async function ScanStatusPage({ params }: { params: Params }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  return (
    <PageBody className="max-w-[960px]">
      <PageHeader title="Reading the page" tone="ice"
        crumbs={<><Link href="/o/uploads">Upload history</Link><span aria-hidden="true" className="mx-2">/</span>Scan {id}</>} />
      <ScanStatus id={Number(id)} />
    </PageBody>
  );
}
