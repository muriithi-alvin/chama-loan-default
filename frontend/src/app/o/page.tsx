import { ArrowRight, Camera } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { BandKey } from "@/components/band-key";
import { BAND, BandChip, Bead, BeadArc, EFFECT_WORDS, EffectIcon } from "@/components/beads";
import { CountUp } from "@/components/count-up";
import { Cooking } from "@/components/figurines";
import { InstallHint } from "@/components/install-hint";
import { LanguageSwitch } from "@/components/language-switch";
import { Card, PageBody, PageHeader } from "@/components/page-header";
import { ago, meetingWhen, money } from "@/lib/format";
import { apiGet } from "@/lib/server-api";
import type { Band, Overview } from "@/lib/types";

import { BandStrands } from "./band-strands";
import { NewScores } from "./new-scores";

export const metadata: Metadata = { title: "Overview" };

const TILES: Band[] = ["high", "medium", "low"];
const TILE_STYLE: Record<Band, string> = {
  high: "bg-high-bg text-high",
  medium: "bg-medium-bg text-medium",
  low: "bg-low-bg text-low",
};

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");
}

export default async function OverviewPage() {
  const data = await apiGet<Overview>("/api/overview");
  const last = data.last_meeting;
  const h = data.health;
  const when = last ? meetingWhen(last.meeting_date, last.meeting_month) : null;

  return (
    <PageBody>
      <PageHeader
        title="Overview"
        sub={when
          ? <>From the meeting of <strong>{when}</strong>{data.scores && <>, updated {ago(data.scores.scored_at)}</>}</>
          : "No meetings recorded yet"}
        art={<Cooking tone="colour" className="h-[150px]" />}
      />
      <InstallHint />
      <NewScores data={data} />

      {data.scores_behind && data.scores && (
        <p className="rounded-card bg-cream px-5 py-4 text-[16px]">
          The colours are from ledger page {data.scores.page_no}. A newer page has been saved and is being checked.
        </p>
      )}

      {data.strand.length > 0 && (
        <section aria-label="Members by colour" className="grid gap-4 sm:grid-cols-3">
          {TILES.map((band) => (
            <Link key={band} href={`/o/members?band=${band}`}
              className={`lift relative flex min-h-[150px] flex-col justify-between gap-3 overflow-hidden rounded-card p-5 no-underline ${TILE_STYLE[band]}`}>
              <span aria-hidden="true" className="absolute right-4 top-4 flex gap-1.5">
                {Array.from({ length: BAND[band].beads }, (_, i) => <Bead key={i} colour={BAND[band].colour} size={18} />)}
              </span>
              <span className="tabular font-display text-[56px] font-extrabold leading-none"><CountUp value={data.counts[band]} /></span>
              <span className="flex flex-col gap-0.5">
                <span className="font-display text-[22px] font-extrabold leading-tight">{BAND[band].label}</span>
                <span className="text-[14px] text-ink/80">{data.counts[band] === 1 ? "member" : "members"} · see who</span>
              </span>
            </Link>
          ))}
        </section>
      )}

      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-12">
        <div className="flex flex-col gap-5 xl:col-span-7">
          <Card className="flex flex-col gap-4" aria-labelledby="ov-bands">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 id="ov-bands" className="text-[24px] sm:text-[26px]">Who might miss a repayment soon</h2>
              <span className="text-[15px] text-muted">One bead per member with a loan running</span>
            </div>
            {data.strand.length ? (
              <BandStrands data={data} />
            ) : (
              <p className="rounded-button bg-cream px-4 py-4 text-[16px]">
                Nothing to show yet. Scan this month&apos;s ledger page to see who to follow up.
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
          <Card aria-labelledby="ov-follow">
            <div className="mb-2 flex flex-wrap items-baseline justify-between gap-3">
              <h2 id="ov-follow" className="text-[24px] sm:text-[26px]">Members to talk to</h2>
              <span className="flex flex-wrap items-center gap-3">
                <LanguageSwitch language={data.language} />
                <Link href="/o/members" className="text-[15px] font-bold">All members</Link>
              </span>
            </div>
            {data.follow_up.length ? (
              <ul>
                {data.follow_up.map((m) => (
                  <li key={m.code} className="flex flex-wrap items-center gap-x-4 gap-y-2.5 border-t border-line py-4">
                    <span aria-hidden="true"
                      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full font-display text-[16px] font-extrabold ${TILE_STYLE[m.band]}`}>
                      {initials(m.name)}
                    </span>
                    <span className="flex min-w-0 flex-[1_1_200px] flex-col gap-1.5">
                      <span className="text-[17px] font-bold">{m.name}</span>
                      <span className="flex items-start gap-2 text-[15px] text-subtle">
                        <EffectIcon effect={m.reason.effect} size={16} />
                        <span lang={data.language}>
                          {m.reason.sentence}:{" "}
                          <span className={`font-bold ${m.reason.effect === "raises risk" ? "text-high" : "text-low"}`}>
                            {EFFECT_WORDS[data.language].short[m.reason.effect]}
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
                Nobody needs following up after the latest meeting.
              </p>
            )}
          </Card>
        </div>
        <div className="flex flex-col gap-5 xl:col-span-5">
          <section aria-labelledby="ov-actions" className="flex flex-col gap-4">
            <h2 id="ov-actions" className="sr-only">Quick actions</h2>
            <Link href="/o/scan"
              className="lift relative flex min-h-[190px] flex-col justify-between gap-4 overflow-hidden rounded-card bg-cobalt p-6 text-white no-underline hover:text-white">
              <BeadArc light className="absolute -right-14 -top-14 h-[200px] w-[200px]" />
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
                <span className="text-[15px] text-muted">Every meeting, page by page</span>
              </span>
              <ArrowRight aria-hidden="true" size={26} />
            </Link>
          </section>
          <Card tone="cream" className="flex flex-col gap-1.5" aria-labelledby="ov-health">
            <h2 id="ov-health" className="mb-2 text-[24px] sm:text-[26px]">The chama at a glance</h2>
            <div className="flex items-baseline justify-between gap-3 border-t border-cream-line py-3.5">
              <span className="text-[16px] text-subtle">Loans running</span>
              <span className="tabular font-display text-[34px] font-extrabold"><CountUp value={h.open_loans} /></span>
            </div>
            <div className="flex items-baseline justify-between gap-3 border-t border-cream-line py-3.5">
              <span className="text-[16px] text-subtle">Still to be repaid</span>
              <span className="tabular font-display text-[30px] font-extrabold sm:text-[34px]">{money(h.outstanding)}</span>
            </div>
            <div className="flex items-baseline justify-between gap-3 border-t border-cream-line py-3.5">
              <span className="max-w-[15em] text-[16px] text-subtle">Members who missed a repayment at the last meeting</span>
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
      </div>
    </PageBody>
  );
}
