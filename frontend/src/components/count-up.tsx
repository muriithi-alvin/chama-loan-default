"use client";

import { animate, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";

import { money } from "@/lib/format";

// Formats by name, not as functions: a server page can only hand a client
// component plain values, and a function prop broke the members' summary.
const FORMATS = { number: (n: number) => String(Math.round(n)), money } as const;

/** A number that counts up once when it first appears; the final text is in the HTML from the start. */
export function CountUp({ value, as = "number" }: { value: number; as?: keyof typeof FORMATS }) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduce = useReducedMotion();
  const format = FORMATS[as];
  useEffect(() => {
    const el = ref.current;
    if (!el || reduce) return;
    const controls = animate(0, value, {
      duration: 0.9,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (n) => {
        el.textContent = format(n);
      },
    });
    return () => controls.stop();
  }, [value, reduce, format]);
  return <span ref={ref}>{format(value)}</span>;
}
