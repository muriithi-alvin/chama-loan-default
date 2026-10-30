import { ArrowRight, Camera, HandHeart, ListChecks, Lock, ShieldCheck, Users } from "lucide-react";
import Link from "next/link";

import { BAND, BandChip, Bead, BeadArc, Logo } from "@/components/beads";
import { Cooking, Market, Meeting, Singing } from "@/components/figurines";
import type { Band } from "@/lib/types";

// The landing page (Sprint II feedback: the start of the site was too plain).
// Beads, bead rings and the wire figurines only; no real chama data, and the
// names in the phone picture are the demo chama's fictional ones.

const STEPS = [
  { icon: Camera, title: "Snap the page", text: "After each meeting, photograph the ledger page with any phone." },
  { icon: ListChecks, title: "Check what was read", text: "Kibaba reads every line. You check the names and numbers before anything is saved." },
  { icon: Users, title: "See who to follow up", text: "Each member with a loan gets a colour, with the reasons from their own record." },
];

const BANDS: Band[] = ["high", "medium", "low"];
const TILE: Record<Band, string> = {
  high: "bg-high-bg text-high",
  medium: "bg-medium-bg text-medium",
  low: "bg-low-bg text-low",
};

const PHONE_ROWS: { name: string; band: Band; why: string }[] = [
  { name: "Wanjiru Kamau", band: "high", why: "Missed a repayment at this meeting" },
  { name: "Kawira Mutembei", band: "medium", why: "Repaid less over the last 3 meetings" },
  { name: "Ndinda Kioko", band: "low", why: "Repaid at each of the last 3 meetings" },
];

function StepRing({ n }: { n: number }) {
  return (
    <span className="relative flex h-16 w-16 shrink-0 items-center justify-center">
      <svg viewBox="0 0 64 64" aria-hidden="true" className="absolute inset-0">
        <circle cx="32" cy="32" r="27" fill="none" stroke="#2547A8" strokeWidth="6" strokeLinecap="round" strokeDasharray="0.1 10.5" />
      </svg>
      <span className="font-display text-[26px] font-extrabold text-ink">{n}</span>
    </span>
  );
}

