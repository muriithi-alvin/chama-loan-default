import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PageBody, PageHeader } from "@/components/page-header";

import { RunTimeline } from "./run-timeline";

type Params = Promise<{ id: string }>;

export const metadata: Metadata = { title: "Updating the records" };

export default async function RunPage({ params }: { params: Params }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  return (
    <PageBody className="max-w-[960px]">
      <PageHeader title="Updating the records" tone="ice"
        sub="Your page is being added to the records, step by step. This page updates by itself."
        crumbs={<><Link href="/o/uploads">Upload history</Link><span aria-hidden="true" className="mx-2">/</span>Update {id}</>} />
      <RunTimeline id={Number(id)} />
    </PageBody>
  );
}
