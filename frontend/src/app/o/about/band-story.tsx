"use client";

import { motion, useReducedMotion, useScroll, useTransform, type MotionValue } from "motion/react";
import { useRef } from "react";

import { BAND, EffectIcon } from "@/components/beads";
import type { Band } from "@/lib/types";

// About the scores, the one scroll story (section 7): a collar of twenty beads
// sorts into three strands sized 50 / 30 / 20 (Low, Medium, High), then one
// bead opens to show its three reasons. With reduced motion it shows the end.

const BEADS: Band[] = [
  ...Array<Band>(4).fill("high"), ...Array<Band>(6).fill("medium"), ...Array<Band>(10).fill("low"),
];
const MIXED = ["red", "sun", "leaf", "cobalt", "orange"] as const;
const ROW_Y: Record<Band, number> = { high: -96, medium: 0, low: 96 };
const GAP = 34;

const EXAMPLE = [
  { sentence: "Missed a repayment at 2 of the last 3 meetings", effect: "raises risk" as const },
  { sentence: "Last missed a repayment 1 month ago", effect: "raises risk" as const },
  { sentence: "Has been in the records for 10 years", effect: "lowers risk" as const },
];

const STEPS = [
  "Each bead is one member with a loan running at a meeting.",
  "The early warning puts them in order of how likely a missed repayment looks in the next 3 meetings: the top 20% are High, the next 30% Medium, the rest Low.",
  "Every bead comes with its reasons, from the member's own record.",
];

function StoryBead({ band, index, progress }: { band: Band; index: number; progress: MotionValue<number> }) {
  const angle = (index / BEADS.length) * Math.PI * 2 - Math.PI / 2;
  const ringX = Math.cos(angle) * 128;
  const ringY = Math.sin(angle) * 128;
  const inRow = BEADS.slice(0, index).filter((b) => b === band).length;
  const rowCount = BEADS.filter((b) => b === band).length;
  const rowX = (inRow - (rowCount - 1) / 2) * GAP;
  const featured = index === 0;

  const x = useTransform(progress, [0.12, 0.45, 0.68, 0.82], [ringX, rowX, rowX, featured ? -150 : rowX]);
  const y = useTransform(progress, [0.12, 0.45, 0.68, 0.82], [ringY, ROW_Y[band], ROW_Y[band], featured ? -20 : ROW_Y[band]]);
  const scale = useTransform(progress, [0.68, 0.82], [1, featured ? 2.6 : 1]);
  const fade = useTransform(progress, [0.68, 0.82], [1, featured ? 1 : 0.25]);
  const tint = useTransform(progress, [0.3, 0.45], [0, 1]);

  return (
    <motion.span aria-hidden="true" className="absolute left-1/2 top-1/2 -ml-[13px] -mt-[13px]" style={{ x, y, scale, opacity: fade }}>
      <span className={`bead bead-${MIXED[index % MIXED.length]} absolute inset-0`} style={{ width: 26, height: 26 }} />
      <motion.span className={`bead bead-${BAND[band].colour} relative`} style={{ width: 26, height: 26, opacity: tint }} />
    </motion.span>
  );
}

function Labels({ progress }: { progress: MotionValue<number> }) {
  const opacity = useTransform(progress, [0.4, 0.5, 0.68, 0.76], [0, 1, 1, 0]);
  return (
    <motion.div aria-hidden="true" style={{ opacity }} className="pointer-events-none absolute inset-0">
      {(["high", "medium", "low"] as Band[]).map((band) => (
        <span key={band} className={`absolute left-1/2 top-1/2 -translate-y-1/2 rounded-full px-3 py-1 text-[14px] font-bold ${BAND[band].chip} ${BAND[band].text}`}
          style={{ marginTop: ROW_Y[band], marginLeft: -BEADS.filter((b) => b === band).length * GAP / 2 - 120 }}>
          {BAND[band].label} {band === "high" ? "20%" : band === "medium" ? "30%" : "50%"}
        </span>
      ))}
    </motion.div>
  );
}

function Reasons({ progress }: { progress: MotionValue<number> }) {
  const opacity = useTransform(progress, [0.8, 0.9], [0, 1]);
  const x = useTransform(progress, [0.8, 0.9], [24, 0]);
  return (
    <motion.div style={{ opacity, x }} className="absolute left-1/2 top-1/2 ml-[-80px] w-[min(340px,70vw)] -translate-y-1/2 rounded-card border border-line bg-white p-4 shadow-[0_14px_30px_rgba(20,33,61,.12)] sm:ml-[-60px]">
      <ReasonList />
    </motion.div>
  );
}

function ReasonList() {
  return (
    <ol className="flex flex-col gap-3">
      {EXAMPLE.map((r) => (
        <li key={r.sentence} className="flex items-start gap-2.5 text-[15px]">
          <EffectIcon effect={r.effect} size={18} />
          <span>
            <strong>{r.sentence}</strong>{" "}
            <span className={r.effect === "raises risk" ? "font-bold text-high" : "font-bold text-low"}>{r.effect}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

function Caption({ progress, index }: { progress: MotionValue<number>; index: number }) {
  const ranges = [[0, 0.05, 0.25, 0.32], [0.32, 0.4, 0.62, 0.7], [0.72, 0.8, 1, 1.01]][index];
  const opacity = useTransform(progress, ranges, [0, 1, 1, 0]);
  return (
    <motion.p style={{ opacity }} className="absolute inset-x-0 top-0 mx-auto max-w-[36em] px-4 text-center text-[18px] font-bold sm:text-[20px]">
      {STEPS[index]}
    </motion.p>
  );
}

/** With reduced motion: the three steps and the example, still. */
function StillStory() {
  return (
    <section aria-label="How members are put into bands" className="flex flex-col gap-4 rounded-card bg-cream p-6">
      {STEPS.map((s) => <p key={s} className="text-[17px]">{s}</p>)}
      <div className="rounded-card bg-white p-4"><ReasonList /></div>
    </section>
  );
}

/** The scroll story. Its own component, so the scroll tracker only exists
 * while the section it follows is on the page. */
function ScrollStory() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  return (
    <section ref={ref} aria-label="How members are put into bands" className="relative h-[280vh]">
      <div className="sticky top-0 flex h-dvh flex-col items-center justify-center overflow-hidden">
        <div className="relative h-[60px] w-full">
          {STEPS.map((_, i) => <Caption key={i} progress={scrollYProgress} index={i} />)}
        </div>
        <div className="relative h-[360px] w-full max-w-[720px]">
          {BEADS.map((band, i) => <StoryBead key={i} band={band} index={i} progress={scrollYProgress} />)}
          <Labels progress={scrollYProgress} />
          <Reasons progress={scrollYProgress} />
        </div>
        <p className="sr-only">
          {STEPS.join(" ")} For example: {EXAMPLE.map((r) => `${r.sentence}, ${r.effect}`).join("; ")}.
        </p>
      </div>
    </section>
  );
}

export function BandStory() {
  const reduce = useReducedMotion();
  return reduce ? <StillStory /> : <ScrollStory />;
}
