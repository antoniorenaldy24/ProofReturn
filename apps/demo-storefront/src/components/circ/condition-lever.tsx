"use client";

import { useCallback, useRef } from "react";
import { motion } from "framer-motion";
import { CIRC_GRADES, GRADE_COLORS, PRODUCT, formatUSD } from "@/lib/data";
import { cn } from "@/lib/utils";

/**
 * ConditionLever — a snapping 4-detent instrument lever.
 * Pointer drag snaps to the nearest grade; arrow keys step.
 * The lever glows in the selected grade's ramp color.
 */
export function ConditionLever({
  idx,
  onChange,
}: {
  idx: number;
  onChange: (idx: number) => void;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);
  const color = GRADE_COLORS[idx];

  const idxFromClientX = useCallback((clientX: number) => {
    const el = trackRef.current;
    if (!el) return idx;
    const rect = el.getBoundingClientRect();
    const t = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    return Math.round(t * 3);
  }, [idx]);

  const onPointerDown = (e: React.PointerEvent) => {
    dragging.current = true;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    onChange(idxFromClientX(e.clientX));
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragging.current) return;
    onChange(idxFromClientX(e.clientX));
  };
  const stop = () => {
    dragging.current = false;
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight" || e.key === "ArrowUp") {
      e.preventDefault();
      onChange(Math.min(3, idx + 1));
    } else if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
      e.preventDefault();
      onChange(Math.max(0, idx - 1));
    } else if (e.key === "Home") {
      onChange(0);
    } else if (e.key === "End") {
      onChange(3);
    }
  };

  const pct = (idx / 3) * 100;

  return (
    <div className="select-none">
      <div className="mb-2 flex items-center justify-between font-tech text-[10px] uppercase tracking-[0.18em] text-faint">
        <span>Drag me — or use arrow keys</span>
        <span
          className="rounded-full px-2 py-0.5 font-semibold"
          style={{
            color,
            background: `color-mix(in srgb, ${color} 10%, transparent)`,
          }}
        >
          GRADE {CIRC_GRADES[idx].grade}
        </span>
      </div>
      <div
        ref={trackRef}
        role="slider"
        tabIndex={0}
        aria-label="Returned condition grade"
        aria-valuemin={0}
        aria-valuemax={3}
        aria-valuenow={idx}
        aria-valuetext={`Grade ${CIRC_GRADES[idx].grade} — ${CIRC_GRADES[idx].condition}`}
        data-cursor="drag"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={stop}
        onPointerCancel={stop}
        onKeyDown={onKeyDown}
        className="relative h-12 cursor-ew-resize touch-none overflow-hidden rounded-xl border border-line bg-panel-2"
      >
        {/* ramp fill — green to red across the track */}
        <div
          aria-hidden
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(90deg, rgba(14,159,110,0.12), rgba(199,134,10,0.10), rgba(238,108,43,0.10), rgba(224,49,49,0.12))",
          }}
        />
        {/* active fill */}
        <motion.div
          className="absolute inset-y-0 left-0"
          animate={{ width: `${pct}%`, background: `color-mix(in srgb, ${color} 20%, transparent)` }}
          transition={{ type: "spring", stiffness: 300, damping: 30 }}
        />
        {/* detent ticks */}
        {CIRC_GRADES.map((g, i) => (
          <span
            key={g.grade}
            aria-hidden
            className={cn(
              "absolute top-0 h-full w-px -translate-x-1/2 transition-colors",
              i <= idx ? "" : "bg-line",
            )}
            style={{
              left: `${(i / 3) * 100}%`,
              background: i <= idx ? `color-mix(in srgb, ${GRADE_COLORS[i]} 55%, transparent)` : undefined,
            }}
          />
        ))}
        {/* knob */}
        <motion.div
          className="absolute top-1/2 grid h-9 w-9 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full border-2 bg-panel"
          animate={{ left: `${pct}%`, borderColor: color }}
          transition={{ type: "spring", stiffness: 320, damping: 26 }}
          style={{
            boxShadow: `0 0 0 4px color-mix(in srgb, ${color} 14%, transparent), 0 3px 8px rgba(21,23,26,0.18)`,
          }}
        >
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: color, animation: "led-pulse 1.8s ease-in-out infinite" }}
          />
        </motion.div>
      </div>
      <div className="mt-1.5 flex justify-between">
        {CIRC_GRADES.map((g, i) => (
          <button
            key={g.grade}
            type="button"
            onClick={() => onChange(i)}
            className={cn(
              "w-9 rounded-md py-0.5 font-tech text-[11px] font-semibold tracking-[0.1em] transition-all",
              i === idx ? "" : "text-faint hover:text-dim",
            )}
            style={
              i === idx
                ? {
                    color: GRADE_COLORS[i],
                    background: `color-mix(in srgb, ${GRADE_COLORS[i]} 10%, transparent)`,
                  }
                : undefined
            }
            aria-pressed={i === idx}
          >
            {g.grade}
          </button>
        ))}
      </div>
      <p className="mt-1 text-right font-tech text-[10px] tabular-nums text-faint">
        exact refund = rate × MSRP · {formatUSD(PRODUCT.msrp ?? 380)}
      </p>
    </div>
  );
}
