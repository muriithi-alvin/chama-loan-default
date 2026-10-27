"use client";

import { useState } from "react";

import { api } from "@/lib/client-api";

export function SignOutButton({ onDark = false, className = "" }: { onDark?: boolean; className?: string }) {
  const [busy, setBusy] = useState(false);
  async function signOut() {
    setBusy(true);
    try {
      await api("/api/session", { method: "DELETE" });
    } finally {
      window.location.assign("/signin");
    }
  }
  return (
    <button type="button" onClick={signOut} disabled={busy}
      className={`min-h-11 rounded-[10px] border-[1.5px] px-3 text-[14px] font-bold ${
        onDark ? "border-side-line text-white hover:bg-white/10" : "border-ink text-ink hover:bg-ice"
      } ${className}`}>
      {busy ? "Signing out" : "Sign out"}
    </button>
  );
}
