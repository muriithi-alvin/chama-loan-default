import Link from "next/link";
import { forbidden } from "next/navigation";

import { AppFooter } from "@/components/app-footer";
import { Logo } from "@/components/beads";
import { SignOutButton } from "@/components/sign-out";
import { apiGet, apiGetOptional } from "@/lib/server-api";
import type { Me, RecordsStatus } from "@/lib/types";

// Members' pages (/m/): their own records only (R2).
export default async function MembersLayout({ children }: { children: React.ReactNode }) {
  const [me, status] = await Promise.all([
    apiGet<Me>("/api/me"),
    apiGetOptional<RecordsStatus>("/api/records-status"),
  ]);
  if (me.user.role !== "member") forbidden();
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-[960px] items-center gap-3 px-4 py-3 sm:px-8">
          <Link href="/m" className="flex items-center gap-2.5 text-ink no-underline hover:text-ink">
            <Logo size={36} />
            <span className="hidden font-display text-[22px] font-extrabold tracking-tight sm:inline">Kibaba</span>
          </Link>
          <span className="flex min-w-0 flex-1 flex-col leading-tight sm:items-end">
            <span className="truncate text-[15px] font-bold">{me.user.name}</span>
            <span className="truncate text-[13px] text-muted">Member, {me.user.chama_name}</span>
          </span>
          <SignOutButton />
        </div>
      </header>
      <div className="flex-1">{children}</div>
      <AppFooter role={me.user.role} status={status} />
    </div>
  );
}
