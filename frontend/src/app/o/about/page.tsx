import type { Metadata } from "next";
import Link from "next/link";

import { BAND, BandChip } from "@/components/beads";
import { Meeting, Singing } from "@/components/figurines";
import { Card, PageBody, PageHeader } from "@/components/page-header";
import type { Band } from "@/lib/types";

import { BandStory } from "./band-story";

export const metadata: Metadata = { title: "How Kibaba decides" };

// OFF-14 in plain words (Sprint II feedback). The testing figures come from the
// Milestone 2 report, sections 10, 12 and 14; the technical terms are kept to
// the closed section at the end.
const TESTED: { band: Band; missed: string; detail: string }[] = [
  { band: "high", missed: "about 1 in 3", detail: "35 of every 100" },
  { band: "medium", missed: "about 1 in 4", detail: "24 of every 100" },
  { band: "low", missed: "about 1 in 8", detail: "12 of every 100" },
];

export default function AboutPage() {
  return (
    <PageBody>
      <PageHeader title="How Kibaba decides" sub="In plain words: what the colours mean, how they are worked out, and their limits"
        art={<Singing tone="colour" className="h-[140px]" />} />

      <Card className="flex flex-col gap-4">
        <h2 className="text-[26px]">In short</h2>
        <ol className="grid gap-4 md:grid-cols-3">
          {[
            "After each meeting, Kibaba looks at every member who has a loan running.",
            "It reads their own record up to that meeting: repayments, how recently they last missed one, their loans and their contributions.",
            "Members whose records look most like those who missed repayments before get the colours that say “talk to them”.",
          ].map((text, i) => (
            <li key={i} className="flex gap-3 rounded-card bg-ice p-4 text-[17px]">
              <span className="font-display text-[28px] font-extrabold leading-none text-cobalt">{i + 1}</span>
              <span>{text}</span>
            </li>
          ))}
        </ol>
        <p className="max-w-[46em] text-[18px]">
          Kibaba suggests who to talk to. Officials decide what to do. Nothing in Kibaba gives or refuses a loan.
        </p>
      </Card>

      <BandStory />

      <Card className="flex flex-col gap-5" aria-labelledby="about-bands">
        <h2 id="about-bands" className="text-[26px]">How well it worked on the chama&apos;s past records</h2>
        <p className="max-w-[46em] text-[17px] text-subtle">
          Kibaba was tried on ten past years, from 2016 to 2025, each time using only the years before. This is how
          often members of each colour missed a repayment within the next 3 meetings.
        </p>
        <ul className="grid gap-4 md:grid-cols-3">
          {TESTED.map((b) => (
            <li key={b.band} className="flex flex-col gap-3 rounded-card border border-line p-5">
              <BandChip band={b.band} />
              <span className="font-display text-[30px] font-extrabold leading-tight">{b.missed}</span>
              <span className="text-[16px]">missed a repayment within 3 meetings ({b.detail})</span>
            </li>
          ))}
        </ul>
        <p className="text-[16px] text-subtle">
          So most members marked &ldquo;{BAND.high.label}&rdquo; still repaid. The colour is a reason to talk, never a verdict.
        </p>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card tone="cream" className="flex flex-col gap-3">
          <h2 className="text-[26px]">The limits</h2>
          <ul className="flex list-disc flex-col gap-2.5 pl-5 text-[17px]">
            <li>It learned from one chama&apos;s records: 12 members over more than 10 years.</li>
            <li>
              It is better than guessing, but far from certain. Picking members at random would find a missed
              repayment 20 times in 100; Kibaba&apos;s order does about one and a half times as well.
            </li>
            <li>More members are marked &ldquo;{BAND.high.label}&rdquo; lately, because missed repayments really have been more common in 2024 and 2025.</li>
          </ul>
        </Card>

        <Card id="protected" className="relative flex scroll-mt-6 flex-col gap-3 overflow-hidden">
          <Meeting tone="ink" className="pointer-events-none absolute -bottom-4 right-2 hidden w-[180px] opacity-[0.1] md:block" />
          <h2 className="text-[26px]">How the records are protected</h2>
          <ul className="flex max-w-[46em] list-disc flex-col gap-2.5 pl-5 text-[17px]">
            <li>Names are swapped for codes before anything is worked out.</li>
            <li>The list linking names and codes stays in a locked part of the database on the chama&apos;s server.</li>
            <li>Ledger photos are saved without location data and shown only to officials.</li>
            <li>Members see only their own records, never colours or other members.</li>
          </ul>
        </Card>
      </div>

      <Card tone="ice">
        <details>
          <summary className="cursor-pointer text-[18px] font-bold">Technical details, for the curious</summary>
          <div className="mt-4 flex max-w-[52em] flex-col gap-3 text-[16px] text-subtle">
            <p>
              The colours come from a random forest model that estimates whether a member will miss a repayment
              within the next 3 meetings. It was chosen over logistic regression and XGBoost because it ranked members
              as well as any of them with the simplest set-up.
            </p>
            <p>
              At each meeting the members with a loan running are put in order: the top 20% are &ldquo;{BAND.high.label}&rdquo;,
              the next 30% &ldquo;{BAND.medium.label}&rdquo; and the other 50% &ldquo;{BAND.low.label}&rdquo;. The reasons are the three
              parts of the member&apos;s record that moved the estimate most (SHAP values).
            </p>
            <p>
              Testing walked forward one year at a time, 2016 to 2025, so every year was judged by a model that had
              seen only earlier years. Each member page shows which model run made its colour under &ldquo;Technical details&rdquo;.
            </p>
          </div>
        </details>
      </Card>

      <div className="flex flex-wrap items-end justify-between gap-6">
        <Link href="/o"
          className="inline-flex min-h-[52px] items-center rounded-button bg-cobalt px-6 text-[16px] font-bold text-white no-underline hover:bg-cobalt-dark hover:text-white">
          Back to the overview
        </Link>
      </div>
    </PageBody>
  );
}
