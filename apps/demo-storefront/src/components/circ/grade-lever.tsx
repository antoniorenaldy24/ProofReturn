"use client";

import { useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { CIRC_GRADES } from "@/lib/data";
import { cn } from "@/lib/utils";

/**
 * The grading lever — a machined detent control. Drag the needle through
 * grades A–D and the whole instrument re-computes; release and it clicks
 * into the nearest grade. Fully operable by keyboard.
 */
export function GradeLever({
  gradeIndex,
  onChange,
}: {
  gradeIndex: number;
  onChange: (index: number) => void;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [dragX, setDragX] = useState<number | null>(null);
  const reduced = useReducedMotion();

  const PADDING = 8; // percent inset for first/last detent
  const pos = (i: number) => PADDING + (i / (CIRC_GRADES.length - 1)) * (100 - PADDING * 2);

  const indexFromX = (clientX: number) => {
    const el = trackRef.current;
    if (!el) return gradeIndex;
    const r = el.getBoundingClientRect();
    const p = ((clientX - r.left) / r.width) * 100;
    const raw = ((p - PADDING) / (100 - PADDING * 2)) * (CIRC_GRADES.length - 1);
    return Math.max(0, Math.min(CIRC_GRADES.length - 1, Math.round(raw)));
  };
  const livePosFromX = (clientX: number) => {
    const el = trackRef.current;
    if (!el) return 50;
    const r = el.getBoundingClientRect();
    return Math.max(PADDING, Math.min(100 - PADDING, ((clientX - r.left) / r.width) * 100));
  };

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setDragX(livePosFromX(e.clientX));
    onChange(indexFromX(e.clientX));
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (dragX === null) return;
    setDragX(livePosFromX(e.clientX));
    const next = indexFromX(e.clientX);
    if (next !== gradeIndex) onChange(next);
  };
  const onPointerUp = () => setDragX(null);

  const onKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowRight" || e.key === "ArrowUp") {
      e.preventDefault();
      onChange(Math.min(CIRC_GRADES.length - 1, gradeIndex + 1));
    } else if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
      e.preventDefault();
      onChange(Math.max(0, gradeIndex - 1));
    } else if (e.key === "Home") {
      e.preventDefault();
      onChange(0);
    } else if (e.key === "End") {
      e.preventDefault();
      onChange(CIRC_GRADES.length - 1);
    }
  };

  const active = CIRC_GRADES[gradeIndex];
  const needleLeft = dragX ?? pos(gradeIndex);

  return (
    <div className="select-none">
      <div
        ref={trackRef}
        role="slider"
        tabIndex={0}
        aria-label="Condition grade selector — sets the refund tier"
        aria-valuemin={1}
        aria-valuemax={4}
        aria-valuenow={gradeIndex + 1}
        aria-valuetext={`Grade ${active.grade} — ${Math.round(active.rate * 100)}% refund`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onKeyDown={onKeyDown}
        data-cursor="drag"
        className="relative h-24 cursor-grab touch-pan-y outline-offset-4 active:cursor-grabbing"
      >
        {/* rail */}
        <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-ink/70" aria-hidden="true" />
        <div className="absolute inset-x-0 top-1/2 h-[7px] -translate-y-1/2 border-y border-ink/40" aria-hidden="true" />

        {/* detents */}
        {CIRC_GRADES.map((g, i) => (
          <button
            key={g.grade}
            onClick={() => onChange(i)}
            tabIndex={-1}
            aria-hidden="true"
            className="group absolute top-1/2 -translate-x-1/2 -translate-y-1/2 p-2"
            style={{ left: `${pos(i)}%` }}
          >
            <span
              className={cn(
                "block h-4 w-[3px] transition-colors",
                i === gradeIndex ? "bg-pr-green" : "bg-ink/60 group-hover:bg-ink",
              )}
            />
            <span
              className={cn(
                "mt-1 block font-ledger text-[10px] font-semibold uppercase tracking-[0.2em] transition-colors",
                i === gradeIndex ? "text-pr-green" : "text-ink-soft group-hover:text-ink",
              )}
            >
              {g.grade}
            </span>
            <span className="mt-0.5 block font-ledger text-[9px] tracking-[0.12em] text-ink-soft">
              {Math.round(g.rate * 100)}%
            </span>
          </button>
        ))}

        {/* needle */}
        <motion.div
          className="pointer-events-none absolute top-1/2 z-10 -translate-x-1/2 -translate-y-full"
          animate={{ left: `${needleLeft}%` }}
          transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 260, damping: 24 }}
        >
          <div className="relative flex flex-col items-center">
            <div className="h-14 w-[1.5px] bg-pr-green" aria-hidden="true" />
            <div
              className="h-0 w-0 border-x-[7px] border-t-[10px] border-x-transparent border-t-pr-green"
              aria-hidden="true"
            />
          </div>
        </motion.div>
      </div>
      <p className="mt-1 text-center font-ledger text-[8.5px] uppercase tracking-[0.24em] text-ink-soft">
        Drag the needle, tap a grade, or use arrow keys
      </p>
    </div>
  );
}
