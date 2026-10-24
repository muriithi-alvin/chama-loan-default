"use client";

import { RotateCw } from "lucide-react";

/** A service error with Retry (X3, X4): specific, safe, with the log reference. */
export function ServiceError({ message, reference, retry }: { message: string; reference?: string; retry: () => void }) {
  return (
    <div role="alert" className="mx-auto my-10 flex max-w-[640px] flex-col gap-4 rounded-card border border-line bg-white p-7">
      <h2 className="text-[26px]">This page could not load</h2>
      <p className="text-[17px] text-subtle">{message}</p>
      {reference && <p className="text-[15px] text-muted">Reference {reference}</p>}
      <div>
        <button type="button" onClick={retry}
          className="inline-flex min-h-12 items-center gap-2 rounded-button bg-cobalt px-5 text-[16px] font-bold text-white hover:bg-cobalt-dark">
          <RotateCw aria-hidden="true" size={18} />
          Try again
        </button>
      </div>
    </div>
  );
}
