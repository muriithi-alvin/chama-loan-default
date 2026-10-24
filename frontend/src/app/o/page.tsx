import { ArrowRight, Camera } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { BandKey } from "@/components/band-key";
import { BandChip, Bead, EffectIcon } from "@/components/beads";
import { CountUp } from "@/components/count-up";
import { Cooking } from "@/components/figurines";
import { InstallHint } from "@/components/install-hint";
import { Card, PageBody, PageHeader } from "@/components/page-header";
import { ago, meetingWhen, money } from "@/lib/format";
import { apiGet } from "@/lib/server-api";
import type { Overview } from "@/lib/types";

import { BandStrands } from "./band-strands";
import { NewScores } from "./new-scores";

export const metadata: Metadata = { title: "Overview" };

export default async function OverviewPage() {
  const data = await apiGet<Overview>("/api/overview");
  const last = data.last_meeting;
  const h = data.health;

  return (
    <PageBody>
      <Cooking tone="ink" className="pointer-events-none absolute bottom-4 right-6 hidden w-[240px] opacity-[0.12] xl:block" />
      <PageHeader
        title="Overview"
        sub={last ? `Last meeting recorded: ${meetingWhen(last.meeting_date, last.meeting_month)}, ledger page ${last.page_no}` : "No meetings recorded yet"}
        action={data.scores && (
          <div className="flex items-center gap-2.5 rounded-full bg-ice py-2.5 pl-3 pr-4 text-[15px]">
            <Bead colour="cobalt" size={14} />
            <span>
              Scored <strong>{ago(data.scores.scored_at)}</strong> with model run <strong>{data.scores.model_label}</strong>
            </span>
          </div>
        )}
      />
      <InstallHint />
      <NewScores data={data} />

      {data.scores_behind && data.scores && (
        <p className="rounded-card bg-cream px-5 py-4 text-[16px]">
          The bands are based on ledger page {data.scores.page_no}; a later page has been recorded and is being scored.
        </p>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <Card className="flex flex-col gap-4 xl:col-span-7" aria-labelledby="ov-bands">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 id="ov-bands" className="text-[24px] sm:text-[26px]">Early warning for the next 3 meetings</h2>
            <span className="text-[15px] text-muted">One bead per member with a loan running</span>
          </div>
          {data.strand.length ? (
            <BandStrands data={data} />
          ) : (
            <p className="rounded-button bg-cream px-4 py-4 text-[16px]">
              No scores yet. Run <code>python -m chama.pipeline score</code>, or scan a page to score the latest meeting.
            </p>
          )}
          <p className="flex items-center gap-2.5 text-[15px] text-muted">
            <span aria-hidden="true" className="flex gap-[3px]">
              <Bead colour="white" /><Bead colour="white" /><Bead colour="white" />
            </span>
            {data.counts.no_loan === 1 ? "1 member has" : `${data.counts.no_loan} members have`} no loan running
          </p>
          <BandKey />
        </Card>

        <section aria-labelledby="ov-actions" className="flex flex-col gap-4 xl:col-span-5">
          <h2 id="ov-actions" className="sr-only">Quick actions</h2>
          <Link href="/o/scan"
            className="lift relative flex min-h-[170px] flex-1 flex-col justify-between gap-4 overflow-hidden rounded-card bg-cobalt p-6 text-white no-underline hover:text-white">
            <svg viewBox="0 0 200 200" aria-hidden="true" className="absolute -right-14 -top-14 h-[200px] w-[200px]">
              <circle cx="100" cy="100" r="88" fill="none" stroke="#F6C343" strokeWidth="9" strokeLinecap="round" strokeDasharray="0.1 17" />
              <circle cx="100" cy="100" r="68" fill="none" stroke="#FFFFFF" strokeWidth="9" strokeLinecap="round" strokeDasharray="0.1 17" opacity="0.6" />
              <circle cx="100" cy="100" r="48" fill="none" stroke="#D62839" strokeWidth="9" strokeLinecap="round" strokeDasharray="0.1 17" />
            </svg>
            <Camera aria-hidden="true" size={34} />
            <span className="relative flex flex-col gap-1">
              <span className="font-display text-[28px] font-extrabold tracking-tight">Scan a page</span>
              <span className="text-[16px] text-cobalt-light">Photograph this month&apos;s ledger page</span>
            </span>
          </Link>
          <Link href="/o/records/meetings"
            className="lift flex min-h-[110px] items-center justify-between gap-4 rounded-card border border-line bg-white px-6 py-5 text-ink no-underline hover:text-ink">
            <span className="flex flex-col gap-1">
              <span className="font-display text-[24px] font-extrabold tracking-tight">View records</span>
              <span className="text-[15px] text-muted">Meetings, pages and loans</span>
            </span>
            <ArrowRight aria-hidden="true" size={26} />
          </Link>
        </section>

        <Card className="xl:col-span-7" aria-labelledby="ov-follow">
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-3">
            <h2 id="ov-follow" className="text-[24px] sm:text-[26px]">Members to follow up</h2>
            <Link href="/o/members" className="text-[15px] font-bold">All members</Link>
          </div>
          {data.follow_up.length ? (
            <ul>
              {data.follow_up.map((m) => (
                <li key={m.code} className="flex flex-wrap items-center gap-x-4 gap-y-2.5 border-t border-line py-4">
                  <span className="flex min-w-0 flex-[1_1_220px] flex-col gap-1.5">
                    <span className="text-[17px] font-bold">{m.name}</span>
                    <span className="flex items-start gap-2 text-[15px] text-subtle">
                      <EffectIcon effect={m.reason.effect} size={16} />
                      <span>
                        {m.reason.sentence}{" "}
                        <span className={`whitespace-nowrap font-bold ${m.reason.effect === "raises risk" ? "text-high" : "text-low"}`}>
                          {m.reason.effect}
                        </span>
                      </span>
                    </span>
                  </span>
                  <BandChip band={m.band} />
                  <Link href={`/o/members/${m.code}`}
                    className="inline-flex min-h-11 items-center rounded-[10px] border-[1.5px] border-ink px-3.5 text-[15px] font-bold text-ink no-underline hover:bg-ice hover:text-ink">
                    Open<span className="sr-only">: {m.name}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="border-t border-line pt-4 text-[16px] text-muted">
              Nobody is in the High or Medium band at the latest meeting.
            </p>
          )}
        </Card>

        <Card tone="cream" className="flex flex-col gap-1.5 xl:col-span-5" aria-labelledby="ov-health">
          <h2 id="ov-health" className="mb-2 text-[24px] sm:text-[26px]">Chama health</h2>
          <div className="flex items-baseline justify-between gap-3 border-t border-cream-line py-3.5">
            <span className="text-[16px] text-subtle">Open loans</span>
            <span className="tabular font-display text-[34px] font-extrabold"><CountUp value={h.open_loans} /></span>
          </div>
          <div className="flex items-baseline justify-between gap-3 border-t border-cream-line py-3.5">
            <span className="text-[16px] text-subtle">Total outstanding</span>
            <span className="tabular font-display text-[30px] font-extrabold sm:text-[34px]">{money(h.outstanding)}</span>
          </div>
          <div className="flex items-baseline justify-between gap-3 border-t border-cream-line py-3.5">
            <span className="max-w-[15em] text-[16px] text-subtle">Running loans that missed a repayment at the last meeting</span>
            <span className="tabular whitespace-nowrap font-display text-[34px] font-extrabold">
              {h.missed_last_meeting} of {h.running_last_meeting}
            </span>
          </div>
          <div aria-hidden="true" className="flex flex-wrap gap-1.5 pt-1.5">
            {Array.from({ length: h.running_last_meeting }, (_, i) => (
              <Bead key={i} colour={i < h.missed_last_meeting ? "red" : "white"} size={18} />
            ))}
          </div>
        </Card>
      </div>

    </PageBody>
  );
}
