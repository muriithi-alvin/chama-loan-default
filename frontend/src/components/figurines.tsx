// Beaded wire figurines of women's everyday life (section 7): single paths drawn
// as strings of beads that slowly travel along the wire. Placeholder art; a
// Kenyan illustrator's drawings can replace these paths without code changes.
// Shown only on sign-in, empty states, "not allowed" and About the scores.

type Tone = "colour" | "light" | "ink";

function palette(tone: Tone) {
  if (tone === "light") return { line: "#FFF4D6", a: "#EE4654", b: "#6F8FE6", c: "#F6C343", d: "#2EA05D", e: "#F07F1A" };
  if (tone === "ink") return { line: "#14213D", a: "#14213D", b: "#14213D", c: "#14213D", d: "#14213D", e: "#14213D" };
  return { line: "#14213D", a: "#D62839", b: "#2547A8", c: "#F6C343", d: "#187A42", e: "#F07F1A" };
}

/** One woman: head, headwrap, shoulders and a long dress. */
function Woman({ x = 0, y = 0, wrap, dress, sash, line, children }: {
  x?: number; y?: number; wrap: string; dress: string; sash: string; line: string; children?: React.ReactNode;
}) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <circle className="wire" cx="60" cy="34" r="16" stroke={line} />
      <path className="wire" stroke={wrap} d="M42 30 C44 8 76 8 78 30 M78 24 C90 18 94 30 84 36" />
      <path className="wire" stroke={line} d="M40 72 C50 60 70 60 80 72" />
      <path className="wire" stroke={dress} d="M42 74 C38 120 30 170 22 228 L98 228 C90 170 82 120 78 74" />
      <path className="wire" stroke={sash} d="M34 134 C50 142 70 142 86 134" />
      {children}
    </g>
  );
}

/** A woman cooking at a sufuria, steam rising. */
export function Cooking({ tone = "colour", className = "" }: { tone?: Tone; className?: string }) {
  const p = palette(tone);
  return (
    <svg viewBox="0 0 240 262" aria-hidden="true" className={className}>
      <g transform="translate(0 24)">
        <Woman wrap={p.a} dress={p.b} sash={p.c} line={p.line}>
          <path className="wire" stroke={p.line} d="M42 78 C24 100 24 122 38 134 M78 78 C96 98 104 112 116 118" />
          <path className="wire" stroke={p.e} d="M110 106 L148 160" />
        </Woman>
        <path className="wire" stroke={p.line} d="M128 164 C128 154 206 154 206 164 C206 174 128 174 128 164 M132 168 L140 200 L194 200 L202 168" />
        <path className="wire" stroke={p.a} d="M134 206 L200 206 M140 206 L130 234 M194 206 L204 234" />
        <path className="figure-steam" stroke="#4A5470" style={{ fill: "none", strokeWidth: 5, strokeLinecap: "round", strokeDasharray: "0.1 9" }} d="M152 146 C146 132 158 124 152 108" />
        <path className="figure-steam" stroke="#4A5470" style={{ fill: "none", strokeWidth: 5, strokeLinecap: "round", strokeDasharray: "0.1 9", animationDelay: "0s, 1s" }} d="M168 144 C162 128 174 120 168 102" />
      </g>
    </svg>
  );
}

/** Three women singing, arms raised, notes floating up. */
export function Singing({ tone = "colour", className = "" }: { tone?: Tone; className?: string }) {
  const p = palette(tone);
  return (
    <svg viewBox="0 0 340 262" aria-hidden="true" className={className}>
      <g transform="translate(0 24)">
        <Woman wrap={p.d} dress={p.a} sash={p.b} line={p.line}>
          <g className="figure-sway"><path className="wire" stroke={p.line} d="M42 76 C30 56 24 36 30 14 M78 76 C90 56 96 36 90 14" /></g>
          <circle className="figure-note" cx="34" cy="2" r="5" fill={p.c} />
        </Woman>
        <Woman x={110} wrap={p.e} dress={p.d} sash={p.c} line={p.line}>
          <path className="wire" stroke={p.line} d="M42 78 C36 96 48 104 60 100 M78 78 C84 96 72 104 60 100" />
          <circle className="figure-note" cx="60" cy="-6" r="5" fill={p.b} style={{ animationDelay: "0.7s" }} />
        </Woman>
        <Woman x={220} wrap={p.b} dress={p.c} sash={p.a} line={p.line}>
          <g className="figure-sway" style={{ animationDelay: "0.8s" }}><path className="wire" stroke={p.line} d="M78 76 C92 58 98 38 92 16" /></g>
          <path className="wire" stroke={p.line} d="M42 78 C34 92 44 104 56 100" />
          <circle className="figure-note" cx="104" cy="2" r="5" fill={p.d} style={{ animationDelay: "2.1s" }} />
        </Woman>
      </g>
    </svg>
  );
}

/** Two women at a chama meeting with the ledger open between them. */
export function Meeting({ tone = "colour", className = "" }: { tone?: Tone; className?: string }) {
  const p = palette(tone);
  return (
    <svg viewBox="0 0 250 262" aria-hidden="true" className={className}>
      <g transform="translate(0 24)">
        <Woman wrap={p.c} dress={p.b} sash={p.a} line={p.line}>
          <path className="wire" stroke={p.line} d="M42 78 C32 90 28 98 30 110 M78 78 C88 90 92 98 90 110" />
          <path className="wire" stroke={p.e} d="M24 102 L60 112 L96 102 L96 134 L60 144 L24 134 Z M60 112 L60 144" />
        </Woman>
        <Woman x={118} wrap={p.a} dress={p.d} sash={p.c} line={p.line}>
          <path className="wire" stroke={p.line} d="M42 78 C30 92 16 104 0 112 M78 78 C88 104 90 124 86 140" />
        </Woman>
      </g>
    </svg>
  );
}

/** A market stall: a woman with a basket of fruit and a phone for payment. */
export function Market({ tone = "colour", className = "" }: { tone?: Tone; className?: string }) {
  const p = palette(tone);
  return (
    <svg viewBox="0 0 250 262" aria-hidden="true" className={className}>
      <g transform="translate(0 24)">
        <Woman wrap={p.b} dress={p.e} sash={p.d} line={p.line}>
          <path className="wire" stroke={p.line} d="M42 78 C30 96 34 110 44 116 M78 78 C96 86 108 78 116 66" />
          <path className="wire" stroke={p.c} d="M110 50 L124 50 L124 74 L110 74 Z" />
        </Woman>
        <path className="wire" stroke={p.line} d="M140 150 L236 150 M146 150 L150 228 M230 150 L226 228" />
        <path className="wire" stroke={p.a} d="M152 140 C152 120 176 120 176 140 M180 140 C180 116 206 116 206 140 M208 140 C208 124 228 124 228 140" />
      </g>
    </svg>
  );
}
