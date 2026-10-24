import { ArrowDown, ArrowUp, ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { ViewTransition } from "react";

import { BandKey } from "@/components/band-key";
import { BandChip, NoLoanChip } from "@/components/beads";
import { Card, PageBody, PageHeader } from "@/components/page-header";
import { meetingWhen, money } from "@/lib/format";
import { apiGet } from "@/lib/server-api";
import type { Band, MemberRow, ScoreSource } from "@/lib/types";

import { MemberFilters } from "./member-filters";

export const metadata: Metadata = { title: "Members" };

type Search = Promise<{ band?: string; q?: string; sort?: string; dir?: string }>;
const SORTS = ["name", "band", "open_loans", "outstanding", "missed_last_3"] as const;
type Sort = (typeof SORTS)[number];
const BAND_RANK: Record<Band, number> = { high: 0, medium: 1, low: 2 };

function sortValue(m: MemberRow, sort: Sort): number | string {
  if (sort === "name") return m.name.toLowerCase();
  if (sort === "band") return m.band ? BAND_RANK[m.band] : 3;
  return m[sort] ?? -1;
}

export default async function MembersPage({ searchParams }: { searchParams: Search }) {
  const params = await searchParams;
  const { members, scores } = await apiGet<{ members: MemberRow[]; scores: ScoreSource | null }>("/api/members");
  const sort: Sort = SORTS.includes(params.sort as Sort) ? (params.sort as Sort) : "band";
  const dir = params.dir === "desc" ? -1 : 1;
  const band = ["high", "medium", "low", "none"].includes(params.band ?? "") ? params.band : undefined;
  const q = (params.q ?? "").trim().toLowerCase();

  const rows = members
    .filter((m) => !band || (band === "none" ? !m.band : m.band === band))
    .filter((m) => !q || m.name.toLowerCase().includes(q))
    .sort((a, b) => {
      const x = sortValue(a, sort);
      const y = sortValue(b, sort);
      if (x < y) return -dir;
      if (x > y) return dir;
      return a.name.localeCompare(b.name);
    });

  const link = (column: Sort) => {
    const next = new URLSearchParams();
    if (band) next.set("band", band);
    if (params.q) next.set("q", params.q);
    next.set("sort", column);
    if (sort === column && dir === 1) next.set("dir", "desc");
    return `/o/members?${next.toString()}`;
  };
  const header = (column: Sort, label: string, numeric = false) => {
    const active = sort === column;
    return (
      <th scope="col" aria-sort={active ? (dir === 1 ? "ascending" : "descending") : "none"}
        className={`border-b border-line px-3 py-2.5 text-[14px] font-bold text-muted ${numeric ? "text-right" : "text-left"}`}>
        <Link href={link(column)} className={`inline-flex items-center gap-1 text-muted no-underline hover:text-ink ${active ? "text-ink" : ""}`}>
          {label}
          {active && (dir === 1 ? <ArrowUp aria-hidden="true" size={14} /> : <ArrowDown aria-hidden="true" size={14} />)}
        </Link>
      </th>
    );
  };

  return (
    <PageBody>
      <PageHeader title="Members"
        sub={scores ? `Bands from the meeting of ${meetingWhen(scores.meeting_date, scores.meeting_month)}, ledger page ${scores.page_no}` : "No scores yet"} />
      <MemberFilters band={band} q={params.q ?? ""} total={members.length} shown={rows.length} />
      <BandKey />

      <Card className="hidden p-0 sm:block sm:p-0">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <caption className="sr-only">Members, their band and their loans. Select a column heading to sort.</caption>
            <thead>
              <tr>
                {header("name", "Name")}
                {header("band", "Band")}
                {header("open_loans", "Open loans", true)}
                {header("outstanding", "Outstanding", true)}
                {header("missed_last_3", "Missed in last 3 meetings", true)}
                <th scope="col" className="border-b border-line px-3 py-2.5"><span className="sr-only">Open</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => (
                <tr key={m.code} className="group transition-colors hover:bg-ice/60">
                  <td className="border-b border-line px-3 py-3.5 text-[16px] font-bold">
                    <ViewTransition name={`member-name-${m.code}`}><span>{m.name}</span></ViewTransition>
                  </td>
                  <td className="border-b border-line px-3 py-3.5">
                    <ViewTransition name={`member-band-${m.code}`}>
                      <span className="inline-flex">{m.band ? <BandChip band={m.band} size="sm" /> : <NoLoanChip />}</span>
                    </ViewTransition>
                  </td>
                  <td className="tabular border-b border-line px-3 py-3.5 text-right text-[16px]">{m.open_loans}</td>
                  <td className="tabular border-b border-line px-3 py-3.5 text-right text-[16px]">{m.outstanding ? money(m.outstanding) : "–"}</td>
                  <td className="tabular border-b border-line px-3 py-3.5 text-right text-[16px]">{m.missed_last_3 ?? "–"}</td>
                  <td className="border-b border-line px-3 py-3.5 text-right">
                    <Link href={`/o/members/${m.code}`}
                      className="inline-flex min-h-11 items-center gap-1 rounded-[10px] px-3 text-[15px] font-bold no-underline hover:bg-ice">
                      Open<span className="sr-only">: {m.name}</span><ChevronRight aria-hidden="true" size={16} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {rows.length === 0 && <p className="px-6 py-6 text-[16px] text-muted">No member matches these filters.</p>}
      </Card>

      <ul className="flex flex-col gap-3 sm:hidden">
        {rows.map((m) => (
          <li key={m.code}>
            <Link href={`/o/members/${m.code}`}
              className="flex flex-col gap-2.5 rounded-card border border-line bg-white p-5 text-ink no-underline active:bg-ice">
              <span className="flex items-center justify-between gap-3">
                <span className="text-[17px] font-bold">{m.name}</span>
                {m.band ? <BandChip band={m.band} size="sm" /> : <NoLoanChip />}
              </span>
              <span className="grid grid-cols-3 gap-2 text-[14px] text-muted">
                <span>Open loans<br /><strong className="tabular text-[16px] text-ink">{m.open_loans}</strong></span>
                <span>Outstanding<br /><strong className="tabular text-[16px] text-ink">{m.outstanding ? money(m.outstanding) : "–"}</strong></span>
                <span>Missed, last 3<br /><strong className="tabular text-[16px] text-ink">{m.missed_last_3 ?? "–"}</strong></span>
              </span>
            </Link>
          </li>
        ))}
        {rows.length === 0 && <li className="text-[16px] text-muted">No member matches these filters.</li>}
      </ul>
    </PageBody>
  );
}
