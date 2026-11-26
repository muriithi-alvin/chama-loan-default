import type { Band } from "@/lib/types";

// Beads are the one decorative element of the Shanga style (section 7).

export type BeadColour = "red" | "ink" | "cobalt" | "orange" | "leaf" | "sun" | "white" | "empty";

export function Bead({ colour, size = 10, className = "" }: { colour: BeadColour; size?: number; className?: string }) {
  return (
    <span aria-hidden="true" className={`bead bead-${colour} ${className}`} style={{ width: size, height: size }} />
  );
}

export function BeadRow({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`bead-row ${className}`} />;
}

/** A corner of a bead collar: four rings of beads, like the logo's, for page headers and cards. */
export function BeadArc({ className = "", light = false }: { className?: string; light?: boolean }) {
  const rings: [number, string][] = light
    ? [[96, "#F6C343"], [74, "#FFFFFF"], [52, "#EE4654"], [30, "#6F8FE6"]]
    : [[96, "#2547A8"], [74, "#D62839"], [52, "#F6C343"], [30, "#187A42"]];
  return (
    <svg viewBox="0 0 220 220" aria-hidden="true" className={className}>
      {rings.map(([r, colour], i) => (
        <circle key={r} cx="110" cy="110" r={r} fill="none" stroke={colour} strokeWidth="9" strokeLinecap="round"
          strokeDasharray="0.1 17" opacity={light && i === 1 ? 0.55 : 1} />
      ))}
    </svg>
  );
}

/** Three concentric bead rings. */
export function Logo({ size = 44, onDark = false }: { size?: number; onDark?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 44 44" aria-hidden="true">
      <circle cx="22" cy="22" r="18" fill="none" stroke={onDark ? "#6F8FE6" : "#2547A8"} strokeWidth="6"
        strokeLinecap="round" strokeDasharray="0.1 9.3" />
      <circle cx="22" cy="22" r="9.5" fill="none" stroke={onDark ? "#EE4654" : "#D62839"} strokeWidth="5"
        strokeLinecap="round" strokeDasharray="0.1 7.4" />
      <circle cx="22" cy="22" r="3.2" fill="#F6C343" />
    </svg>
  );
}

// The bands in everyday words (Sprint II feedback: "High / Medium / Low" and
// test figures were hard to follow for officials who have never seen a model).
export const BAND = {
  low: {
    label: "Less likely to miss", beads: 1, colour: "leaf", text: "text-low", chip: "bg-low-bg",
    meaning: "Less likely to miss a repayment in the next 3 meetings.",
  },
  medium: {
    label: "Keep an eye on", beads: 2, colour: "sun", text: "text-medium", chip: "bg-medium-bg",
    meaning: "Could miss a repayment in the next 3 meetings. Check in when you can.",
  },
  high: {
    label: "Follow up now", beads: 3, colour: "red", text: "text-high", chip: "bg-high-bg",
    meaning: "More likely than others to miss a repayment in the next 3 meetings. Talk to them first.",
  },
} as const satisfies Record<Band, {
  label: string; beads: number; colour: BeadColour; text: string; chip: string; meaning: string;
}>;

/** What a reason does to the chance of a missed repayment, in plain words. */
export const EFFECT_TEXT = { "raises risk": "more likely to miss", "lowers risk": "less likely to miss" } as const;

/** The same, in English and Kiswahili (D-044): short for lists, long for a member's page. */
export const EFFECT_WORDS = {
  en: {
    short: EFFECT_TEXT,
    long: { "raises risk": "Makes a missed repayment more likely", "lowers risk": "Makes a missed repayment less likely" },
  },
  sw: {
    short: { "raises risk": "uwezekano zaidi wa kukosa", "lowers risk": "uwezekano mdogo wa kukosa" },
    long: { "raises risk": "Huongeza uwezekano wa kukosa marejesho", "lowers risk": "Hupunguza uwezekano wa kukosa marejesho" },
  },
} as const;

/** A band label: bead count, word and colour, so it never relies on colour alone. */
export function BandChip({ band, size = "md" }: { band: Band; size?: "sm" | "md" | "lg" }) {
  const b = BAND[band];
  const sizes = {
    sm: { pad: "py-0.5 pl-2 pr-2.5 text-[14px] gap-1.5", bead: 8 },
    md: { pad: "py-1 pl-2 pr-3 text-[14px] gap-2", bead: 10 },
    lg: { pad: "py-1.5 pl-3 pr-4 text-[18px] gap-2.5", bead: 14 },
  }[size];
  return (
    <span className={`inline-flex shrink-0 items-center rounded-full font-bold ${b.chip} ${b.text} ${sizes.pad}`}>
      <span aria-hidden="true" className="flex gap-[3px]">
        {Array.from({ length: b.beads }, (_, i) => (
          <Bead key={i} colour={b.colour} size={sizes.bead} />
        ))}
      </span>
      {b.label}
    </span>
  );
}

export function NoLoanChip() {
  return (
    <span className="inline-flex shrink-0 items-center gap-2 rounded-full bg-ice px-3 py-1 text-[14px] font-bold text-subtle">
      <Bead colour="white" size={10} />
      No loan running
    </span>
  );
}

/** An up arrow for "more likely to miss", a down arrow for "less likely": always shown with the words. */
export function EffectIcon({ effect, size = 20 }: { effect: "raises risk" | "lowers risk"; size?: number }) {
  const up = effect === "raises risk";
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={up ? "#9E1B2A" : "#135C30"}
      strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0">
      {up ? <path d="M12 19V5M6 11l6-6 6 6" /> : <path d="M12 5v14M6 13l6 6 6-6" />}
    </svg>
  );
}
