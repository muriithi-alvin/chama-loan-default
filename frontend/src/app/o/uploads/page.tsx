import { Camera } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Bead } from "@/components/beads";
import { Market } from "@/components/figurines";
import { Card, PageBody, PageHeader } from "@/components/page-header";
import { dayAndTime } from "@/lib/format";
import { apiGet } from "@/lib/server-api";
import type { Upload } from "@/lib/types";

export const metadata: Metadata = { title: "Upload history" };

const STATUS: Record<string, { text: string; bead: "cobalt" | "leaf" | "red" | "sun" | "empty" }> = {
  queued: { text: "Waiting to be read", bead: "empty" },
  reading: { text: "Being read", bead: "cobalt" },
  ready: { text: "Ready to check", bead: "sun" },
  failed: { text: "Could not be read", bead: "red" },
  accepted: { text: "Accepted", bead: "leaf" },
  discarded: { text: "Discarded", bead: "empty" },
};

function next(u: Upload): { href: string; label: string } {
  if (u.status === "ready") return { href: `/o/scans/${u.id}/review`, label: u.source === "typed" ? "Carry on typing" : "Review" };
  if (u.status === "accepted" && u.run_id) return { href: `/o/runs/${u.run_id}`, label: "Records update" };
  return { href: `/o/scans/${u.id}`, label: "Status" };
}

export default async function UploadsPage() {
  const { uploads } = await apiGet<{ uploads: Upload[] }>("/api/uploads");
  return (
    <PageBody>
      <PageHeader title="Upload history" tone="ice" sub="Every page scanned or typed in, who sent it and what happened to it."
        action={<Link href="/o/scan" className="inline-flex min-h-12 items-center gap-2 rounded-button bg-cobalt px-5 text-[16px] font-bold text-white no-underline hover:bg-cobalt-dark hover:text-white"><Camera aria-hidden="true" size={18} /> Scan a page</Link>} />
      {uploads.length === 0 ? (
        <Card tone="cream" className="relative flex min-h-[220px] flex-col items-start justify-center gap-4 overflow-hidden">
          <Market tone="ink" className="pointer-events-none absolute -bottom-6 right-4 w-[200px] opacity-[0.12]" />
          <p className="font-display text-[26px] font-extrabold">No scans yet. Scan your first ledger page.</p>
          <Link href="/o/scan" className="inline-flex min-h-12 items-center gap-2 rounded-button bg-cobalt px-5 text-[16px] font-bold text-white no-underline hover:bg-cobalt-dark hover:text-white">
            <Camera aria-hidden="true" size={18} /> Scan a page
          </Link>
        </Card>
      ) : (
        <ul className="flex flex-col gap-3">
          {uploads.map((u) => {
            const s = STATUS[u.status];
            const go = next(u);
            return (
              <li key={u.id} className="flex flex-wrap items-center gap-x-5 gap-y-3 rounded-card border border-line bg-white px-5 py-4">
                <span className="flex min-w-0 flex-[1_1_260px] flex-col gap-1">
                  <span className="text-[17px] font-bold">
                    {u.source === "typed" ? "Typed page" : "Scan"} {u.id}{u.page_no ? `, now ledger page ${u.page_no}` : ""}
                  </span>
                  <span className="text-[15px] text-muted">
                    {u.source === "typed" ? "Typed in" : u.parts > 1 ? `${u.parts} photos sent` : "Sent"} by {u.uploaded_by} on {dayAndTime(u.created_at)}
                  </span>
                </span>
                <span className="inline-flex items-center gap-2 text-[15px] font-bold"><Bead colour={s.bead} size={12} />{s.text}</span>
                <span className="flex gap-2">
                  <Link href={go.href} className="inline-flex min-h-11 items-center rounded-[10px] border-[1.5px] border-ink px-3.5 text-[15px] font-bold text-ink no-underline hover:bg-ice hover:text-ink">
                    {go.label}<span className="sr-only"> for scan {u.id}</span>
                  </Link>
                  {(u.edits ?? 0) > 0 && (
                    <Link href={`/o/edits?upload=${u.id}`} className="inline-flex min-h-11 items-center rounded-[10px] px-3.5 text-[15px] font-bold no-underline hover:bg-ice">
                      {u.edits} {u.edits === 1 ? "edit" : "edits"}<span className="sr-only"> on scan {u.id}</span>
                    </Link>
                  )}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </PageBody>
  );
}
