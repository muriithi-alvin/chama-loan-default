"use client";

import { Mail, MessageSquareText, Smartphone } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { api, ApiProblem } from "@/lib/client-api";
import type { CodeStep, Me, Site } from "@/lib/types";

type Props = {
  ended: boolean;
  next?: string;
  site: Site | null;
  serverDown: boolean;
  step?: "code";
  error?: string;
};

// Messages for the codes the Google round trip comes back with (/signin?error=...)
const RETURN_ERRORS: Record<string, string> = {
  google_off: "Signing in with Google is not switched on yet. Use your email or phone.",
  google_failed: "Signing in with Google did not finish. Try again.",
  no_access: "This Google account has no access to a chama yet. Ask your chama's admin to add your email.",
  mismatch: "This sign-in does not match the account on record. Ask your chama's admin to check it.",
  no_phone: "Officials confirm each sign-in with a code texted to their phone, and your account has no phone number yet. Ask your chama's admin to add it.",
  too_many_codes: "A code was sent a moment ago. Wait a minute, then try again.",
  too_many_attempts: "Too many sign-in attempts. Wait a minute, then try again.",
  phone_not_set_up: "Codes by text message are not set up yet. The admin needs to turn on phone sign-in in Supabase.",
  sign_in_unavailable: "The sign-in service is not answering. Try again in a minute.",
  sign_in_not_set_up: "Sign-in is not set up on this server yet. The admin needs to add the Supabase settings.",
};