/** The Overview, drawn small inside a phone. */
function Phone() {
  return (
    <div aria-hidden="true" className="relative mx-auto w-[320px] rotate-[2deg] rounded-[38px] bg-ink p-3 shadow-[0_30px_60px_rgba(20,33,61,.28)]">
      <div className="overflow-hidden rounded-[28px] bg-white">
        <div className="flex items-center gap-2 bg-cream px-4 pb-3 pt-5">
          <Logo size={26} />
          <span className="font-display text-[17px] font-extrabold">Overview</span>
        </div>
        <div className="bead-edge !mb-0 bg-cream" />
        <div className="grid grid-cols-3 gap-1.5 p-3">
          {BANDS.map((b, i) => (
            <div key={b} className={`flex flex-col gap-1 rounded-[12px] p-2 ${TILE[b]}`}>
              <span className="font-display text-[24px] font-extrabold leading-none">{[3, 1, 2][i]}</span>
              <span className="text-[10px] font-bold leading-tight">{BAND[b].label}</span>
            </div>
          ))}
        </div>
        <ul className="flex flex-col gap-2 px-3 pb-4">
          {PHONE_ROWS.map((r) => (
            <li key={r.name} className="flex items-center gap-2.5 rounded-[12px] border border-line px-2.5 py-2">
              <span className="flex gap-[2px]">
                {Array.from({ length: BAND[r.band].beads }, (_, i) => <Bead key={i} colour={BAND[r.band].colour} size={9} />)}
              </span>
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-[12px] font-bold">{r.name}</span>
                <span className="truncate text-[10px] text-muted">{r.why}</span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function Landing() {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1200px] items-center gap-3 px-4 py-3 sm:px-8">
          <Link href="/" className="flex items-center gap-2.5 text-ink no-underline hover:text-ink">
            <Logo size={38} />
            <span className="font-display text-[24px] font-extrabold tracking-tight">Kibaba</span>
          </Link>
          <nav aria-label="This page" className="ml-auto flex items-center gap-2 sm:gap-5">
            <a href="#how" className="hidden text-[16px] font-bold text-ink no-underline hover:text-cobalt sm:inline">How it works</a>
            <a href="#private" className="hidden text-[16px] font-bold text-ink no-underline hover:text-cobalt md:inline">Privacy</a>
            <Link href="/signin" className="inline-flex min-h-11 items-center rounded-button bg-cobalt px-5 text-[16px] font-bold text-white no-underline hover:bg-cobalt-dark hover:text-white">
              Sign in
            </Link>
          </nav>
        </div>
      </header>

      <main id="main" tabIndex={-1} className="flex-1 focus:outline-none">
        <section className="relative overflow-hidden bg-cream">
          <BeadArc className="pointer-events-none absolute -left-36 -top-36 h-[300px] w-[300px] opacity-60" />
          <div className="relative mx-auto grid max-w-[1200px] items-center gap-12 px-4 pb-44 pt-14 sm:px-8 lg:grid-cols-[1.15fr_1fr] lg:pb-48 lg:pt-20">
            <div className="flex flex-col gap-6">
              <p className="inline-flex w-fit items-center gap-2 rounded-full bg-white px-4 py-1.5 text-[15px] font-bold text-cobalt">
                <Bead colour="sun" size={10} /> Early warning for chamas
              </p>
              <h1 className="text-[44px] leading-[1.02] sm:text-[60px]">Know who to check in with, before a repayment is missed.</h1>
              <p className="max-w-[34em] text-[19px] text-subtle">
                Kibaba reads your chama&apos;s ledger book from a photo and shows officials which members might need a
                friendly word, and why. Members see their own loans and contributions.
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <Link href="/signin" className="inline-flex min-h-14 items-center gap-2 rounded-button bg-cobalt px-7 text-[18px] font-bold text-white no-underline hover:bg-cobalt-dark hover:text-white">
                  Sign in <ArrowRight aria-hidden="true" size={20} />
                </Link>
                <a href="#how" className="inline-flex min-h-14 items-center rounded-button border-2 border-ink bg-white px-6 text-[18px] font-bold text-ink no-underline hover:bg-ice hover:text-ink">
                  See how it works
                </a>
              </div>
              <p className="text-[15px] text-muted">Officials decide. Kibaba only suggests who to talk to.</p>
            </div>
            <div className="relative flex justify-center">
              <BeadArc className="pointer-events-none absolute left-1/2 top-1/2 h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 opacity-70" />
              <Phone />
            </div>
          </div>
          <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-center gap-4 sm:gap-10">
            <Meeting className="hidden h-[170px] md:block" />
            <Cooking className="h-[150px] sm:h-[170px]" />
            <Singing className="h-[150px] sm:h-[170px]" />
            <Market className="hidden h-[170px] md:block" />
          </div>
        </section>
        <div aria-hidden="true" className="bead-edge !mb-0" />

        <section id="how" aria-labelledby="how-title" className="mx-auto flex max-w-[1200px] scroll-mt-20 flex-col gap-8 px-4 py-20 sm:px-8">
          <div className="flex flex-col gap-3">
            <h2 id="how-title" className="text-[36px] sm:text-[44px]">How it works</h2>
            <p className="max-w-[40em] text-[18px] text-subtle">Three steps after every meeting, all on a phone.</p>
          </div>
          <ol className="grid gap-5 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <li key={s.title} className="reveal lift flex flex-col gap-4 rounded-card border border-line bg-white p-6">
                <div className="flex items-center justify-between">
                  <StepRing n={i + 1} />
                  <s.icon aria-hidden="true" size={30} className="text-cobalt" />
                </div>
                <h3 className="text-[26px]">{s.title}</h3>
                <p className="text-[17px] text-subtle">{s.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="colours-title" className="bg-ice">
          <div className="mx-auto flex max-w-[1200px] flex-col gap-8 px-4 py-20 sm:px-8">
            <div className="flex flex-col gap-3">
              <h2 id="colours-title" className="text-[36px] sm:text-[44px]">Three colours, one meaning each</h2>
              <p className="max-w-[40em] text-[18px] text-subtle">
                Every member with a loan gets a colour from their own record: repayments, contributions and loans.
              </p>
            </div>
            <ul className="grid gap-5 md:grid-cols-3">
              {BANDS.map((b) => (
                <li key={b} className={`reveal relative flex flex-col gap-3 overflow-hidden rounded-card p-6 ${TILE[b]}`}>
                  <span aria-hidden="true" className="flex gap-1.5">
                    {Array.from({ length: BAND[b].beads }, (_, i) => <Bead key={i} colour={BAND[b].colour} size={22} />)}
                  </span>
                  <span className="font-display text-[28px] font-extrabold leading-tight">{BAND[b].label}</span>
                  <span className="text-[17px] text-ink">{BAND[b].meaning}</span>
                </li>
              ))}
            </ul>
            <p className="text-[16px] text-subtle">A colour is a reason to talk, never a verdict. Nothing in Kibaba approves or refuses a loan.</p>
          </div>
        </section>

        <section aria-labelledby="who-title" className="mx-auto flex max-w-[1200px] flex-col gap-8 px-4 py-20 sm:px-8">
          <h2 id="who-title" className="text-[36px] sm:text-[44px]">Made for the whole chama</h2>
          <div className="grid gap-5 lg:grid-cols-2">
            <div className="reveal relative flex min-h-[300px] flex-col gap-4 overflow-hidden rounded-card bg-ink p-8 text-white">
              <BeadArc light className="pointer-events-none absolute -right-20 -top-20 h-[180px] w-[180px]" />
              <h3 className="text-[30px] text-cream">For officials</h3>
              <ul className="relative flex flex-col gap-2.5 pr-20 text-[17px] text-side-text">
                <li className="flex gap-2.5"><Bead colour="sun" size={12} className="mt-1.5" />Who to follow up after each meeting, and why</li>
                <li className="flex gap-2.5"><Bead colour="sun" size={12} className="mt-1.5" />Every meeting&apos;s page, kept beside its photo</li>
                <li className="flex gap-2.5"><Bead colour="sun" size={12} className="mt-1.5" />A new page added in a few minutes from a photo</li>
              </ul>
              <Meeting tone="light" className="pointer-events-none absolute -bottom-3 right-4 h-[150px] opacity-70" />
            </div>
            <div className="reveal relative flex min-h-[300px] flex-col gap-4 overflow-hidden rounded-card bg-cream p-8">
              <BeadArc className="pointer-events-none absolute -right-20 -top-20 h-[180px] w-[180px]" />
              <h3 className="text-[30px]">For members</h3>
              <ul className="relative flex flex-col gap-2.5 pr-20 text-[17px] text-subtle">
                <li className="flex gap-2.5"><Bead colour="cobalt" size={12} className="mt-1.5" />Your loans, what is left to repay and when it is due</li>
                <li className="flex gap-2.5"><Bead colour="cobalt" size={12} className="mt-1.5" />Your contributions and repayments, meeting by meeting</li>
                <li className="flex gap-2.5"><Bead colour="cobalt" size={12} className="mt-1.5" />Only your own records, never anyone else&apos;s</li>
              </ul>
              <Market className="pointer-events-none absolute -bottom-3 right-4 h-[150px] opacity-80" />
            </div>
          </div>
        </section>

        <section id="private" aria-labelledby="private-title" className="scroll-mt-20 bg-cream">
          <div className="mx-auto flex max-w-[1200px] flex-col gap-8 px-4 py-20 sm:px-8">
            <h2 id="private-title" className="text-[36px] sm:text-[44px]">Private by design</h2>
            <ul className="grid gap-5 md:grid-cols-3">
              {[
                { icon: Lock, title: "Names stay private", text: "Names are swapped for codes before anything is worked out." },
                { icon: ShieldCheck, title: "Each to their own", text: "Members see only their own records. Ledger photos are shown only to officials." },
                { icon: HandHeart, title: "People decide", text: "Kibaba suggests who to talk to. The chama's officials decide what to do." },
              ].map((p) => (
                <li key={p.title} className="reveal flex flex-col gap-3 rounded-card bg-white p-6">
                  <span className="flex h-12 w-12 items-center justify-center rounded-full bg-ice">
                    <p.icon aria-hidden="true" size={24} className="text-cobalt" />
                  </span>
                  <h3 className="text-[22px]">{p.title}</h3>
                  <p className="text-[16px] text-subtle">{p.text}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>

      <footer className="relative overflow-hidden bg-ink text-white">
        <div aria-hidden="true" className="bead-edge !mb-0" />
        <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-4 py-12 sm:px-8 md:flex-row md:items-end md:justify-between">
          <div className="flex flex-col gap-3">
            <span className="flex items-center gap-3">
              <Logo size={40} onDark />
              <span className="font-display text-[26px] font-extrabold">Kibaba</span>
            </span>
            <p lang="sw" className="font-display text-[22px] font-extrabold text-cream">Haba na haba hujaza kibaba</p>
            <p className="text-[15px] text-side-muted">Little by little fills the measure.</p>
          </div>
          <div className="flex flex-col gap-3 md:items-end">
            <Link href="/signin" className="inline-flex min-h-12 w-fit items-center gap-2 rounded-button bg-sun px-6 text-[17px] font-bold text-ink no-underline hover:bg-cream hover:text-ink">
              Sign in <ArrowRight aria-hidden="true" size={18} />
            </Link>
            <p className="text-[14px] text-side-muted">Strathmore University, CS Project II 2026</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
