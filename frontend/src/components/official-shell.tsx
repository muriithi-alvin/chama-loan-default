"use client";

import {
  BookOpen, Camera, ClipboardList, History, Info, LayoutGrid, MoreHorizontal, PenLine, Users, X, type LucideIcon,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import type { Me } from "@/lib/types";

import { Bead, Logo } from "./beads";
import { Meeting } from "./figurines";
import { SignOutButton } from "./sign-out";

type Page = { href: string; label: string; icon: LucideIcon; exact?: boolean };

// The four pages officials use every month, then the quieter ones.
const MAIN: Page[] = [
  { href: "/o", label: "Overview", icon: LayoutGrid, exact: true },
  { href: "/o/members", label: "Members", icon: Users },
  { href: "/o/scan", label: "Scan a page", icon: Camera },
  { href: "/o/records/meetings", label: "Records", icon: BookOpen },
];
const MORE: Page[] = [
  { href: "/o/about", label: "How Kibaba decides", icon: Info },
  { href: "/o/uploads", label: "Upload history", icon: History },
  { href: "/o/edits", label: "Edit record", icon: PenLine },
];
const PAGES = [...MAIN, ...MORE];

function isActive(path: string, href: string, exact?: boolean) {
  if (exact) return path === href;
  if (href === "/o/scan") return path.startsWith("/o/scan") || path.startsWith("/o/runs");
  return path === href || path.startsWith(`${href}/`);
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");
}

function Avatar({ name, size = 40 }: { name: string; size?: number }) {
  return (
    <span aria-hidden="true" style={{ width: size, height: size }}
      className="flex shrink-0 items-center justify-center rounded-full bg-sun text-[14px] font-bold text-ink">
      {initials(name)}
    </span>
  );
}

function SideList({ pages, path, big = false }: { pages: Page[]; path: string; big?: boolean }) {
  return (
    <ul className={`flex flex-col gap-1 ${big ? "text-[17px]" : "text-[15px]"}`}>
      {pages.map((p) => {
        const active = isActive(path, p.href, p.exact);
        return (
          <li key={p.href} className="relative">
            {active && (
              <motion.span layoutId="side-active" aria-hidden="true"
                className="absolute inset-0 rounded-button bg-white/[0.12]"
                transition={{ type: "spring", stiffness: 500, damping: 40 }} />
            )}
            <Link href={p.href} aria-current={active ? "page" : undefined}
              className={`relative flex items-center gap-3 rounded-button px-3 no-underline ${big ? "min-h-12" : "min-h-10"} ${
                active ? "font-bold text-white hover:text-white" : "text-side-text hover:bg-white/[0.06] hover:text-white"
              }`}>
              {active ? <Bead colour="sun" size={12} /> : <Bead colour="empty" size={12} />}
              {p.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function Sidebar({ me, path }: { me: Me; path: string }) {
  return (
    <nav aria-label="Officials" className="on-dark sticky top-0 hidden h-dvh w-[264px] shrink-0 flex-col gap-6 overflow-y-auto bg-ink px-[18px] pb-6 pt-9 text-white lg:flex">
      <div aria-hidden="true" className="bead-edge absolute inset-x-0 top-0 !mb-0 opacity-90" />
      <Link href="/o" className="flex items-center gap-3 px-2 text-white no-underline hover:text-white">
        <Logo size={40} onDark />
        <span className="flex flex-col">
          <span className="font-display text-[24px] font-extrabold leading-none tracking-tight">Kibaba</span>
          <span className="text-[13px] text-side-muted">Early warning</span>
        </span>
      </Link>
      <div className="flex flex-col gap-0.5 rounded-[14px] bg-white/[0.07] px-3 py-3.5">
        <span className="text-[13px] text-side-muted">Your chama</span>
        <span className="text-[16px] font-bold text-cream">{me.user.chama_name}</span>
      </div>
      <SideList pages={MAIN} path={path} big />
      <div className="flex flex-col gap-2">
        <span className="px-3 text-[13px] font-bold uppercase tracking-wide text-side-muted">More</span>
        <SideList pages={MORE} path={path} />
      </div>
      <Meeting tone="light" className="mt-auto w-[200px] self-center opacity-40" />
      <div className="flex items-center gap-3 border-t border-white/[0.14] px-2.5 pt-3.5">
        <Avatar name={me.user.name} />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-[15px] font-bold leading-tight">{me.user.name}</span>
          <span className="text-[13px] capitalize text-side-muted">{me.user.position ?? me.user.role}</span>
        </span>
        <SignOutButton onDark />
      </div>
    </nav>
  );
}

const BOTTOM = [
  { href: "/o", label: "Overview", icon: LayoutGrid, exact: true },
  { href: "/o/members", label: "Members", icon: Users },
  { href: "/o/scan", label: "Scan", icon: Camera },
  { href: "/o/records/meetings", label: "Records", icon: ClipboardList },
];

function PhoneBars({ me, path }: { me: Me; path: string }) {
  const [more, setMore] = useState(false);
  useEffect(() => setMore(false), [path]);
  useEffect(() => {
    if (!more) return;
    const close = (e: KeyboardEvent) => e.key === "Escape" && setMore(false);
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [more]);

  return (
    <>
      <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-white/95 px-4 py-2.5 backdrop-blur lg:hidden">
        <Link href="/o" aria-label="Overview" className="flex items-center gap-2.5 no-underline">
          <Logo size={34} />
        </Link>
        <span className="flex min-w-0 flex-1 flex-col leading-tight">
          <span className="truncate text-[15px] font-bold text-ink">{me.user.chama_name}</span>
          <span className="truncate text-[13px] text-muted">{me.user.name}, <span className="capitalize">{me.user.position ?? me.user.role}</span></span>
        </span>
        <SignOutButton />
      </header>

      <nav aria-label="Officials" className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-ice/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
        <ul className="mx-auto grid max-w-[560px] grid-cols-5 items-end px-2">
          {BOTTOM.slice(0, 2).map((p) => <BottomItem key={p.href} {...p} active={isActive(path, p.href, p.exact)} />)}
          <li className="flex justify-center">
            <Link href="/o/scan" aria-current={isActive(path, "/o/scan") ? "page" : undefined}
              className="-mt-6 flex flex-col items-center gap-1 pb-1.5 text-[12px] font-bold text-ink no-underline">
              <span className="bead bead-cobalt flex items-center justify-center shadow-[0_8px_18px_rgba(37,71,168,.35)]"
                style={{ width: 60, height: 60 }}>
                <Camera aria-hidden="true" size={26} color="#fff" strokeWidth={2.2} />
              </span>
              Scan
            </Link>
          </li>
          <BottomItem {...BOTTOM[3]} active={isActive(path, BOTTOM[3].href)} />
          <li>
            <button type="button" onClick={() => setMore(true)} aria-expanded={more} aria-haspopup="dialog"
              className="flex min-h-14 w-full flex-col items-center justify-center gap-1 text-[12px] font-bold text-subtle">
              <MoreHorizontal aria-hidden="true" size={22} />
              More
            </button>
          </li>
        </ul>
      </nav>

      <AnimatePresence>
        {more && (
          <motion.div className="fixed inset-0 z-40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <button type="button" aria-label="Close the menu" className="absolute inset-0 bg-ink/40" onClick={() => setMore(false)} />
            <motion.div role="dialog" aria-modal="true" aria-label="More pages"
              initial={{ y: "100%" }} animate={{ y: 0 }} exit={{ y: "100%" }}
              transition={{ type: "spring", stiffness: 420, damping: 40 }}
              className="absolute inset-x-0 bottom-0 rounded-t-[24px] bg-white px-5 pb-[calc(24px+env(safe-area-inset-bottom))] pt-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-display text-[22px] font-extrabold">More</span>
                <button type="button" onClick={() => setMore(false)} aria-label="Close"
                  className="flex h-11 w-11 items-center justify-center rounded-full hover:bg-ice">
                  <X aria-hidden="true" size={22} />
                </button>
              </div>
              <ul className="flex flex-col">
                {PAGES.filter((p) => !BOTTOM.some((b) => b.href === p.href) && p.href !== "/o/scan").map((p) => (
                  <li key={p.href}>
                    <Link href={p.href} className="flex min-h-14 items-center gap-3 border-t border-line text-[17px] font-bold text-ink no-underline">
                      <p.icon aria-hidden="true" size={20} />
                      {p.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

function BottomItem({ href, label, icon: Icon, active }: { href: string; label: string; icon: typeof Users; active: boolean }) {
  return (
    <li>
      <Link href={href} aria-current={active ? "page" : undefined}
        className={`flex min-h-14 flex-col items-center justify-center gap-1 text-[12px] font-bold no-underline ${active ? "text-cobalt" : "text-subtle"}`}>
        <Icon aria-hidden="true" size={22} strokeWidth={active ? 2.4 : 2} />
        {label}
      </Link>
    </li>
  );
}

export function OfficialShell({ me, footer, children }: { me: Me; footer: React.ReactNode; children: React.ReactNode }) {
  const path = usePathname();
  return (
    <div className="flex min-h-dvh flex-col">
      <div className="flex flex-1 items-start">
        <Sidebar me={me} path={path} />
        <div className="flex min-w-0 flex-1 flex-col">
          <PhoneBars me={me} path={path} />
          <div className="flex flex-1 flex-col pb-28 lg:pb-0">
            <div className="flex-1">{children}</div>
            {footer}
          </div>
        </div>
      </div>
    </div>
  );
}
