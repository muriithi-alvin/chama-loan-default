"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { api, ApiProblem } from "@/lib/client-api";
import type { Language } from "@/lib/types";

const CHOICES: { value: Language; label: string }[] = [
  { value: "en", label: "English" },
  { value: "sw", label: "Kiswahili" },
];

/** English or Kiswahili for the reasons (D-044). Saved on the account, so the
 *  meeting text the day before comes in the same language. */
export function LanguageSwitch({ language }: { language: Language }) {
  const router = useRouter();
  const [chosen, setChosen] = useState(language);
  const [problem, setProblem] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  async function choose(value: Language) {
    if (value === chosen) return;
    setProblem(null);
    setChosen(value);
    try {
      await api("/api/me/language", { method: "PUT", json: { language: value } });
      startTransition(() => router.refresh());
    } catch (e) {
      setChosen(language);
      setProblem(e instanceof ApiProblem ? e.message : "Could not change the language. Try again.");
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <div role="group" aria-label="Language of the reasons" aria-busy={pending}
        className="inline-flex rounded-full border-[1.5px] border-line bg-white p-0.5">
        {CHOICES.map((c) => (
          <button key={c.value} type="button" lang={c.value} aria-pressed={chosen === c.value}
            onClick={() => choose(c.value)}
            className={`min-h-9 rounded-full px-3.5 text-[14px] font-bold ${
              chosen === c.value ? "bg-ink text-white" : "text-subtle hover:bg-ice"
            }`}>
            {c.label}
          </button>
        ))}
      </div>
      {problem && <p role="alert" className="text-[14px] text-high">{problem}</p>}
    </div>
  );
}
