"use client";

import { useEffect, useRef } from "react";

// The sign-in page's bead collar (section 7, "the one memorable moment"):
// six rings of glass beads. Beads part around the pointer and spring back;
// a tap sends a colour ripple outwards; a soft highlight chases round each
// ring. Drawn on one canvas from pre-rendered bead sprites, it pauses when
// the tab is hidden or the collar is off screen, and with reduced motion it
// is drawn once and stays still. The form never waits for it.

const SIZE = 580; // drawing units; the canvas scales to its box
const RADII = [126, 152, 178, 204, 230, 256];
const BEAD = 14;
const COLOURS: [string, string, string][] = [
  // [highlight, light, dark] per colour: red, ink, cobalt, orange, leaf, sun
  ["rgba(255,255,255,.85)", "#EE4654", "#A11B29"],
  ["rgba(255,255,255,.7)", "#3A4A75", "#0B1428"],
  ["rgba(255,255,255,.85)", "#4470DB", "#18317A"],
  ["rgba(255,255,255,.85)", "#FF9E45", "#C25A08"],
  ["rgba(255,255,255,.85)", "#2EA05D", "#0E552C"],
  ["rgba(255,255,255,.9)", "#FFD95E", "#D19A12"],
];
const PART_RADIUS = 150;
const PART_PUSH = 40;
const CHASE_SECONDS = 6;

type BeadState = { x: number; y: number; colour: number; turn: number; dx: number; dy: number; vx: number; vy: number };

function sprite(colour: [string, string, string], px: number): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = c.height = px;
  const g = c.getContext("2d")!;
  const r = px / 2;
  const body = g.createRadialGradient(r, r * 1.16, 0, r, r * 1.16, r * 1.1);
  body.addColorStop(0, colour[1]);
  body.addColorStop(0.38, colour[1]);
  body.addColorStop(1, colour[2]);
  g.fillStyle = body;
  g.beginPath();
  g.arc(r, r, r, 0, Math.PI * 2);
  g.fill();
  const shine = g.createRadialGradient(r * 0.68, r * 0.6, 0, r * 0.68, r * 0.6, r * 0.7);
  shine.addColorStop(0, colour[0]);
  shine.addColorStop(0.38, colour[0]);
  shine.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = shine;
  g.beginPath();
  g.arc(r, r, r, 0, Math.PI * 2);
  g.fill();
  return c;
}

function makeBeads(): BeadState[] {
  const beads: BeadState[] = [];
  RADII.forEach((r, ri) => {
    const n = Math.round((2 * Math.PI * r) / 25);
    for (let k = 0; k < n; k++) {
      const a = (k / n) * Math.PI * 2 - Math.PI / 2;
      beads.push({
        x: SIZE / 2 + r * Math.cos(a),
        y: SIZE / 2 + r * Math.sin(a),
        colour: (ri + (Math.floor(k / 4) % 2) * 3) % 6,
        turn: ri % 2 ? 1 - k / n : k / n,
        dx: 0, dy: 0, vx: 0, vy: 0,
      });
    }
  });
  return beads;
}

