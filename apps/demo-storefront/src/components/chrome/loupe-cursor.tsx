"use client";

import { useEffect, useRef } from "react";

/**
 * The loupe — a printed ring that follows the pointer (fine pointers only,
 * enforced by CSS so no state is needed), enlarging and announcing its verb
 * over anything marked data-cursor="…". The native cursor is kept: the loupe
 * is an instrument, not a replacement.
 */
export function LoupeCursor() {
  const ref = useRef<HTMLDivElement>(null);
  const labelRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const fine = window.matchMedia("(pointer: fine)").matches;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!fine || reduced) return;

    let x = -100;
    let y = -100;
    let tx = -100;
    let ty = -100;
    let raf = 0;
    let started = false;

    const ring = ref.current;
    const label = labelRef.current;

    const tick = () => {
      x += (tx - x) * 0.22;
      y += (ty - y) * 0.22;
      if (ring) ring.style.transform = `translate(${x}px, ${y}px) translate(-50%, -50%)`;
      raf = requestAnimationFrame(tick);
    };

    const onMove = (e: PointerEvent) => {
      tx = e.clientX;
      ty = e.clientY;
      if (!started) {
        started = true;
        x = tx;
        y = ty;
        if (ring) ring.style.opacity = "1";
      }
      const el = (e.target as HTMLElement)?.closest?.("[data-cursor]") as HTMLElement | null;
      if (ring) ring.dataset.mode = el?.dataset.cursor ?? "";
      if (label) label.textContent = el?.dataset.cursor ?? "";
    };
    const onLeave = () => {
      if (ring) ring.style.opacity = "0";
      started = false;
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onMove);
      document.documentElement.removeEventListener("pointerleave", onLeave);
    };
  }, []);

  // Visibility is delegated to CSS: fine pointers only, never under reduced motion.
  return (
    <div
      ref={ref}
      aria-hidden="true"
      className="loupe loupe-root pointer-events-none fixed left-0 top-0 z-[90] opacity-0 transition-opacity duration-300"
      style={{ mixBlendMode: "multiply" }}
    >
      <div className="loupe-ring flex items-center justify-center rounded-full">
        <span className="block h-[3px] w-[3px] rounded-full" />
      </div>
      <span
        ref={labelRef}
        className="mt-1.5 block text-center font-ledger text-[8px] font-semibold uppercase tracking-[0.28em] text-ink"
        style={{ width: 34 }}
      />
    </div>
  );
}