function GoogleMark() {
  return (
    <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}

function Dots({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-3">
      <span aria-hidden="true" className="flex gap-1.5">
        {[0, 1, 2].map((i) => (
          <motion.span key={i} className="bead bead-sun" style={{ width: 9, height: 9 }}
            animate={{ y: [0, -5, 0] }} transition={{ duration: 0.7, repeat: Infinity, delay: i * 0.12 }} />
        ))}
      </span>
      {label}
    </span>
  );
}

export function SignInForm({ ended, next, site, serverDown, step, error }: Props) {
  const router = useRouter();
  const id = useId();
  const methods = site?.methods ?? { password: true, google: false, phone: false };
  const ready = site?.sign_in_ready ?? true;
  const [how, setHow] = useState<"email" | "phone">(methods.password || !methods.phone ? "email" : "phone");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [waiting, setWaiting] = useState<CodeStep | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [problem, setProblem] = useState<ApiProblem | null>(
    error ? new ApiProblem(0, error, RETURN_ERRORS[error] ?? "Sign-in did not finish. Try again.") : null,
  );
  const codeInput = useRef<HTMLInputElement>(null);

  // Back from Google with a code still to type: ask the server where it went
  useEffect(() => {
    if (step !== "code") return;
    api<{ waiting: boolean; phone_hint?: string }>("/api/session/step")
      .then((s) => s.waiting ? setWaiting({ next: "code", phone_hint: s.phone_hint ?? "your phone" })
        : setProblem(new ApiProblem(401, "step_ended", "This sign-in has ended. Start again.")))
      .catch(() => setProblem(new ApiProblem(0, "unknown", "Kibaba's server is not answering. Reload the page.")));
  }, [step]);

  useEffect(() => { if (waiting) codeInput.current?.focus(); }, [waiting]);

  function signedIn(me: Me) {
    router.replace(next ?? (me.user.role === "member" ? "/m" : "/o"));
    router.refresh();
  }

  async function run(work: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setProblem(null);
    setNotice(null);
    try {
      await work();
    } catch (err) {
      const p = err instanceof ApiProblem ? err : new ApiProblem(0, "unknown", "Sign-in did not work. Try again.");
      if (p.code === "step_ended") { setWaiting(null); setCode(""); }
      setProblem(p);
      setBusy(false);
    }
  }

  const withPassword = (e: React.FormEvent) => {
    e.preventDefault();
    return run(async () => {
      const reply = await api<Me | CodeStep>("/api/session", { json: { email, password } });
      if ("next" in reply) { setWaiting(reply); setBusy(false); } else signedIn(reply);
    });
  };
  const withPhone = (e: React.FormEvent) => {
    e.preventDefault();
    return run(async () => {
      setWaiting(await api<CodeStep>("/api/session/phone", { json: { phone } }));
      setBusy(false);
    });
  };
  const withCode = (e: React.FormEvent) => {
    e.preventDefault();
    return run(async () => signedIn(await api<Me>("/api/session/code", { json: { code } })));
  };
  const resend = () => run(async () => {
    const sent = await api<{ phone_hint: string }>("/api/session/code/resend", { method: "POST" });
    setNotice(`A new code was sent to ${sent.phone_hint}.`);
    setBusy(false);
  });

  const fieldError = (field: string) => (problem?.field === field ? problem : null);
  const general = problem && !problem.field ? problem : null;
  const inputClass =
    "h-[52px] w-full min-w-0 rounded-button border-[1.5px] bg-white px-4 text-[17px] text-ink placeholder:text-muted/80";
  const primary =
    "relative h-14 overflow-hidden rounded-button bg-cobalt text-[18px] font-bold text-white transition-colors hover:bg-cobalt-dark disabled:opacity-80";
  const googleHref = `/api/session/google${next ? `?next=${encodeURIComponent(next)}` : ""}`;

  const messages = (
    <div aria-live="polite" className="empty:hidden flex flex-col gap-3">
      {ended && !problem && !waiting && (
        <p className="rounded-button bg-ice px-4 py-3 text-[16px]">Your session ended. Sign in again to carry on.</p>
      )}
      {serverDown && (
        <p className="rounded-button bg-high-bg px-4 py-3 text-[16px] text-high">
          Kibaba&apos;s server is not answering. Check that it is running, then reload this page.
        </p>
      )}
      {!ready && (
        <p className="rounded-button bg-cream px-4 py-3 text-[16px]">
          Sign-in is not set up on this server yet. The admin needs to add the Supabase settings.
        </p>
      )}
      {notice && <p className="rounded-button bg-low-bg px-4 py-3 text-[16px] text-low">{notice}</p>}
      <AnimatePresence>
        {general && (
          <motion.p initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="rounded-button bg-high-bg px-4 py-3 text-[16px] text-high">
            {general.message} {general.ref && <span className="text-[14px]">(reference {general.ref})</span>}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );

  if (waiting) {
    return (
      <form onSubmit={withCode} noValidate className="flex flex-col gap-5">
        {messages}
        <div className="flex items-start gap-3 rounded-card bg-ice px-5 py-4">
          <MessageSquareText aria-hidden="true" size={24} className="mt-0.5 shrink-0 text-cobalt" />
          <p className="text-[17px]">
            We texted a 6-digit code to <strong>{waiting.phone_hint}</strong>. Type it here to finish signing in.
            {site?.officials_confirm_by_phone && " Officials confirm every sign-in this way."}
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor={`${id}-code`} className="text-[16px] font-bold">Code from the text message</label>
          <input ref={codeInput} id={`${id}-code`} inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]*"
            maxLength={6} placeholder="123456" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            aria-invalid={!!fieldError("code")} aria-describedby={fieldError("code") ? `${id}-code-error` : undefined}
            className={`${inputClass} max-w-[220px] text-center text-[24px] tracking-[0.4em] tabular ${fieldError("code") ? "border-high" : "border-field"}`} />
          {fieldError("code") && <p id={`${id}-code-error`} className="text-[15px] font-bold text-high">{fieldError("code")!.message}</p>}
        </div>
        <motion.button type="submit" disabled={busy || code.length !== 6} whileTap={{ scale: 0.98 }} className={primary}>
          {busy ? <Dots label="Checking the code" /> : "Finish signing in"}
        </motion.button>
        <div className="flex flex-wrap gap-x-5 gap-y-2 text-[15px]">
          <button type="button" onClick={resend} disabled={busy} className="font-bold text-cobalt hover:underline">Send a new code</button>
          <button type="button" onClick={() => { setWaiting(null); setCode(""); setProblem(null); }} disabled={busy}
            className="font-bold text-subtle hover:underline">Start again</button>
        </div>
      </form>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {messages}
      {methods.google && (
        <>
          <a href={googleHref}
            className="flex h-14 items-center justify-center gap-3 rounded-button border-[1.5px] border-field bg-white text-[17px] font-bold text-ink no-underline hover:bg-ice hover:text-ink">
            <GoogleMark /> Continue with Google
          </a>
          {(methods.password || methods.phone) && (
            <div className="flex items-center gap-3 text-[14px] text-muted" aria-hidden="true">
              <span className="h-px flex-1 bg-line" /> or <span className="h-px flex-1 bg-line" />
            </div>
          )}
        </>
      )}

      {methods.phone && methods.password && (
        <div role="tablist" aria-label="Sign in with" className="grid grid-cols-2 gap-1 rounded-button bg-ice p-1">
          {([["email", "Email", Mail], ["phone", "Phone", Smartphone]] as const).map(([key, label, Icon]) => (
            <button key={key} type="button" role="tab" aria-selected={how === key}
              onClick={() => { setHow(key); setProblem(null); }}
              className={`flex h-11 items-center justify-center gap-2 rounded-[10px] text-[16px] font-bold ${how === key ? "bg-white text-ink shadow-[0_1px_4px_rgba(20,33,61,.12)]" : "text-subtle"}`}>
              <Icon aria-hidden="true" size={18} /> {label}
            </button>
          ))}
        </div>
      )}

      {!methods.password && !methods.phone ? null : how === "phone" && methods.phone ? (
        <form onSubmit={withPhone} noValidate className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <label htmlFor={`${id}-phone`} className="text-[16px] font-bold">Phone number</label>
            <input id={`${id}-phone`} type="tel" autoComplete="tel" inputMode="tel" placeholder="07XX XXX XXX"
              value={phone} onChange={(e) => setPhone(e.target.value)}
              aria-invalid={!!fieldError("phone")} aria-describedby={`${id}-phone-help${fieldError("phone") ? ` ${id}-phone-error` : ""}`}
              className={`${inputClass} ${fieldError("phone") ? "border-high" : "border-field"}`} />
            <p id={`${id}-phone-help`} className="text-[15px] text-muted">The number on your chama account. We text you a code.</p>
            {fieldError("phone") && <p id={`${id}-phone-error`} className="text-[15px] font-bold text-high">{fieldError("phone")!.message}</p>}
          </div>
          <motion.button type="submit" disabled={busy} whileTap={{ scale: 0.98 }} className={primary}>
            {busy ? <Dots label="Sending the code" /> : "Text me a code"}
          </motion.button>
          {site?.officials_confirm_by_phone && (
            <p className="text-[15px] text-muted">Officials: sign in with Google or your email first. A code then comes to this phone.</p>
          )}
        </form>
      ) : (
        <form onSubmit={withPassword} noValidate className="flex flex-col gap-5">
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

          <motion.button type="submit" disabled={busy} whileTap={{ scale: 0.98 }} className={primary}>
            {busy ? <Dots label="Signing in" /> : "Sign in"}
          </motion.button>
          <p className="text-[15px] text-muted">Forgotten your password? Ask your chama&apos;s admin to reset it.</p>
        </form>
      )}
    </div>
  );
}
