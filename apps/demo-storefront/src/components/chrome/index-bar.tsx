"use client";

import { useEffect, useState } from "react";
import { useLedger } from "@/lib/store";
import { cn } from "@/lib/utils";

const INDEX = [
  { id: "object", numeral: "I", label: "The Object" },
  { id: "curve", numeral: "II", label: "The Curve" },
  { id: "passport", numeral: "III", label: "The Passport" },
  { id: "counting-house", numeral: "IV", label: "The Counting House" },
];

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ block: "start" });
}

/**
 * The press bar — ProofReturn's fixed masthead, plate index, and
 * a live ledger counter that jumps straight to the Counting House.
 */
export function IndexBar() {
  const qty = useLedger((s) => s.qty);
  const [active, setActive] = useState<string>("");
  const [lifted, setLifted] = useState(false);

  useEffect(() => {
    const onScroll = () => setLifted(window.scrollY > 80);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });

    const sections = INDEX.map((i) => document.getElementById(i.id)).filter(
      (el): el is HTMLElement => !!el,
    );
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) setActive(e.target.id);
        });
      },
      { rootMargin: "-40% 0px -55% 0px" },
    );
    sections.forEach((s) => io.observe(s));
    return () => {
      window.removeEventListener("scroll", onScroll);
      io.disconnect();
    };
  }, []);

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-[80] border-b border-ink/60 bg-paper/95 backdrop-blur-[2px] transition-shadow duration-300",
        lifted && "shadow-[0_1px_0_var(--ink),0_10px_24px_-18px_rgba(34,29,18,0.55)]",
      )}
    >
      <div className="mx-auto flex h-12 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <button
          onClick={() => window.scrollTo({ top: 0 })}
          className="flex items-center gap-2.5"
          aria-label="Back to the top of the note"
        >
          <span className="block h-2.5 w-2.5 rounded-full border border-ink bg-pr-green" aria-hidden="true" />
          <span className="font-ledger text-[11px] font-semibold uppercase tracking-[0.28em] text-ink">
            ProofReturn
          </span>
          <span className="hidden font-ledger text-[9px] uppercase tracking-[0.22em] text-ink-soft sm:inline">
            demo · specimen
          </span>
        </button>

        <nav aria-label="Plate index" className="hidden items-center gap-5 md:flex">
          {INDEX.map((item) => (
            <button
              key={item.id}
              onClick={() => scrollToId(item.id)}
              aria-current={active === item.id ? "true" : undefined}
              className={cn(
                "group flex items-baseline gap-1.5 whitespace-nowrap font-ledger text-[10px] uppercase tracking-[0.2em] transition-colors",
                active === item.id ? "text-pr-green" : "text-ink-soft hover:text-ink",
              )}
            >
              <span className="font-semibold">{item.numeral}</span>
              <span className="hidden xl:inline">{item.label}</span>
              <span
                aria-hidden="true"
                className={cn(
                  "block h-px w-0 bg-pr-green transition-all duration-300",
                  active === item.id ? "w-full" : "group-hover:w-3",
                )}
              />
            </button>
          ))}
        </nav>

        <button
          onClick={() => scrollToId("counting-house")}
          data-cursor="open"
          className="flex items-center gap-2 border border-ink/70 px-3 py-1.5 font-ledger text-[10px] font-semibold uppercase tracking-[0.2em] text-ink transition-colors hover:border-pr-green hover:text-pr-green"
          aria-live="polite"
        >
          <span>Ledger</span>
          <span className="flex h-4 min-w-4 items-center justify-center border border-pr-red px-1 text-[9px] text-pr-red">
            {qty}
          </span>
        </button>
      </div>
      <div aria-hidden="true" className="h-[3px] w-full border-t border-ink/25" />
    </header>
  );
}
