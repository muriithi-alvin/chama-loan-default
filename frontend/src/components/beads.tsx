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

export const BAND = {
  low: { label: "Low", beads: 1, colour: "leaf", text: "text-low", chip: "bg-low-bg" },
  medium: { label: "Medium", beads: 2, colour: "sun", text: "text-medium", chip: "bg-medium-bg" },
  high: { label: "High", beads: 3, colour: "red", text: "text-high", chip: "bg-high-bg" },
} as const satisfies Record<Band, { label: string; beads: number; colour: BeadColour; text: string; chip: string }>;

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

/** "Raises risk" with an up arrow, "Lowers risk" with a down arrow: always the words too. */
export function EffectIcon({ effect, size = 20 }: { effect: "raises risk" | "lowers risk"; size?: number }) {
  const up = effect === "raises risk";
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={up ? "#9E1B2A" : "#135C30"}
      strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0">
      {up ? <path d="M12 19V5M6 11l6-6 6 6" /> : <path d="M12 5v14M6 13l6 6 6-6" />}
    </svg>
  );
}