export function BeadCollar({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const beads = makeBeads();
    let scale = 1;
    let sprites: HTMLCanvasElement[] = [];
    let pointer: { x: number; y: number } | null = null;
    let ripple: { x: number; y: number; start: number } | null = null;
    let frame = 0;
    let visible = true;
    let onScreen = true;

    const resize = () => {
      const box = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(box.width * dpr);
      canvas.height = Math.round(box.height * dpr);
      scale = (box.width * dpr) / SIZE;
      sprites = COLOURS.map((c) => sprite(c, Math.ceil(BEAD * 2 * scale)));
      draw(performance.now());
    };

    const draw = (now: number) => {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      const chase = still ? -1 : (now / 1000 / CHASE_SECONDS) % 1;
      for (const b of beads) {
        let size = BEAD;
        if (chase >= 0) {
          const gap = Math.abs(chase - b.turn);
          const near = Math.min(gap, 1 - gap);
          if (near < 0.02) size *= 1 + 0.3 * (1 - near / 0.02);
        }
        if (ripple) {
          const reach = (now - ripple.start) * 0.9; // drawing units per ms
          const d = Math.hypot(b.x - ripple.x, b.y - ripple.y);
          const wave = Math.abs(reach - d);
          if (wave < 60) size *= 1 + 0.95 * (1 - wave / 60);
        }
        const img = sprites[b.colour];
        ctx.drawImage(img, b.x + b.dx - size / 2, b.y + b.dy - size / 2, size, size);
      }
    };

    const step = (now: number) => {
      // springs: each bead is pushed away from the pointer and pulled home
      for (const b of beads) {
        let tx = 0;
        let ty = 0;
        if (pointer) {
          const ox = b.x - pointer.x;
          const oy = b.y - pointer.y;
          const d = Math.hypot(ox, oy) || 1;
          if (d < PART_RADIUS) {
            const f = Math.pow(1 - d / PART_RADIUS, 2) * PART_PUSH;
            tx = (ox / d) * f;
            ty = (oy / d) * f;
          }
        }
        b.vx = (b.vx + (tx - b.dx) * 0.12) * 0.78;
        b.vy = (b.vy + (ty - b.dy) * 0.12) * 0.78;
        b.dx += b.vx;
        b.dy += b.vy;
      }
      if (ripple && now - ripple.start > 1100) ripple = null;
      draw(now);
      frame = visible && onScreen ? requestAnimationFrame(step) : 0;
    };

    const start = () => {
      if (!still && !frame && visible && onScreen) frame = requestAnimationFrame(step);
    };

    const toLocal = (e: PointerEvent) => {
      const box = canvas.getBoundingClientRect();
      return { x: ((e.clientX - box.left) / box.width) * SIZE, y: ((e.clientY - box.top) / box.height) * SIZE };
    };
    const onMove = (e: PointerEvent) => {
      pointer = toLocal(e);
      start();
    };
    const onLeave = () => {
      pointer = null;
    };
    const onDown = (e: PointerEvent) => {
      const p = toLocal(e);
      ripple = { ...p, start: performance.now() };
      start();
    };
    const onVisibility = () => {
      visible = document.visibilityState === "visible";
      start();
    };

    const observer = new IntersectionObserver(([entry]) => {
      onScreen = entry.isIntersecting;
      start();
    });
    observer.observe(canvas);
    const resizer = new ResizeObserver(resize);
    resizer.observe(canvas);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerleave", onLeave);
    canvas.addEventListener("pointerdown", onDown);
    document.addEventListener("visibilitychange", onVisibility);
    resize();
    start();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      resizer.disconnect();
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerleave", onLeave);
      canvas.removeEventListener("pointerdown", onDown);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  return (
    <div className={`@container relative aspect-square w-full max-w-[580px] ${className}`}>
      <canvas ref={canvasRef} aria-hidden="true" className="absolute inset-0 h-full w-full cursor-crosshair touch-none" />
      <div className="pointer-events-none absolute left-1/2 top-1/2 flex aspect-square w-[34%] -translate-x-1/2 -translate-y-1/2 flex-col items-center justify-center gap-1.5 rounded-full bg-white text-center shadow-[inset_0_0_0_6px_#FFF4D6,inset_0_0_0_8px_#F6C343]">
        <span lang="sw" className="font-display text-[clamp(14px,4cqw,23px)] font-extrabold leading-[1.05] tracking-tight text-ink">
          Haba na haba
          <br />
          hujaza kibaba
        </span>
        <span className="max-w-[75%] text-[clamp(10px,2.4cqw,13px)] leading-tight text-muted">
          Little by little fills the measure
        </span>
      </div>
    </div>
  );
}
