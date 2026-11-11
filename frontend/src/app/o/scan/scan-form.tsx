"use client";

import { Camera, CheckCircle2, ImagePlus, Keyboard, Lightbulb, Maximize, RotateCcw, Sun, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { Card } from "@/components/page-header";
import { api, ApiProblem } from "@/lib/client-api";
import { checkFile, shrink } from "@/lib/resize";
import type { Upload } from "@/lib/types";

const MAX_PARTS = 3;

const TIPS = [
  { icon: Maximize, text: "The whole page in view, all four corners" },
  { icon: RotateCcw, text: "Flat on a table, photographed from straight above" },
  { icon: Sun, text: "Good light, no shadow or glare across the numbers" },
];

type Part = { blob: Blob; preview: string; before: number; after: number };

function newKey() {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID().replaceAll("-", "") : `${Date.now()}${Math.random()}`.replace(".", "");
}

// One meeting's page in up to 3 photos (D-039): a page too big for one photo,
// or a meeting that runs over several pages. They are read together, in order.
export function ScanForm() {
  const router = useRouter();
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [parts, setParts] = useState<Part[]>([]);
  const [error, setError] = useState<ApiProblem | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [sending, setSending] = useState(false);
  const [key, setKey] = useState(newKey);
  const shown = useRef<Part[]>([]);
  shown.current = parts;

  useEffect(() => () => shown.current.forEach((p) => URL.revokeObjectURL(p.preview)), []);

  async function choose(e: React.ChangeEvent<HTMLInputElement>) {
    const chosen = Array.from(e.target.files ?? []);
    e.target.value = "";          // choosing the same file again still counts
    setError(null);
    if (!chosen.length) return;
    const room = MAX_PARTS - parts.length;
    if (chosen.length > room) {
      setError(new ApiProblem(422, "too_many", `One meeting takes up to ${MAX_PARTS} photos. Remove one to add another.`, undefined, "photo"));
      return;
    }
    for (const file of chosen) {
      const problem = checkFile(file);
      if (problem) {
        setError(new ApiProblem(422, "file", problem, undefined, "photo"));
        return;
      }
    }
    setPreparing(true);
    try {
      const added: Part[] = [];
      for (const file of chosen) {
        const small = await shrink(file);
        added.push({ blob: small, preview: URL.createObjectURL(small), before: file.size, after: small.size });
      }
      setParts((p) => [...p, ...added]);
      setKey(newKey());           // other photos are a new upload; the same form sent twice is not
    } catch {
      setError(new ApiProblem(422, "file", "This photo could not be opened. Choose a JPEG, PNG or WebP photo.", undefined, "photo"));
    } finally {
      setPreparing(false);
    }
  }

  function remove(i: number) {
    URL.revokeObjectURL(parts[i].preview);
    setParts((p) => p.filter((_, j) => j !== i));
    setKey(newKey());
    setError(null);
  }

  async function send() {
    if (!parts.length || sending) return;
    setSending(true);
    setError(null);
    const form = new FormData();
    parts.forEach((p, i) => form.append("photos", p.blob, `ledger-page-part-${i + 1}.jpg`));
    form.append("idempotency_key", key);
    try {
      const { upload } = await api<{ upload: Upload; created: boolean }>("/api/uploads", { body: form });
      router.push(`/o/scans/${upload.id}`);
    } catch (e) {
      setError(e instanceof ApiProblem ? e : new ApiProblem(0, "unknown", "The photos could not be sent. Try again."));
      setSending(false);
    }
  }

  const fieldError = error?.field === "photo" ? error : null;
  const mb = (n: number) => `${(n / 1024 / 1024).toFixed(1)} MB`;
  const full = parts.length >= MAX_PARTS;

  return (
    <div className="flex flex-col gap-6">
      <Card tone="ice" className="flex flex-col gap-4">
        <h2 className="flex items-center gap-2.5 text-[22px]"><Lightbulb aria-hidden="true" size={22} /> For a clear reading</h2>
        <ul className="grid gap-3 sm:grid-cols-3">
          {TIPS.map((t) => (
            <li key={t.text} className="flex items-start gap-3 text-[16px]">
              <t.icon aria-hidden="true" size={22} className="mt-0.5 shrink-0 text-cobalt" />
              {t.text}
            </li>
          ))}
        </ul>
        <p className="text-[15px] text-subtle">
          Page too big for one photo, or the meeting runs over to the next page? Add up to {MAX_PARTS} photos, top to
          bottom, and they are read together as one meeting.
        </p>
      </Card>

      <div className="flex flex-col gap-3">
        <label htmlFor={`${id}-photo`} className="text-[17px] font-bold">Photos of this meeting&apos;s page</label>
        <p id={`${id}-help`} className="text-[15px] text-muted">JPEG, PNG or WebP, up to 20 MB each. On a phone this opens the camera.</p>
        <input ref={input} id={`${id}-photo`} type="file" accept="image/jpeg,image/png,image/webp" capture="environment" multiple
          onChange={choose} aria-describedby={`${id}-help${fieldError ? ` ${id}-error` : ""}`} aria-invalid={!!fieldError}
          className="sr-only" />
        {!full && (
          <button type="button" onClick={() => input.current?.click()} disabled={preparing || sending}
            className={`group flex flex-col items-center justify-center gap-3 rounded-card border-2 border-dashed bg-white px-6 text-center transition-colors hover:bg-ice ${
              parts.length ? "min-h-[110px] py-5" : "min-h-[160px] py-8"
            } ${fieldError ? "border-high" : "border-field"}`}>
            {preparing ? (
              <span className="flex items-center gap-3 text-[17px] font-bold">
                <span className="bead bead-cobalt bead-pulse" style={{ width: 16, height: 16 }} aria-hidden="true" /> Preparing the photo
              </span>
            ) : (
              <>
                <span className="bead bead-cobalt flex items-center justify-center transition-transform group-hover:scale-105"
                  style={{ width: parts.length ? 48 : 64, height: parts.length ? 48 : 64 }}>
                  {parts.length ? <ImagePlus aria-hidden="true" size={24} color="#fff" /> : <Camera aria-hidden="true" size={28} color="#fff" />}
                </span>
                <span className="text-[18px] font-bold">
                  {parts.length ? `Add part ${parts.length + 1} of this page (up to ${MAX_PARTS})` : "Take or choose a photo"}
                </span>
              </>
            )}
          </button>
        )}
        <div aria-live="polite">
          {fieldError && <p id={`${id}-error`} className="text-[16px] font-bold text-high">{fieldError.message}</p>}
        </div>
      </div>

      <AnimatePresence initial={false}>
        {parts.length > 0 && (
          <motion.ol key="parts" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            aria-label="Photos to send, in order"
            className={`grid gap-4 ${parts.length > 1 ? "sm:grid-cols-2 lg:grid-cols-3" : ""}`}>
            {parts.map((p, i) => (
              <motion.li key={p.preview} layout initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }}
                className="flex flex-col gap-3 rounded-card border border-line p-3 sm:p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[15px] font-bold">{parts.length > 1 ? `Part ${i + 1} of ${parts.length}` : "The page"}</span>
                  <button type="button" onClick={() => remove(i)} disabled={sending} aria-label={`Remove photo ${i + 1}`}
                    className="flex h-9 w-9 items-center justify-center rounded-full text-high hover:bg-high-bg">
                    <X aria-hidden="true" size={18} />
                  </button>
                </div>
                {/* eslint-disable-next-line @next/next/no-img-element -- a local preview, never uploaded twice */}
                <img src={p.preview} alt={`Preview of photo ${i + 1}`}
                  className={`w-full rounded-button bg-ink/[0.04] object-contain ${parts.length > 1 ? "max-h-[300px]" : "max-h-[520px]"}`} />
                <p className="flex items-center gap-2 text-[14px] text-muted">
                  <CheckCircle2 aria-hidden="true" size={16} className="shrink-0 text-leaf" />
                  {mb(p.after)} (from {mb(p.before)}), location data removed
                </p>
              </motion.li>
            ))}
          </motion.ol>
        )}
      </AnimatePresence>

      {error && !fieldError && (
        <p role="alert" className="rounded-button bg-high-bg px-4 py-3 text-[16px] text-high">
          {error.message} {error.ref && <span className="text-[14px]">(reference {error.ref})</span>}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <button type="button" onClick={send} disabled={!parts.length || sending || preparing}
          className="inline-flex min-h-14 items-center gap-3 rounded-button bg-cobalt px-7 text-[18px] font-bold text-white hover:bg-cobalt-dark disabled:opacity-50">
          {sending ? "Sending" : parts.length > 1 ? `Send ${parts.length} photos for reading` : "Send for reading"}
        </button>
        <Link href="/o/type" className="inline-flex items-center gap-2 text-[16px] font-bold">
          <Keyboard aria-hidden="true" size={18} /> No photo? Type the page in instead
        </Link>
      </div>
    </div>
  );
}
