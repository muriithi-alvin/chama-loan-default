"use client";

import { Smartphone, X } from "lucide-react";
import { useEffect, useState } from "react";

const KEY = "chama-install-hint-closed";

// "Add to Home screen" for officials on phones (X7). Hidden on large screens,
// when already installed, and once closed.
export function InstallHint() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    let closed = false;
    try {
      closed = window.localStorage.getItem(KEY) === "1";
    } catch {
      closed = false;
    }
    const installed = window.matchMedia("(display-mode: standalone)").matches;
    const phone = window.matchMedia("(max-width: 1023px)").matches;
    setShow(!closed && !installed && phone);
  }, []);
  if (!show) return null;
  const close = () => {
    setShow(false);
    try {
      window.localStorage.setItem(KEY, "1");
    } catch {
      /* private window: the hint simply comes back next time */
    }
  };
  return (
    <div className="flex items-start gap-3 rounded-card bg-cream px-5 py-4 lg:hidden">
      <Smartphone aria-hidden="true" size={22} className="mt-0.5 shrink-0" />
      <p className="flex-1 text-[16px]">
        <strong>Keep Kibaba on your phone.</strong> In the browser menu, choose <em>Add to Home screen</em> to open it
        like an app.
      </p>
      <button type="button" onClick={close} aria-label="Close this hint"
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full hover:bg-white/60">
        <X aria-hidden="true" size={20} />
      </button>
    </div>
  );
}
