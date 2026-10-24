import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { BeadCollar } from "@/components/bead-collar";
import { Logo } from "@/components/beads";
import { Cooking, Singing } from "@/components/figurines";
import { apiGetOptional } from "@/lib/server-api";
import type { Me } from "@/lib/types";

import { SignInForm } from "./signin-form";

export const metadata: Metadata = { title: "Sign in" };

type Search = Promise<{ ended?: string; next?: string }>;

function safeNext(next: string | undefined): string | undefined {
  // only a page on this site, never another address
  return next && /^\/(o|m)(\/|$)/.test(next) ? next : undefined;
}

export default async function SignInPage({ searchParams }: { searchParams: Search }) {
  const { ended, next } = await searchParams;
  const [me, site] = await Promise.all([
    apiGetOptional<Me>("/api/me"),
    apiGetOptional<{ sign_in_ready: boolean }>("/api/site"),
  ]);
  if (me) redirect(me.user.role === "member" ? "/m" : "/o");

  return (
    <div className="flex min-h-dvh flex-col">
      <div className="flex flex-1 flex-wrap">
        <section aria-label="Bead collar"
          className="relative flex min-h-[560px] min-w-0 flex-[1_1_640px] flex-col items-center overflow-hidden bg-cream px-6 pt-9 lg:min-h-[860px]">
          <BeadCollar className="max-w-[min(580px,88vw)]" />
          <p className="mt-3.5 text-[15px] text-muted">Move through the beads. Tap to send a ripple.</p>
          <div aria-hidden="true" className="pointer-events-none absolute bottom-0 left-1/2 flex w-[940px] max-w-[120%] -translate-x-1/2 items-end justify-center gap-6 opacity-90">
            <Cooking className="hidden h-[220px] sm:block" />
            <Singing className="h-[200px] sm:h-[220px]" />
          </div>
        </section>

        <main id="main" tabIndex={-1} aria-label="Sign in" className="flex min-w-0 flex-[1_1_440px] items-center justify-center px-6 py-14 sm:px-8">
          <div className="flex w-full max-w-[420px] flex-col gap-8">
            <div className="flex items-center gap-3">
              <Logo />
              <div className="flex flex-col gap-px">
                <span className="font-display text-[26px] font-extrabold leading-none tracking-tight">Kibaba</span>
                <span className="text-[14px] text-muted">Early warning for chama officials</span>
              </div>
            </div>
            <div className="flex flex-col gap-3">
              <h1 className="text-[44px] sm:text-[48px]">Sign in</h1>
              <p className="text-[18px] text-muted">
                Officials see which members to follow up and why. Members see their own records.
              </p>
            </div>
            <SignInForm ended={ended === "1"} next={safeNext(next)} ready={site?.sign_in_ready ?? true}
              serverDown={site === null} />
            <div className="flex items-start gap-3 border-t border-line pt-5">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#187A42" strokeWidth="2.2"
                strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="mt-px shrink-0">
                <rect x="5" y="11" width="14" height="9" rx="2" />
                <path d="M8 11V8a4 4 0 0 1 8 0v3" />
              </svg>
              <p className="text-[15px] text-muted">
                Names stay private inside the system. Members see only their own records, and ledger photos are
                shown only to officials.
              </p>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
