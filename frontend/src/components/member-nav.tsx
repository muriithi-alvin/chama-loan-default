"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const PAGES = [
  { href: "/m", label: "My summary" },
  { href: "/m/loans", label: "My loans" },
];

/** The members' two pages (MEM-1, MEM-2), under the header. */
export function MemberNav() {
  const path = usePathname();
  return (
    <nav aria-label="My pages" className="mx-auto flex max-w-[960px] gap-2 px-4 pb-3 sm:px-8">
      {PAGES.map((p) => {
        const here = path === p.href;
        return (
          <Link key={p.href} href={p.href} aria-current={here ? "page" : undefined}
            className={`inline-flex min-h-[44px] items-center rounded-full px-5 text-[16px] font-bold no-underline ${
              here ? "bg-ink text-white hover:text-white" : "bg-ice text-ink hover:bg-cobalt-light hover:text-ink"
            }`}>
            {p.label}
          </Link>
        );
      })}
    </nav>
  );
}
