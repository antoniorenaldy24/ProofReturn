"use client";

import { useEffect, useState } from "react";
import { motion, useScroll, useSpring } from "framer-motion";
import { Clock, ShoppingCart } from "lucide-react";
import { SECTIONS } from "@/lib/data";
import { useLedger } from "@/lib/store";
import { cn } from "@/lib/utils";

/** Ticking lab clock — the page is alive. */
function LabClock() {
  const [time, setTime] = useState<string | null>(null);
  useEffect(() => {
    const fmt = () =>
      new Date().toLocaleTimeString("en-GB", { hour12: false });
    setTime(fmt());
    const t = window.setInterval(() => setTime(fmt()), 1000);
    return () => window.clearInterval(t);
  }, []);
  return (
    <span className="hidden items-center gap-1.5 font-tech text-[10px] font-medium tabular-nums tracking-[0.18em] text-faint md:flex">
      <Clock className="h-3 w-3" strokeWidth={1.5} />
      {time ?? "--:--:--"}
    </span>
  );
}

export function Nav() {
  const qty = useLedger((s) => s.qty);
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 140, damping: 28, mass: 0.4 });
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

  return (
    <header className="sticky top-[93px] inset-x-0 z-40">
      <div className="h-[3px] w-full bg-line/40">
        <motion.div
          style={{ scaleX }}
          className="h-full origin-left bg-gradient-to-r from-sig via-indigo to-teal"
        />
      </div>
      <nav
        aria-label="Primary"
        className="border-b border-line bg-paper/85 backdrop-blur-md"
      >
        <div className="mx-auto flex h-14 max-w-[1500px] items-center justify-between gap-4 px-4 sm:px-6">
          <a
            href="#specimen"
            className="group flex items-center gap-3"
            aria-label="ProofReturn — back to top"
          >
            <span className="relative grid h-7 w-7 place-items-center rounded-lg border border-sig/60">
              <span className="h-2.5 w-2.5 rounded-[3px] bg-sig transition-transform duration-300 group-hover:rotate-45" />
              <span className="absolute inset-[3px] rounded-[4px] border border-sig/30" />
            </span>
            <span className="font-display text-[15px] font-semibold tracking-tight text-ink">
              ProofReturn
            </span>
            <span className="hidden rounded-full border border-line px-2 py-0.5 font-tech text-[9px] uppercase tracking-[0.2em] text-faint md:inline-block">
              Return Lab
            </span>
          </a>

          <div className="hidden items-center gap-1 lg:flex">
            {SECTIONS.map((s) => {
              const isActive = active === s.id;
              return (
                <a
                  key={s.id}
                  href={`#${s.id}`}
                  className={cn(
                    "group relative flex items-baseline gap-1.5 rounded-full px-3 py-2 font-tech text-[11px] font-medium uppercase tracking-[0.16em] transition-colors",
                    isActive ? "text-ink" : "text-dim hover:text-ink",
                  )}
                >
                  <span
                    className="text-[9px] transition-colors"
                    style={{ color: isActive ? s.hue : undefined }}
                  >
                    {s.index}
                  </span>
                  {s.code}
                  {isActive ? (
                    <motion.span
                      layoutId="nav-pill"
                      className="absolute inset-0 -z-10 rounded-full"
                      style={{
                        background: `color-mix(in srgb, ${s.hue} 9%, transparent)`,
                        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${s.hue} 28%, transparent)`,
                      }}
                      transition={{ type: "spring", stiffness: 320, damping: 30 }}
                    />
                  ) : null}
                </a>
              );
            })}
          </div>

          <div className="flex items-center gap-3">
            <LabClock />
            <span className="hidden rounded-full border border-sig/40 bg-sig/[0.06] px-2.5 py-1 font-tech text-[9px] font-semibold uppercase tracking-[0.2em] text-sig sm:inline-block">
              Demo
            </span>
            <a
              href="#checkout"
              className={cn(
                "relative grid h-9 w-9 place-items-center rounded-full border transition-all duration-300",
                qty > 0
                  ? "border-sig/60 bg-sig/[0.07] text-sig"
                  : "border-line text-dim hover:border-faint hover:text-ink",
              )}
              aria-label={`Open checkout — ${qty} unit${qty === 1 ? "" : "s"} in ledger`}
            >
              <ShoppingCart className="h-4 w-4" strokeWidth={1.5} />
              {qty > 0 ? (
                <motion.span
                  key={qty}
                  initial={{ scale: 0.4, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ type: "spring", stiffness: 500, damping: 18 }}
                  className="absolute -top-1.5 -right-1.5 grid h-4.5 min-w-4.5 place-items-center rounded-full bg-sig px-1 font-tech text-[10px] font-bold text-white shadow-[0_4px_12px_-2px_rgba(214,58,0,0.5)]"
                >
                  {qty}
                </motion.span>
              ) : null}
            </a>
          </div>
        </div>
      </nav>
    </header>
  );
}
