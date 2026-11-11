"use client";

import { AlertTriangle, Check, ChevronLeft, ChevronRight, Info, Plus, Trash2, UserPlus } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { FlowSteps } from "@/components/flow-steps";
import { Card } from "@/components/page-header";
import { PhotoViewer } from "@/components/photo-viewer";
import { api, ApiProblem } from "@/lib/client-api";
import type { Draft, DraftFlag, DraftRow, DraftTable } from "@/lib/types";

type Save = "idle" | "saving" | "saved" | "failed";

function FlagNote({ flag }: { flag: DraftFlag }) {
  const check = flag.level === "check";
  return (
    <span className={`inline-flex items-start gap-1.5 text-[14px] ${check ? "font-bold text-high" : "text-medium"}`}>
      {check ? <AlertTriangle aria-hidden="true" size={15} className="mt-0.5 shrink-0" /> : <Info aria-hidden="true" size={15} className="mt-0.5 shrink-0" />}
      <span><span className="uppercase">{check ? "Check" : "Hint"}</span>: {flag.message}</span>
    </span>
  );
}

/** One cell: edited locally, saved when you leave it. */
function Cell({ row, column, label, onSave, wide = false, compact = false }: {
  row: DraftRow; column: string; label: string; onSave: (row: DraftRow, column: string, value: string) => void;
  wide?: boolean; compact?: boolean;
}) {
  const saved = row.cells[column] ?? "";
  const [value, setValue] = useState(saved);
  useEffect(() => setValue(saved), [saved]);
  const flags = row.flags.filter((f) => f.col === column);
  const check = flags.some((f) => f.level === "check");
  const hint = !check && flags.length > 0;
  return (
    <label className={`flex flex-col gap-1 ${wide ? "min-w-[180px]" : "min-w-[96px]"}`}>
      <span className={compact ? "sr-only" : "text-[13px] font-bold text-muted"}>{label}</span>
      <span className="relative">
        <input value={value} onChange={(e) => setValue(e.target.value)}
          onBlur={() => value !== saved && onSave(row, column, value)}
          onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          aria-invalid={check} aria-label={compact ? label : undefined}
          className={`h-11 w-full rounded-[10px] border-[1.5px] bg-white px-2.5 text-[15px] tabular ${
            check ? "border-high bg-high-bg/40 pr-8" : hint ? "border-sun pr-8" : "border-field"
          }`} />
        {(check || hint) && (
          <AlertTriangle aria-hidden="true" size={16} className={`absolute right-2.5 top-1/2 -translate-y-1/2 ${check ? "text-high" : "text-medium"}`} />
        )}
      </span>
    </label>
  );
}

function RowFlags({ row }: { row: DraftRow }) {
  if (!row.flags.length) return null;
  return <div className="flex flex-col gap-1">{row.flags.map((f, i) => <FlagNote key={i} flag={f} />)}</div>;
}

