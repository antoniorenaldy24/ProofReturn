"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Check, MousePointer2 } from "lucide-react";
import { SECTIONS } from "@/lib/data";
import { useLedger } from "@/lib/store";
import { cn } from "@/lib/utils";

/**
 * Journey — human-first wayfinding over the lab chrome.
 * Strip: horizontal "how this works" cards under the hero.
 * Rail: fixed scroll-spy dots on the right (desktop).
 */

function useJourneyDone() {
  const qty = useLedger((s) => s.qty);
  const passportVerified = useLedger((s) => s.passportVerified);
  const lastOrder = useLedger((s) => s.lastOrder);
  return [
    qty > 0, // 01 — met the object, added to order
    true, // 02 — the curve is always on view (no interaction gate)
    passportVerified, // 03 — rig run
    Boolean(lastOrder), // 04 — sandbox order sealed
  ];
}

function useActiveSection() {
  const [active, setActive] = useState<string>("specimen");
  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) setActive(e.target.id);
        }
      },
      { rootMargin: "-38% 0px -55% 0px" },
    );
    for (const s of SECTIONS) {
      const el = document.getElementById(s.id);
      if (el) obs.observe(el);
    }
    return () => obs.disconnect();
  }, []);
  return active;
}

/* ————————————————— horizontal strip ————————————————— */

export function JourneyStrip() {
  const done = useJourneyDone();
  const [active] = useActiveSection();

  return (
    <div className="border-t border-line bg-panel/60 py-8 backdrop-blur-sm sm:py-10">
      <div className="mx-auto max-w-[1500px] px-4 sm:px-6">
        <div className="flex items-center gap-2.5">
          <MousePointer2 className="h-3.5 w-3.5 text-faint" strokeWidth={1.5} />
          <span className="font-tech text-[10px] font-semibold uppercase tracking-[0.24em] text-faint">
            How this store works — four steps, top to bottom
          </span>
        </div>

        <ol className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {SECTIONS.map((s, i) => {
            const isDone = done[i];
            const isActive = active === s.id;
            return (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  className="group flex h-full flex-col gap-2.5 rounded-2xl border bg-panel p-4 transition-all duration-300 hover:-translate-y-0.5"
                  style={{
                    borderColor: isActive
                      ? `color-mix(in srgb, ${s.hue} 45%, var(--line))`
                      : "var(--line)",
                    boxShadow: isActive
                      ? `0 12px 32px -14px color-mix(in srgb, ${s.hue} 40%, transparent)`
                      : undefined,
                  }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2.5">
                      <motion.span
                        animate={
                          isActive
                            ? { scale: [1, 1.14, 1] }
                            : { scale: 1 }
                        }
                        transition={
                          isActive ? { duration: 1.8, repeat: Infinity } : { duration: 0.2 }
                        }
                        className="grid h-7 w-7 place-items-center rounded-full font-tech text-[11px] font-bold text-white"
                        style={{ background: s.hue }}
                      >
                        {isDone ? <Check className="h-3.5 w-3.5" strokeWidth={3} /> : s.index}
                      </motion.span>
                      <span className="font-display text-[15px] font-semibold tracking-tight text-ink">
                        {s.human}
                      </span>
                    </span>
                    <span
                      className="font-tech text-[9px] uppercase tracking-[0.18em]"
                      style={{ color: s.hue, opacity: isActive ? 1 : 0.55 }}
                    >
                      {s.code}
                    </span>
                  </div>
                  <p className="font-display text-[12.5px] leading-relaxed text-dim">
                    {s.action}
                  </p>
                </a>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

/* ————————————————— fixed side rail (desktop) ————————————————— */

export function JourneyRail() {
  const done = useJourneyDone();
  const active = useActiveSection();

  return (
    <nav
      aria-label="Section progress"
      className="fixed top-1/2 right-5 z-40 hidden -translate-y-1/2 xl:block"
    >
      <ol className="relative flex flex-col items-end gap-4">
        {/* connecting line */}
        <span
          aria-hidden
          className="absolute top-2 right-[9px] bottom-2 w-px bg-line"
        />
        {SECTIONS.map((s, i) => {
          const isActive = active === s.id;
          const isDone = done[i];
          return (
            <li key={s.id} className="relative">
              <a
                href={`#${s.id}`}
                aria-label={`Step ${s.index} — ${s.human}${isDone ? " (done)" : ""}`}
                aria-current={isActive ? "true" : undefined}
                className="group flex items-center gap-3"
              >
                {/* hover-only label — never a persistent floating pill */}
                <span
                  className="pointer-events-none translate-x-2 rounded-full border border-line bg-panel/95 px-3 py-1 font-tech text-[10px] font-semibold uppercase tracking-[0.16em] text-ink opacity-0 shadow-[0_6px_20px_-8px_rgba(21,23,26,0.25)] backdrop-blur-sm transition-all duration-200 group-hover:translate-x-0 group-hover:opacity-100"
                >
                  {isDone ? "✓ " : ""}{s.human}
                </span>
                <span
                  className={cn(
                    "relative grid place-items-center rounded-full border-2 transition-all duration-300",
                    isActive ? "h-[18px] w-[18px]" : "h-3 w-3 group-hover:h-4 group-hover:w-4",
                  )}
                  style={{
                    borderColor: s.hue,
                    background: isDone || isActive ? s.hue : "var(--panel)",
                    boxShadow: isActive
                      ? `0 0 0 5px color-mix(in srgb, ${s.hue} 18%, transparent)`
                      : undefined,
                  }}
                >
                  {isDone && !isActive ? (
                    <Check className="h-2 w-2 text-white" strokeWidth={4} />
                  ) : null}
                </span>
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
