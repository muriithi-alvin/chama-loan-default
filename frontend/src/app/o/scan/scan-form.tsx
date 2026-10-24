"use client";

import { Camera, CheckCircle2, ImageUp, Lightbulb, Maximize, RotateCcw, Sun } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";

import { Card } from "@/components/page-header";
import { api, ApiProblem } from "@/lib/client-api";
import { checkFile, shrink } from "@/lib/resize";
import type { Upload } from "@/lib/types";

const TIPS = [
  { icon: Maximize, text: "The whole page in view, all four corners" },
  { icon: RotateCcw, text: "Flat on a table, photographed from straight above" },
  { icon: Sun, text: "Good light, no shadow or glare across the numbers" },
];

function newKey() {
  return typeof crypto.randomUUID === "function" ? crypto.randomUUID().replaceAll("-", "") : `${Date.now()}${Math.random()}`.replace(".", "");
}

export function ScanForm() {
  const router = useRouter();
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<Blob | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [error, setError] = useState<ApiProblem | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [sending, setSending] = useState(false);
  const [key, setKey] = useState(newKey);
  const [sizes, setSizes] = useState<{ before: number; after: number } | null>(null);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  async function choose(e: React.ChangeEvent<HTMLInputElement>) {
    const chosen = e.target.files?.[0];
    setError(null);
    if (!chosen) return;
    const problem = checkFile(chosen);
    if (problem) {
      setError(new ApiProblem(422, "file", problem, undefined, "photo"));
      setFile(null);
      setPreview(null);
      return;
    }
    setPreparing(true);
    try {
      const small = await shrink(chosen);
      setFile(small);
      setPreview(URL.createObjectURL(small));
      setSizes({ before: chosen.size, after: small.size });
      setKey(newKey());           // a new photo is a new upload; the same one sent twice is not
    } catch {
      setError(new ApiProblem(422, "file", "This photo could not be opened. Choose a JPEG, PNG or WebP photo.", undefined, "photo"));
    } finally {
      setPreparing(false);
    }
  }

  async function send() {
    if (!file || sending) return;
    setSending(true);
    setError(null);
    const form = new FormData();
    form.append("photo", file, "ledger-page.jpg");
    form.append("idempotency_key", key);
    try {
      const { upload } = await api<{ upload: Upload; created: boolean }>("/api/uploads", { body: form });
      router.push(`/o/scans/${upload.id}`);
    } catch (e) {
      setError(e instanceof ApiProblem ? e : new ApiProblem(0, "unknown", "The photo could not be sent. Try again."));
      setSending(false);
    }
  }

  const fieldError = error?.field === "photo" ? error : null;
  const mb = (n: number) => `${(n / 1024 / 1024).toFixed(1)} MB`;

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
      </Card>

      <div className="flex flex-col gap-3">
        <label htmlFor={`${id}-photo`} className="text-[17px] font-bold">Ledger page photo</label>
        <p id={`${id}-help`} className="text-[15px] text-muted">JPEG, PNG or WebP, up to 20 MB. On a phone this opens the camera.</p>
        <input ref={input} id={`${id}-photo`} type="file" accept="image/jpeg,image/png,image/webp" capture="environment"
          onChange={choose} aria-describedby={`${id}-help${fieldError ? ` ${id}-error` : ""}`} aria-invalid={!!fieldError}
          className="sr-only" />
        <button type="button" onClick={() => input.current?.click()} disabled={preparing || sending}
          className={`group flex min-h-[160px] flex-col items-center justify-center gap-3 rounded-card border-2 border-dashed bg-white px-6 py-8 text-center transition-colors hover:bg-ice ${
            fieldError ? "border-high" : "border-field"
          }`}>
          {preparing ? (
            <span className="flex items-center gap-3 text-[17px] font-bold">
              <span className="bead bead-cobalt bead-pulse" style={{ width: 16, height: 16 }} aria-hidden="true" /> Preparing the photo
            </span>
          ) : (
            <>
              <span className="bead bead-cobalt flex items-center justify-center transition-transform group-hover:scale-105" style={{ width: 64, height: 64 }}>
                {file ? <ImageUp aria-hidden="true" size={28} color="#fff" /> : <Camera aria-hidden="true" size={28} color="#fff" />}
              </span>
              <span className="text-[18px] font-bold">{file ? "Choose a different photo" : "Take or choose a photo"}</span>
            </>
          )}
        </button>
        <div aria-live="polite">
          {fieldError && <p id={`${id}-error`} className="text-[16px] font-bold text-high">{fieldError.message}</p>}
        </div>
      </div>

      <AnimatePresence>
        {preview && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="flex flex-col gap-4 rounded-card border border-line p-4 sm:p-5">
            {/* eslint-disable-next-line @next/next/no-img-element -- a local preview, never uploaded twice */}
            <img src={preview} alt="Preview of the photo to send" className="max-h-[520px] w-full rounded-button object-contain bg-ink/[0.04]" />
            {sizes && (
              <p className="flex items-center gap-2 text-[15px] text-muted">
                <CheckCircle2 aria-hidden="true" size={18} className="text-leaf" />
                Ready to send: {mb(sizes.after)} (from {mb(sizes.before)}), location data removed.
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {error && !fieldError && (
        <p role="alert" className="rounded-button bg-high-bg px-4 py-3 text-[16px] text-high">
          {error.message} {error.ref && <span className="text-[14px]">(reference {error.ref})</span>}
        </p>
      )}

      <div>
        <button type="button" onClick={send} disabled={!file || sending || preparing}
          className="inline-flex min-h-14 items-center gap-3 rounded-button bg-cobalt px-7 text-[18px] font-bold text-white hover:bg-cobalt-dark disabled:opacity-50">
          {sending ? "Sending" : "Send for reading"}
        </button>
      </div>
    </div>
  );
}
