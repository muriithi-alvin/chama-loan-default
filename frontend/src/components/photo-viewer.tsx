"use client";

import { Maximize2, Minus, Plus, RotateCcw } from "lucide-react";
import { useState } from "react";
import { TransformComponent, TransformWrapper } from "react-zoom-pan-pinch";

/** A ledger photo you can zoom and pan with the mouse, a finger or the buttons. */
export function PhotoViewer({ src, alt, className = "" }: { src: string; alt: string; className?: string }) {
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
  const button = "flex h-11 w-11 items-center justify-center rounded-full bg-white text-ink shadow-[0_2px_8px_rgba(20,33,61,.18)] hover:bg-ice";
  return (
    <div className={`relative overflow-hidden rounded-card border border-line bg-ink/[0.04] ${className}`}>
      {state === "failed" ? (
        <p role="alert" className="flex h-full min-h-[240px] items-center justify-center p-6 text-center text-[16px] text-muted">
          The photo could not be loaded. Reload the page to try again.
        </p>
      ) : (
        <TransformWrapper minScale={1} maxScale={6} wheel={{ step: 0.15 }} doubleClick={{ mode: "zoomIn" }}>
          {({ zoomIn, zoomOut, resetTransform, centerView }) => (
            <>
              <div className="absolute right-3 top-3 z-10 flex gap-2" role="group" aria-label="Photo zoom">
                <button type="button" className={button} onClick={() => zoomIn()} aria-label="Zoom in"><Plus aria-hidden="true" size={20} /></button>
                <button type="button" className={button} onClick={() => zoomOut()} aria-label="Zoom out"><Minus aria-hidden="true" size={20} /></button>
                <button type="button" className={button} onClick={() => centerView(1)} aria-label="Fit the page"><Maximize2 aria-hidden="true" size={18} /></button>
                <button type="button" className={button} onClick={() => resetTransform()} aria-label="Reset"><RotateCcw aria-hidden="true" size={18} /></button>
              </div>
              <TransformComponent wrapperClass="!h-full !w-full" contentClass="!h-full !w-full">
                {/* eslint-disable-next-line @next/next/no-img-element -- private photo served by the API */}
                <img src={src} alt={alt} draggable={false} onLoad={() => setState("ready")} onError={() => setState("failed")}
                  className={`h-full w-full object-contain transition-opacity duration-300 ${state === "ready" ? "opacity-100" : "opacity-0"}`} />
              </TransformComponent>
            </>
          )}
        </TransformWrapper>
      )}
      {state === "loading" && (
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span className="bead bead-cobalt bead-pulse" style={{ width: 18, height: 18 }} />
        </div>
      )}
    </div>
  );
}