export function Review({ initial }: { initial: Draft }) {
  const router = useRouter();
  const [draft, setDraft] = useState(initial);
  const [save, setSave] = useState<Save>("idle");
  const [problem, setProblem] = useState<ApiProblem | null>(null);
  const [confirm, setConfirm] = useState<"accept" | "discard" | null>(null);
  const [busy, setBusy] = useState(false);
  const [card, setCard] = useState(0);
  const [part, setPart] = useState(1);
  const dialog = useRef<HTMLDialogElement>(null);
  const editable = draft.status === "ready";
  const typed = draft.source === "typed";      // typed in: no photo, the ledger takes the whole width (D-038)

  useEffect(() => {
    if (confirm) dialog.current?.showModal();
    else dialog.current?.close();
  }, [confirm]);

  const byTable = useMemo(() => {
    const out: Record<DraftTable, DraftRow[]> = { meetings: [], statements: [], new_loans: [] };
    for (const r of draft.rows) out[r.table].push(r);
    return out;
  }, [draft.rows]);
  const meeting = byTable.meetings[0];
  const lines = byTable.statements;
  const checks = draft.rows.reduce((n, r) => n + r.flags.filter((f) => f.level === "check").length, 0);

  async function call(path: string, options: Parameters<typeof api>[1]) {
    setSave("saving");
    setProblem(null);
    try {
      const next = await api<Draft>(path, options);
      setDraft(next);
      setSave("saved");
      return next;
    } catch (e) {
      setSave("failed");
      setProblem(e instanceof ApiProblem ? e : new ApiProblem(0, "unknown", "The change was not saved. Try again."));
      return null;
    }
  }

  const saveCell = (row: DraftRow, column: string, value: string) =>
    call(`/api/uploads/${draft.upload_id}/rows/${row.id}`, { method: "PATCH", json: { column, value } });
  const addRow = async (table: DraftTable) => {
    const next = await call(`/api/uploads/${draft.upload_id}/rows`, { json: { table } });
    if (next && table === "statements") setCard(next.rows.filter((r) => r.table === "statements").length - 1);
  };
  const deleteRow = (row: DraftRow) =>
    call(`/api/uploads/${draft.upload_id}/rows/${row.id}`, { method: "DELETE" });
  const matchName = (raw: string, member: string | null, isNew: boolean) =>
    call(`/api/uploads/${draft.upload_id}/names`, { method: "PUT", json: { raw, member, is_new: isNew } });

  async function finish(action: "accept" | "discard") {
    setBusy(true);
    setProblem(null);
    try {
      if (action === "accept") {
        const done = await api<{ run_id: number }>(`/api/uploads/${draft.upload_id}/accept`, { method: "POST" });
        router.push(`/o/runs/${done.run_id}`);
      } else {
        await api(`/api/uploads/${draft.upload_id}/discard`, { method: "POST" });
        router.push("/o/uploads");
      }
    } catch (e) {
      setProblem(e instanceof ApiProblem ? e : new ApiProblem(0, "unknown", "That did not work. Try again."));
      setConfirm(null);
      setBusy(false);
    }
  }

  const columns = draft.columns;
  const statementColumns = columns.statements;

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
      <div className="xl:col-span-12"><FlowSteps at="check" typed={typed} /></div>
      {!typed && (
        <div className="xl:col-span-5">
          <div className="flex flex-col gap-3 xl:sticky xl:top-6">
            {draft.photo.available && draft.photo.parts > 1 && (
              <div role="tablist" aria-label="Photos of this meeting" className="flex flex-wrap gap-2">
                {Array.from({ length: draft.photo.parts }, (_, i) => i + 1).map((n) => (
                  <button key={n} type="button" role="tab" aria-selected={part === n} onClick={() => setPart(n)}
                    className={`min-h-11 rounded-full px-4 text-[15px] font-bold ${part === n ? "bg-ink text-white" : "border-[1.5px] border-ink bg-white hover:bg-ice"}`}>
                    Part {n} of {draft.photo.parts}
                  </button>
                ))}
              </div>
            )}
            {draft.photo.available ? (
              <PhotoViewer key={part} src={`/api/uploads/${draft.upload_id}/photo?part=${part}`}
                alt={draft.photo.parts > 1 ? `Part ${part} of the scanned ledger page` : "The scanned ledger page"}
                className={draft.photo.parts > 1 ? "h-[380px] xl:h-[calc(100dvh-200px)]" : "h-[380px] xl:h-[calc(100dvh-140px)]"} />
            ) : (
              <Card tone="cream"><p className="text-[16px]">{draft.photo.reason}</p></Card>
            )}
          </div>
        </div>
      )}

      <div className={`flex flex-col gap-6 ${typed ? "xl:col-span-12" : "xl:col-span-7"}`}>
        {typed && (
          <Card tone="cream" className="flex flex-col gap-1.5">
            <p className="text-[17px] font-bold">Each member is on a line, with the balance they carried from the last meeting.</p>
            <p className="text-[16px] text-subtle">
              Type what each one paid: Monthly, Repaid, Interest and the Balance after. Leave a cell empty if nothing was paid.
              A loan given today goes under &ldquo;Loans given at this meeting&rdquo;. Everything is saved as you go.
            </p>
          </Card>
        )}
        <div aria-live="polite" className="flex flex-wrap items-center gap-3 text-[15px]">
          <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 font-bold ${checks ? "bg-high-bg text-high" : "bg-low-bg text-low"}`}>
            {checks ? <AlertTriangle aria-hidden="true" size={15} /> : <Check aria-hidden="true" size={15} />}
            {checks ? `${checks} ${checks === 1 ? "cell" : "cells"} to check` : "No cells flagged"}
          </span>
          <span className="text-muted">
            {save === "saving" ? "Saving…" : save === "saved" ? "All changes saved" : save === "failed" ? "Not saved" : "Changes are saved as you go"}
          </span>
        </div>
        {problem && (
          <p role="alert" className="rounded-button bg-high-bg px-4 py-3 text-[16px] text-high">
            {problem.message} {problem.ref && <span className="text-[14px]">(reference {problem.ref})</span>}
          </p>
        )}
        {!editable && (
          <p className="rounded-button bg-cream px-4 py-3 text-[16px]">This scan is {draft.status}; it can no longer be changed here.</p>
        )}

        {meeting && (
          <Card aria-labelledby="rv-meeting" className="flex flex-col gap-4">
            <h2 id="rv-meeting" className="text-[22px]">{typed ? "The meeting: date and totals" : "The page: date and totals"}</h2>
            <fieldset disabled={!editable} className="grid grid-cols-2 gap-3 md:grid-cols-3">
              {columns.meetings.filter((c) => !["host", "notes", "column_headers"].includes(c.key)).map((c) => (
                <Cell key={c.key} row={meeting} column={c.key} label={c.label} onSave={saveCell} />
              ))}
            </fieldset>
            <details className="text-[15px]">
              <summary className="cursor-pointer font-bold text-cobalt">Notes, host and column headings</summary>
              <fieldset disabled={!editable} className="mt-3 grid gap-3 md:grid-cols-3">
                {columns.meetings.filter((c) => ["host", "notes", "column_headers"].includes(c.key)).map((c) => (
                  <Cell key={c.key} row={meeting} column={c.key} label={c.label} onSave={saveCell} wide />
                ))}
              </fieldset>
            </details>
            <RowFlags row={meeting} />
            {draft.problems.filter((p) => p.field === "meeting_date").map((p) => (
              <p key={p.message} className="text-[15px] font-bold text-high">{p.message}</p>
            ))}
          </Card>
        )}

        <Card aria-labelledby="rv-names" className="flex flex-col gap-4">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 id="rv-names" className="text-[22px]">Names on the page</h2>
            <span className="text-[15px] text-muted">
              {draft.names.filter((n) => n.member || n.is_new).length} of {draft.names.length} matched
            </span>
          </div>
          <ul className="flex flex-col">
            {draft.names.map((n) => {
              const done = n.member || n.is_new;
              return (
                <li key={n.raw} className="flex flex-col gap-2.5 border-t border-line py-3.5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <span className="flex items-center gap-2 text-[16px]">
                      {done ? <Check aria-hidden="true" size={18} className="text-leaf" /> : <AlertTriangle aria-hidden="true" size={18} className="text-high" />}
                      Written as <strong className="capitalize">&ldquo;{n.raw}&rdquo;</strong>
                      {n.known_spelling && <span className="text-[14px] text-muted">(known spelling)</span>}
                    </span>
                    <label className="flex items-center gap-2 text-[15px]">
                      <span className="sr-only">Member for {n.raw}</span>
                      <select disabled={!editable} value={n.is_new ? "__new" : n.member ?? ""}
                        onChange={(e) => matchName(n.raw, e.target.value === "__new" ? null : e.target.value || null, e.target.value === "__new")}
                        className={`h-11 min-w-[220px] rounded-[10px] border-[1.5px] bg-white px-2.5 text-[15px] ${done ? "border-field" : "border-high"}`}>
                        <option value="">Choose the member…</option>
                        {draft.members.map((m) => <option key={m} value={m}>{m}</option>)}
                        <option value="__new">A new member</option>
                      </select>
                    </label>
                  </div>
                  {!done && n.suggestions.length > 0 && (
                    <div className="flex flex-wrap items-center gap-2 text-[14px]">
                      <span className="text-muted">Looks like:</span>
                      {n.suggestions.map((s) => (
                        <button key={s.name} type="button" disabled={!editable} onClick={() => matchName(n.raw, s.name, false)}
                          className="min-h-9 rounded-full border-[1.5px] border-cobalt px-3 font-bold text-cobalt hover:bg-ice">
                          {s.name}
                        </button>
                      ))}
                    </div>
                  )}
                  {!done && !n.suggestions.length && (
                    <button type="button" disabled={!editable} onClick={() => matchName(n.raw, null, true)}
                      className="inline-flex min-h-9 items-center gap-1.5 self-start rounded-full border-[1.5px] border-ink px-3 text-[14px] font-bold hover:bg-ice">
                      <UserPlus aria-hidden="true" size={15} /> Mark as a new member
                    </button>
                  )}
                </li>
              );
            })}
            {draft.names.length === 0 && <li className="text-[15px] text-muted">No names read yet.</li>}
          </ul>
        </Card>

        <Card aria-labelledby="rv-lines" className="flex flex-col gap-4 p-4 sm:p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 id="rv-lines" className="text-[22px]">Member lines ({lines.length})</h2>
            <button type="button" disabled={!editable} onClick={() => addRow("statements")}
              className="inline-flex min-h-11 items-center gap-1.5 rounded-button border-[1.5px] border-ink px-3.5 text-[15px] font-bold hover:bg-ice disabled:opacity-50">
              <Plus aria-hidden="true" size={16} /> Add a line
            </button>
          </div>

          {/* Desktop: every line as a row of fields */}
          <fieldset disabled={!editable} className="hidden flex-col md:flex">
            <legend className="sr-only">Member lines</legend>
            {lines.map((row, i) => (
              <div key={row.id} className={`flex flex-col gap-2 border-t border-line py-3 ${row.flags.some((f) => f.level === "check") ? "bg-high-bg/20" : ""}`}>
                <div className="flex items-end gap-2 overflow-x-auto pb-1">
                  <span className="tabular w-7 shrink-0 pb-3 text-right text-[14px] text-muted">{i + 1}</span>
                  {statementColumns.map((c) => (
                    <Cell key={c.key} row={row} column={c.key} label={c.label} onSave={saveCell} wide={c.key === "member_name" || c.key === "remarks"} compact={i > 0} />
                  ))}
                  <button type="button" onClick={() => deleteRow(row)} aria-label={`Delete line ${i + 1}`}
                    className="mb-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-high hover:bg-high-bg">
                    <Trash2 aria-hidden="true" size={18} />
                  </button>
                </div>
                <div className="pl-9"><RowFlags row={row} /></div>
              </div>
            ))}
          </fieldset>

          {/* Phone: one line at a time as a card */}
          <div className="md:hidden">
            <AnimatePresence mode="wait">
              {lines[card] && (
                <motion.fieldset key={lines[card].id} disabled={!editable} initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -24 }}
                  className="flex flex-col gap-3 rounded-card border border-line p-4">
                  <legend className="px-1 text-[15px] font-bold">Line {card + 1} of {lines.length}</legend>
                  <div className="grid grid-cols-2 gap-3">
                    {statementColumns.map((c) => (
                      <Cell key={c.key} row={lines[card]} column={c.key} label={c.label} onSave={saveCell} />
                    ))}
                  </div>
                  <RowFlags row={lines[card]} />
                  <button type="button" onClick={() => deleteRow(lines[card])}
                    className="inline-flex min-h-11 items-center gap-1.5 self-start rounded-button px-3 text-[15px] font-bold text-high hover:bg-high-bg">
                    <Trash2 aria-hidden="true" size={16} /> Delete this line
                  </button>
                </motion.fieldset>
              )}
            </AnimatePresence>
            <div className="mt-3 flex justify-between">
              <button type="button" disabled={card === 0} onClick={() => setCard((c) => c - 1)}
                className="inline-flex min-h-12 items-center gap-1 rounded-button border-[1.5px] border-ink px-4 font-bold disabled:opacity-40">
                <ChevronLeft aria-hidden="true" size={18} /> Previous
              </button>
              <button type="button" disabled={card >= lines.length - 1} onClick={() => setCard((c) => c + 1)}
                className="inline-flex min-h-12 items-center gap-1 rounded-button border-[1.5px] border-ink px-4 font-bold disabled:opacity-40">
                Next <ChevronRight aria-hidden="true" size={18} />
              </button>
            </div>
          </div>
        </Card>

        <Card aria-labelledby="rv-loans" className="flex flex-col gap-4 p-4 sm:p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 id="rv-loans" className="text-[22px]">Loans given at this meeting ({byTable.new_loans.length})</h2>
            <button type="button" disabled={!editable} onClick={() => addRow("new_loans")}
              className="inline-flex min-h-11 items-center gap-1.5 rounded-button border-[1.5px] border-ink px-3.5 text-[15px] font-bold hover:bg-ice disabled:opacity-50">
              <Plus aria-hidden="true" size={16} /> Add a loan
            </button>
          </div>
          <fieldset disabled={!editable} className="flex flex-col">
            <legend className="sr-only">New loans</legend>
            {byTable.new_loans.map((row, i) => (
              <div key={row.id} className="flex flex-col gap-2 border-t border-line py-3">
                <div className="flex flex-wrap items-end gap-2">
                  {columns.new_loans.map((c) => (
                    <Cell key={c.key} row={row} column={c.key} label={c.label} onSave={saveCell} wide={c.key === "member_name"} />
                  ))}
                  <button type="button" onClick={() => deleteRow(row)} aria-label={`Delete loan ${i + 1}`}
                    className="mb-0.5 flex h-10 w-10 items-center justify-center rounded-full text-high hover:bg-high-bg">
                    <Trash2 aria-hidden="true" size={18} />
                  </button>
                </div>
                <RowFlags row={row} />
              </div>
            ))}
            {byTable.new_loans.length === 0 && <p className="text-[15px] text-muted">None read from the page.</p>}
          </fieldset>
        </Card>

        {editable && (
          <div className="sticky bottom-24 z-10 flex flex-col gap-3 rounded-card border border-line bg-white/95 p-4 shadow-[0_-8px_24px_rgba(20,33,61,.08)] backdrop-blur lg:bottom-4">
            {draft.problems.length > 0 && (
              <ul className="flex flex-col gap-1 text-[15px] text-high">
                {draft.problems.map((p) => <li key={p.message} className="flex items-start gap-1.5"><AlertTriangle aria-hidden="true" size={15} className="mt-0.5 shrink-0" />{p.message}</li>)}
              </ul>
            )}
            <div className="flex flex-wrap gap-3">
              <button type="button" disabled={!draft.ready_to_accept || busy} onClick={() => setConfirm("accept")}
                className="inline-flex min-h-14 items-center gap-2 rounded-button bg-cobalt px-6 text-[18px] font-bold text-white hover:bg-cobalt-dark disabled:opacity-50">
                <Check aria-hidden="true" size={20} /> Accept the page
              </button>
              <button type="button" disabled={busy} onClick={() => setConfirm("discard")}
                className="inline-flex min-h-14 items-center rounded-button border-2 border-ink px-5 text-[16px] font-bold hover:bg-ice">
                Discard
              </button>
            </div>
          </div>
        )}
      </div>

      <dialog ref={dialog} onClose={() => setConfirm(null)} aria-labelledby="rv-confirm"
        className="m-auto w-[min(520px,92vw)] rounded-card p-0 backdrop:bg-ink/50">
        <div className="flex flex-col gap-4 p-6">
          <h2 id="rv-confirm" className="text-[26px]">{confirm === "accept" ? "Accept this page?" : "Discard this scan?"}</h2>
          <p className="text-[17px] text-subtle">
            {confirm === "accept"
              ? `The ${lines.length} lines become the next ledger page in the records, and Kibaba updates the records and works out who to follow up. You will see the results next. After this, the page can only change through a new page.`
              : typed ? "This typed page is set aside and nothing is added to the records. The edit record keeps what was typed."
                : "The rows read from this photo are set aside and nothing is added to the records. The edit record keeps what was changed."}
          </p>
          <div className="flex flex-wrap gap-3">
            <button type="button" disabled={busy} onClick={() => confirm && finish(confirm)}
              className={`inline-flex min-h-12 items-center rounded-button px-5 text-[16px] font-bold text-white disabled:opacity-60 ${confirm === "accept" ? "bg-cobalt hover:bg-cobalt-dark" : "bg-high"}`}>
              {busy ? "Working…" : confirm === "accept" ? "Yes, accept the page" : "Yes, discard it"}
            </button>
            <button type="button" disabled={busy} onClick={() => setConfirm(null)}
              className="inline-flex min-h-12 items-center rounded-button border-2 border-ink px-5 text-[16px] font-bold hover:bg-ice">
              Go back
            </button>
          </div>
        </div>
      </dialog>
    </div>
  );
}
