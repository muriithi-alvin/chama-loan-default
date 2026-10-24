"use client";

import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { api, ApiProblem } from "@/lib/client-api";
import type { Me } from "@/lib/types";

type Props = { ended: boolean; next?: string; ready: boolean; serverDown: boolean };

export function SignInForm({ ended, next, ready, serverDown }: Props) {
  const router = useRouter();
  const id = useId();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<ApiProblem | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setProblem(null);
    try {
      const me = await api<Me>("/api/session", { json: { email, password } });
      router.replace(next ?? (me.user.role === "member" ? "/m" : "/o"));
      router.refresh();
    } catch (err) {
      setProblem(err instanceof ApiProblem ? err : new ApiProblem(0, "unknown", "Sign-in did not work. Try again."));
      setBusy(false);
    }
  }

  const fieldError = (field: string) => (problem?.field === field ? problem : null);
  const general = problem && !problem.field ? problem : null;
  const inputClass =
    "h-[52px] w-full min-w-0 rounded-button border-[1.5px] bg-white px-4 text-[17px] text-ink placeholder:text-muted/80";

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
      <div aria-live="polite" className="empty:hidden">
        {ended && !problem && (
          <p className="rounded-button bg-ice px-4 py-3 text-[16px]">Your session ended. Sign in again to carry on.</p>
        )}
        {serverDown && (
          <p className="rounded-button bg-high-bg px-4 py-3 text-[16px] text-high">
            Kibaba's server is not answering. Check that it is running, then reload this page.
          </p>
        )}
        {!ready && (
          <p className="rounded-button bg-cream px-4 py-3 text-[16px]">
            Sign-in is not set up on this server yet. The admin needs to add the Supabase settings.
          </p>
        )}
        <AnimatePresence>
          {general && (
            <motion.p initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              className="rounded-button bg-high-bg px-4 py-3 text-[16px] text-high">
              {general.message} <span className="text-[14px]">(reference {general.ref})</span>
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor={`${id}-email`} className="text-[16px] font-bold">Email</label>
        <input id={`${id}-email`} type="email" autoComplete="email" inputMode="email" required
          placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)}
          aria-invalid={!!fieldError("email")} aria-describedby={fieldError("email") ? `${id}-email-error` : undefined}
          className={`${inputClass} ${fieldError("email") ? "border-high" : "border-field"}`} />
        {fieldError("email") && (
          <p id={`${id}-email-error`} className="text-[15px] font-bold text-high">{fieldError("email")!.message}</p>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor={`${id}-password`} className="text-[16px] font-bold">Password</label>
        <div className="flex gap-2">
          <input id={`${id}-password`} type={show ? "text" : "password"} autoComplete="current-password" required
            placeholder="Your password" value={password} onChange={(e) => setPassword(e.target.value)}
            aria-invalid={!!fieldError("password")}
            aria-describedby={fieldError("password") ? `${id}-password-error` : undefined}
            className={`${inputClass} flex-1 ${fieldError("password") ? "border-high" : "border-field"}`} />
          <button type="button" onClick={() => setShow((s) => !s)} aria-pressed={show}
            aria-label={show ? "Hide password" : "Show password"}
            className="h-[52px] rounded-button border-[1.5px] border-field bg-white px-4 text-[15px] font-bold text-ink hover:bg-ice">
            {show ? "Hide" : "Show"}
          </button>
        </div>
        {fieldError("password") && (
          <p id={`${id}-password-error`} className="text-[15px] font-bold text-high">{fieldError("password")!.message}</p>
        )}
      </div>

      <motion.button type="submit" disabled={busy} whileTap={{ scale: 0.98 }}
        className="relative h-14 overflow-hidden rounded-button bg-cobalt text-[18px] font-bold text-white transition-colors hover:bg-cobalt-dark disabled:opacity-80">
        {busy ? (
          <span className="inline-flex items-center gap-3">
            <span aria-hidden="true" className="flex gap-1.5">
              {[0, 1, 2].map((i) => (
                <motion.span key={i} className="bead bead-sun" style={{ width: 9, height: 9 }}
                  animate={{ y: [0, -5, 0] }} transition={{ duration: 0.7, repeat: Infinity, delay: i * 0.12 }} />
              ))}
            </span>
            Signing in
          </span>
        ) : (
          "Sign in"
        )}
      </motion.button>
      <p className="text-[15px] text-muted">Forgotten your password? Ask your chama&apos;s admin to reset it.</p>
    </form>
  );
}
