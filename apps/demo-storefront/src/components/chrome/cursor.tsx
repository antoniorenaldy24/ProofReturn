"use client";

import { useEffect, useState } from "react";
import { motion, useMotionValue, useSpring } from "framer-motion";

type CursorMode = "idle" | "drag" | "run" | "open" | "inspect" | "stop";

const LABELS: Record<CursorMode, string | null> = {
  idle: null,
  drag: "DRAG",
  run: "RUN",
  open: "OPEN",
  inspect: "INSPECT",
  stop: "STOP",
};

/**
 * Crosshair cursor — instrument-style pointer for the lab.
 * Desktop (fine pointer) only; activates on first move, never during SSR.
 */
export function Cursor() {
  const [enabled, setEnabled] = useState(false);
  const [mode, setMode] = useState<CursorMode>("idle");

  const x = useMotionValue(-100);
  const y = useMotionValue(-100);
  const rx = useSpring(x, { stiffness: 520, damping: 40, mass: 0.5 });
  const ry = useSpring(y, { stiffness: 520, damping: 40, mass: 0.5 });

  useEffect(() => {
    const fine = window.matchMedia("(pointer: fine)").matches;
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!fine || calm) return;

    let active = false;
    const move = (e: MouseEvent) => {
      if (!active) {
        active = true;
        setEnabled(true);
      }
      x.set(e.clientX);
      y.set(e.clientY);
      const target = e.target as HTMLElement | null;
      const hit = target?.closest?.("[data-cursor]");
      setMode((hit?.getAttribute("data-cursor") as CursorMode | null) ?? "idle");
    };
    window.addEventListener("mousemove", move, { passive: true });
    return () => window.removeEventListener("mousemove", move);
  }, [x, y]);

  if (!enabled) return null;

  const label = LABELS[mode];
  const isActive = mode !== "idle";

  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-[100]">
      {/* crosshair */}
      <motion.div style={{ x: rx, y: ry }} className="absolute top-0 left-0">
        <div className="relative -translate-x-1/2 -translate-y-1/2">
          <motion.span
            animate={{ width: isActive ? 0 : 22, opacity: isActive ? 0 : 1 }}
            transition={{ duration: 0.18 }}
            className="absolute top-1/2 left-1/2 h-px -translate-y-1/2 bg-ink/70"
          />
          <motion.span
            animate={{ height: isActive ? 0 : 22, opacity: isActive ? 0 : 1 }}
            transition={{ duration: 0.18 }}
            className="absolute top-1/2 left-1/2 w-px -translate-x-1/2 bg-ink/70"
          />
          {/* reticle */}
          <motion.div
            animate={{
              width: isActive ? 44 : 8,
              height: isActive ? 44 : 8,
              opacity: isActive ? 1 : 0.9,
              rotate: isActive ? 90 : 0,
            }}
            transition={{ type: "spring", stiffness: 380, damping: 26 }}
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
          >
            {isActive ? (
              <>
                <span className="absolute top-0 left-0 h-2 w-2 border-t border-l border-sig" />
                <span className="absolute top-0 right-0 h-2 w-2 border-t border-r border-sig" />
                <span className="absolute bottom-0 left-0 h-2 w-2 border-b border-l border-sig" />
                <span className="absolute bottom-0 right-0 h-2 w-2 border-b border-r border-sig" />
              </>
            ) : (
              <span className="absolute inset-0 rounded-full border border-ink/50" />
            )}
          </motion.div>
          <span className="absolute top-1/2 left-1/2 h-[3px] w-[3px] -translate-x-1/2 -translate-y-1/2 bg-sig" />
        </div>
      </motion.div>
      {/* mode label */}
      <motion.div style={{ x: rx, y: ry }} className="absolute top-0 left-0">
        <motion.span
          animate={{ opacity: label ? 1 : 0, y: label ? 0 : 6 }}
          transition={{ duration: 0.16 }}
          className="absolute top-6 left-6 border border-sig/60 bg-paper/95 px-1.5 py-0.5 font-tech text-[9px] font-semibold tracking-[0.24em] text-sig"
        >
          {label}
        </motion.span>
      </motion.div>
    </div>
  );
}
