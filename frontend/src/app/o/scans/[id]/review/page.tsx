import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PageBody, PageHeader } from "@/components/page-header";
import { apiGet } from "@/lib/server-api";
import type { Draft } from "@/lib/types";

import { Review } from "./review";

type Params = Promise<{ id: string }>;

export const metadata: Metadata = { title: "Check the rows" };

export default async function ReviewPage({ params }: { params: Params }) {
  const { id } = await params;
  if (!/^\d+$/.test(id)) notFound();
  const draft = await apiGet<Draft>(`/api/uploads/${id}/draft`);
  return (
    <PageBody className="max-w-[1440px]">
      {draft.source === "typed" ? (
        <PageHeader title="Type the amounts" tone="cream"
          sub="The members and the balances they carried are filled in. Type what each one paid at this meeting, then accept the page."
          crumbs={<><Link href="/o/uploads">Upload history</Link><span aria-hidden="true" className="mx-2">/</span>Typed page {id}</>} />
      ) : (
        <PageHeader title="Check the rows"
          sub="Compare each row with the photo, correct anything misread, and match every name. Changes are saved as you go."
          crumbs={<><Link href="/o/uploads">Upload history</Link><span aria-hidden="true" className="mx-2">/</span>
            <Link href={`/o/scans/${id}`}>Scan {id}</Link><span aria-hidden="true" className="mx-2">/</span>Review</>} />
      )}
      <Review initial={draft} />
    </PageBody>
  );
}
