
"use client";

import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiProblem } from "@/lib/client-api";
import type { Me, Site } from "@/lib/types";

type Props = {
  ended: boolean;
  next?: string;
  site: Site | null;
  serverDown: boolean;
  error?: string;
};

const RETURN_ERRORS: Record<string, string> = {
  google_off: "Google sign-in is not enabled yet. Ask your administrator to check the Supabase configuration.",
  google_failed: "Signing in with Google did not finish. Try again.",
  no_access: "This Google account has no access to a chama yet. Ask your chama's admin to add your email.",
  mismatch: "This Google account does not match the identity linked to your Kibaba account. Ask your chama's admin to check it.",
  too_many_attempts: "Too many sign-in attempts. Wait a minute, then try again.",
  sign_in_unavailable: "The sign-in service is not answering. Try again in a minute.",
  sign_in_not_set_up: "Sign-in is not set up on this server yet. The admin needs to add the Supabase settings.",
};

function GoogleMark() {
  return (
    <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#FFC107"
        d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"
      />
      <path
        fill="#FF3D00"
        d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"
      />
    </svg>
  );
}

function Dots({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-3">
      <span aria-hidden="true" className="flex gap-1.5">
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="bead bead-sun"
            style={{ width: 9, height: 9 }}
            animate={{ y: [0, -5, 0] }}
            transition={{
              duration: 0.7,
              repeat: Infinity,
              delay: i * 0.12,
            }}
          />
        ))}
      </span>
      {label}
    </span>
  );
}

export function SignInForm({
  ended,
  next,
  site,
  serverDown,
  error,
}: Props) {
  const router = useRouter();

  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<ApiProblem | null>(
    error
      ? new ApiProblem(
          0,
          error,
          RETURN_ERRORS[error] ?? "Sign-in did not finish. Try again.",
        )
      : null,
  );

  const ready = site?.sign_in_ready ?? true;
  const googleEnabled = site?.methods?.google ?? false;

  const googleHref = `/api/session/google${
    next ? `?next=${encodeURIComponent(next)}` : ""
  }`;

  const general = problem && !problem.field ? problem : null;

  const primary =
    "relative flex h-14 w-full items-center justify-center gap-3 overflow-hidden rounded-button bg-cobalt text-[18px] font-bold text-white transition-colors hover:bg-cobalt-dark disabled:opacity-80";

  function startGoogleSignIn() {
    if (busy || !googleEnabled || !ready || serverDown) {
      return;
    }

    setBusy(true);
    setProblem(null);

    // Let the browser follow the server's Google OAuth redirect.
    window.location.assign(googleHref);
  }

  const messages = (
    <div aria-live="polite" className="flex flex-col gap-3">
      {ended && !problem && (
        <p className="rounded-button bg-ice px-4 py-3 text-[16px]">
          Your session ended. Sign in again to carry on.
        </p>
      )}

      {serverDown && (
        <p className="rounded-button bg-high-bg px-4 py-3 text-[16px] text-high">
          Kibaba&apos;s server is not answering. Check that it is running,
          then reload this page.
        </p>
      )}

      {!ready && (
        <p className="rounded-button bg-cream px-4 py-3 text-[16px]">
          Sign-in is not set up on this server yet. The admin needs to add
          the Supabase settings.
        </p>
      )}

      {ready && site && !googleEnabled && (
        <p className="rounded-button bg-cream px-4 py-3 text-[16px]">
          Google sign-in is currently unavailable. Please contact your
          chama&apos;s administrator.
        </p>
      )}

      <AnimatePresence>
        {general && (
          <motion.p
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="rounded-button bg-high-bg px-4 py-3 text-[16px] text-high"
          >
            {general.message}{" "}
            {general.ref && (
              <span className="text-[14px]">
                (reference {general.ref})
              </span>
            )}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );

  return (
    <div className="flex flex-col gap-5">
      {messages}

      <button
        type="button"
        onClick={startGoogleSignIn}
        disabled={busy || !ready || !googleEnabled || serverDown}
        className={primary}
      >
        {busy ? (
          <Dots label="Connecting to Google" />
        ) : (
          <>
            <GoogleMark />
            Continue with Google
          </>
        )}
      </button>

      <p className="text-center text-[15px] text-muted">
        Use the Google account registered with your chama.
      </p>
    </div>
  );
}
