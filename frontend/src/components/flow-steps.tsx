import { Fragment } from "react";

export type Stage = "send" | "read" | "check" | "update" | "results";

const STAGES: { key: Stage; photo: string; typed: string }[] = [
  { key: "send", photo: "Send the photos", typed: "Choose the meeting" },
  { key: "read", photo: "Reading", typed: "Filled in" },
  { key: "check", photo: "Check the rows", typed: "Type the amounts" },
  { key: "update", photo: "Update the records", typed: "Update the records" },
  { key: "results", photo: "Who to follow up", typed: "Who to follow up" },
];

/** Where the treasurer is, from sending a page to its results (D-040). Each
 * stage opens the next by itself, so nobody needs the menu in between. */
export function FlowSteps({ at, typed = false, failed = false }: { at: Stage; typed?: boolean; failed?: boolean }) {
  const current = STAGES.findIndex((s) => s.key === at);
  return (
    <nav aria-label="Steps for adding a page">
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-2 text-[14px] font-bold">
        {STAGES.map((s, i) => {
          const done = i < current || (i === current && at === "results" && !failed);
          const here = i === current && !done;
          return (
            <Fragment key={s.key}>
              {i > 0 && <li aria-hidden="true" className={`h-0.5 w-5 rounded ${i <= current ? "bg-leaf" : "bg-line"}`} />}
              <li aria-current={here ? "step" : undefined}
                className={`inline-flex items-center gap-2 rounded-full px-3 py-1 ${here ? (failed ? "bg-high-bg text-high" : "bg-ice text-cobalt") : done ? "text-low" : "text-muted"}`}>
                {done ? (
                  <span aria-hidden="true" className="bead bead-leaf" style={{ width: 14, height: 14 }} />
                ) : here ? (
                  <span aria-hidden="true" className={`bead ${failed ? "bead-red" : "bead-cobalt bead-pulse"}`} style={{ width: 14, height: 14 }} />
                ) : (
                  <span aria-hidden="true" className="block h-[14px] w-[14px] rounded-full border-2 border-dotted border-field" />
                )}
                {typed ? s.typed : s.photo}
                <span className="sr-only">{done ? " (done)" : here ? (failed ? " (stopped)" : " (now)") : " (to come)"}</span>
              </li>
            </Fragment>
          );
        })}
      </ol>
    </nav>
  );
}
