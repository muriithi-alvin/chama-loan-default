"use client";

import { Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

const BANDS = [
  { value: "", label: "All" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
  { value: "none", label: "No loan running" },
];

// Filters live in the address, so a filtered list can be bookmarked (OFF-2).
export function MemberFilters({ band, q, total, shown }: { band?: string; q: string; total: number; shown: number }) {
  const router = useRouter();
  const path = usePathname();
  const params = useSearchParams();
  const [text, setText] = useState(q);
  const [pending, startTransition] = useTransition();

  const go = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    startTransition(() => router.replace(`${path}?${next.toString()}`, { scroll: false }));
  };

  useEffect(() => {
    if (text === q) return;
    const t = window.setTimeout(() => go({ q: text }), 250);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
      <label className="relative flex-1 sm:max-w-[340px]">
        <span className="sr-only">Search by name</span>
        <Search aria-hidden="true" size={18} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted" />
        <input type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder="Search by name"
          className="h-12 w-full rounded-button border-[1.5px] border-field bg-white pl-10 pr-4 text-[16px]" />
      </label>
      <fieldset className="flex flex-wrap gap-2">
        <legend className="sr-only">Band</legend>
        {BANDS.map((b) => {
          const active = (band ?? "") === b.value;
          return (
            <button key={b.value} type="button" aria-pressed={active} onClick={() => go({ band: b.value })}
              className={`min-h-11 rounded-full border-[1.5px] px-4 text-[15px] font-bold transition-colors ${
                active ? "border-ink bg-ink text-white" : "border-field bg-white text-ink hover:bg-ice"
              }`}>
              {b.label}
            </button>
          );
        })}
      </fieldset>
      <p aria-live="polite" className={`text-[15px] text-muted sm:ml-auto ${pending ? "opacity-60" : ""}`}>
        Showing {shown} of {total} members
      </p>
    </div>
  );
}
