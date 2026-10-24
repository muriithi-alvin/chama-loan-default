import type { Metadata } from "next";
import Link from "next/link";

import { BandChip } from "@/components/beads";
import { Meeting, Singing } from "@/components/figurines";
import { Card, PageBody, PageHeader } from "@/components/page-header";

import { BandStory } from "./band-story";

export const metadata: Metadata = { title: "About the scores" };

// OFF-14. Figures from the Milestone 2 report, sections 10, 12 and 14.
const BANDS = [
  { band: "high" as const, share: "The top 20% of scores", missed: "about 1 in 3", detail: "35 of every 100" },
  { band: "medium" as const, share: "The next 30%", missed: "about 1 in 4", detail: "24 of every 100" },
  { band: "low" as const, share: "The other 50%", missed: "about 1 in 8", detail: "12 of every 100" },
];

export default function AboutPage() {
  return (
    <PageBody>
      <PageHeader title="About the scores" sub="How the early warning works, what the bands mean, and its limits" />

      <Card className="flex flex-col gap-4">
        <h2 className="text-[26px]">How the early warning works</h2>
        <p className="max-w-[46em] text-[18px]">
          At each meeting, the early warning looks at every member who has a loan running and at their record up to
          that meeting: their repayments, how recently they last missed one, their loans and their contributions. It
          then puts them in order of how likely it looks that they will miss a repayment within the next 3 meetings.
        </p>
        <p className="max-w-[46em] text-[18px]">
          It suggests who to follow up. Officials decide what to do. Nothing on these pages gives or refuses a loan.
        </p>
      </Card>

      <BandStory />

      <Card className="flex flex-col gap-5" aria-labelledby="about-bands">
        <h2 id="about-bands" className="text-[26px]">What each band means</h2>
        <p className="max-w-[46em] text-[17px] text-subtle">
          The model was tested by going forward through the records one year at a time: each year from 2016 to 2025
          was scored by a model that had seen only the years before it. This is how often each band missed a
          repayment within the next 3 meetings in that test.
        </p>
        <ul className="grid gap-4 md:grid-cols-3">
          {BANDS.map((b) => (
            <li key={b.band} className="flex flex-col gap-3 rounded-card border border-line p-5">
              <BandChip band={b.band} />
              <span className="text-[15px] text-muted">{b.share}</span>
              <span className="font-display text-[30px] font-extrabold leading-tight">{b.missed}</span>
              <span className="text-[16px]">missed a repayment within 3 meetings ({b.detail} in testing)</span>
            </li>
          ))}
        </ul>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card tone="cream" className="flex flex-col gap-3">
          <h2 className="text-[26px]">The limits</h2>
          <ul className="flex list-disc flex-col gap-2.5 pl-5 text-[17px]">
            <li>It learned from one chama&apos;s records: 12 members over more than 10 years.</li>
            <li>
              It ranks members better than chance, but it is far from certain. Picking members at random would find a
              missed repayment 20 times in 100; the early warning&apos;s order does about one and a half times as well.
            </li>
            <li>Most members in the High band still repaid. A band is a reason to talk, never a verdict.</li>
            <li>
              More members are in the High band lately, because missed repayments really have been more common in
              2024 and 2025.
            </li>
          </ul>
        </Card>
        <Card tone="ice" className="flex flex-col gap-3">
          <h2 className="text-[26px]">Why there is no loan-default category yet</h2>
          <p className="text-[17px]">
            The system was also tested on whether a loan would end unpaid. Its bands for that came out in the wrong
            order: fewer loans went unpaid in the Medium band than in the Low band. Until the chama agrees what counts
            as an unpaid loan and there are more such loans to learn from, that category is not shown.
          </p>
        </Card>
      </div>

      <Card id="protected" className="relative flex scroll-mt-6 flex-col gap-3 overflow-hidden">
        <Meeting tone="ink" className="pointer-events-none absolute -bottom-4 right-2 hidden w-[200px] opacity-[0.1] md:block" />
        <h2 className="text-[26px]">How the records are protected</h2>
        <ul className="flex max-w-[46em] list-disc flex-col gap-2.5 pl-5 text-[17px]">
          <li>Names are replaced by codes before any analysis. The model never sees a name.</li>
          <li>The link between names and codes is kept in a restricted part of the database, on this server only.</li>
          <li>Ledger photos are re-saved without location data, kept outside the website&apos;s files, and shown only to officials.</li>
          <li>Members see only their own records, never scores or other members.</li>
          <li>Keys for outside services stay on the server, and the server&apos;s logs hold codes, never names.</li>
        </ul>
      </Card>

      <div className="flex flex-wrap items-end justify-between gap-6">
        <Link href="/o"
          className="inline-flex min-h-[52px] items-center rounded-button bg-cobalt px-6 text-[16px] font-bold text-white no-underline hover:bg-cobalt-dark hover:text-white">
          Back to members to follow up
        </Link>
        <Singing tone="colour" className="w-[260px] opacity-80" />
      </div>
    </PageBody>
  );
}
