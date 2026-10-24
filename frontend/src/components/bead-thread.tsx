"use client";

import { motion, useReducedMotion } from "motion/react";

/** A bead travelling along a thread while work goes on; it settles at the end
 * when done, or stops and turns red when it fails (section 7, scan status). */
export function BeadThread({ state, steps }: { state: "working" | "done" | "failed"; steps: string[] }) {
  const reduce = useReducedMotion();
  return (
    <div className="flex flex-col gap-3">
      <div className="relative h-8">
        <svg aria-hidden="true" viewBox="0 0 600 12" preserveAspectRatio="none" className="absolute inset-x-0 top-1/2 h-3 w-full -translate-y-1/2">
          <line x1="6" y1="6" x2="594" y2="6" className={state === "working" ? "wire" : ""} stroke="#C7CFE0" strokeWidth="4" strokeLinecap="round" />
        </svg>
        <motion.span aria-hidden="true"
          className={`bead absolute top-1/2 -mt-[14px] -ml-[14px] ${state === "failed" ? "bead-red" : state === "done" ? "bead-leaf" : "bead-cobalt"}`}
          style={{ width: 28, height: 28 }}
          initial={false}
          animate={
            state === "working" && !reduce
              ? { left: ["4%", "88%", "4%"], scale: [1, 1.12, 1] }
              : { left: state === "done" ? "96%" : state === "failed" ? "50%" : "4%", scale: 1 }
          }
          transition={state === "working" && !reduce ? { duration: 3.2, repeat: Infinity, ease: "easeInOut" } : { type: "spring", stiffness: 120, damping: 14 }}
        >
          {state === "failed" && <span className="flex h-full w-full items-center justify-center text-[15px] font-extrabold text-white">!</span>}
        </motion.span>
      </div>
      <div className="flex justify-between text-[14px] font-bold text-muted">
        {steps.map((s) => <span key={s}>{s}</span>)}
      </div>
    </div>
  );
}
