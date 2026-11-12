"use client";

import { useEffect, useRef } from "react";
import { motion, useReducedMotion } from "framer-motion";
import gsap from "gsap";
import { GuillocheField } from "@/components/ornament/guilloche-field";
import { EngravedHeadphones } from "@/components/product/engraved-headphones";
import { CornerMark, MicrotextStrip, Rule, Seal } from "@/components/ornament/ornaments";
import { PRODUCT, spellDollars } from "@/lib/data";

/** Modulated oval — the portrait frame of the note. */
function ovalRosePath(cx: number, cy: number, rx: number, ry: number, a: number, n: number, phase = 0): string {
  const steps = 180;
  const pts: string[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = (i / steps) * Math.PI * 2;
    const m = 1 + a * Math.sin(n * t + phase);
    pts.push(`${(cx + rx * m * Math.cos(t)).toFixed(1)} ${(cy + ry * m * Math.sin(t)).toFixed(1)}`);
  }
  return `M ${pts[0]} L ${pts.slice(1).join(" L ")} Z`;
}

function Denomination({ className }: { className?: string }) {
  return (
    <div
      className={`flex flex-col items-center border-[1.5px] border-ink bg-sheet px-2.5 py-1 leading-none shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--ink)_35%,transparent)] ${className ?? ""}`}
      aria-label={`Denomination ${PRODUCT.currencySymbol}${PRODUCT.msrp.toFixed(2)}`}
    >
      <span className="engraved text-xl font-bold text-ink sm:text-3xl">
        {PRODUCT.currencySymbol}
        {PRODUCT.msrp}
      </span>
      <span className="mt-0.5 hidden font-ledger text-[7px] uppercase tracking-[0.3em] text-ink-soft sm:block">
        {PRODUCT.minorUnits.toLocaleString()} units
      </span>
    </div>
  );
}

/**
 * THE NOTE — the storefront opens as a banknote for headphones:
 * masthead, serials, denomination corners, engraved portrait,
 * spelled value, and the refund promise printed on its face.
 */
export function NoteHero() {
  const reduced = useReducedMotion();
  const noteRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (reduced) return;
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
      tl.fromTo("[data-hero-eyebrow]", { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.6 })
        .fromTo(
          "[data-hero-masthead]",
          { opacity: 0, y: 34, clipPath: "inset(0 0 100% 0)" },
          { opacity: 1, y: 0, clipPath: "inset(0 0 -10% 0)", duration: 1.0 },
          "-=0.3",
        )
        .fromTo("[data-hero-serial]", { opacity: 0 }, { opacity: 1, duration: 0.5, stagger: 0.12 }, "-=0.4")
        .fromTo(
          "[data-hero-portrait]",
          { opacity: 0, scale: 0.965 },
          { opacity: 1, scale: 1, duration: 0.9 },
          "-=0.35",
        )
        .fromTo("[data-hero-bottom]", { opacity: 0, y: 16 }, { opacity: 1, y: 0, duration: 0.7 }, "-=0.45")
        .fromTo("[data-hero-counter]", { opacity: 0, y: 18 }, { opacity: 1, y: 0, duration: 0.7 }, "-=0.4");
    }, rootRef);
    return () => ctx.revert();
  }, [reduced]);

  const onNotePointer = (e: React.PointerEvent) => {
    if (reduced || e.pointerType !== "mouse") return;
    const el = noteRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const nx = (e.clientX - r.left) / r.width - 0.5;
    const ny = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `perspective(1200px) rotateX(${(-ny * 2.2).toFixed(2)}deg) rotateY(${(nx * 2.8).toFixed(2)}deg)`;
  };
  const resetNote = () => {
    const el = noteRef.current;
    if (el) el.style.transform = "perspective(1200px) rotateX(0deg) rotateY(0deg)";
  };

  return (
    <section
      ref={rootRef}
      className="relative flex min-h-svh flex-col items-center justify-center overflow-hidden px-3 pb-14 pt-20 sm:px-6"
      aria-label="ProofReturn demonstration note"
    >
      <GuillocheField className="absolute inset-0 h-full w-full" />

      <div
        data-hero-note
        ref={noteRef}
        onPointerMove={onNotePointer}
        onPointerLeave={resetNote}
        className="relative z-10 w-full max-w-5xl border-[1.5px] border-ink bg-sheet/95 p-1 shadow-[0_24px_60px_-30px_rgba(34,29,18,0.5)] transition-transform duration-300 ease-out will-change-transform"
        data-cursor="read"
      >
        {/* inner frame */}
        <div className="relative border border-ink/70 px-4 pb-5 pt-6 sm:px-10 sm:pb-7 sm:pt-8">
          <CornerMark className="absolute left-1.5 top-1.5" size={20} />
          <CornerMark className="absolute right-1.5 top-1.5 rotate-90" size={20} />
          <CornerMark className="absolute bottom-1.5 right-1.5 rotate-180" size={20} />
          <CornerMark className="absolute bottom-1.5 left-1.5 -rotate-90" size={20} />

          <div className="pointer-events-none absolute inset-x-2 top-1 hidden sm:block">
            <MicrotextStrip text="PROOFRETURN · DEMONSTRATION NOTE · SIMULATED DATA · NOT LEGAL ADVICE" repeat={28} />
          </div>

          {/* ——— Masthead ——— */}
          <div className="mt-3 text-center sm:mt-4">
            <p
              data-hero-eyebrow
              className="font-ledger text-[9px] font-semibold uppercase tracking-[0.4em] text-pr-red sm:text-[10px]"
            >
              Demonstration note · front-end simulation · no real payments
            </p>
            <h1
              data-hero-masthead
              className="engraved mt-2 text-[clamp(1.95rem,9vw,7rem)] font-semibold uppercase leading-[0.95] tracking-tight text-ink"
            >
              Proof<span className="text-pr-green">Return</span>
            </h1>
            <p className="engraved-text mt-2 text-sm italic text-ink-soft sm:text-base">
              The storefront that prints its fine print in intaglio
            </p>
          </div>

          <Rule draw className="mt-4" />

          {/* ——— Serial row ——— */}
          <div className="mt-2 flex items-center justify-between font-ledger text-[10px] font-semibold tracking-[0.22em] text-pr-red sm:text-[11px]">
            <span data-hero-serial>K 0380 2026 A</span>
            <span data-hero-serial className="hidden sm:inline">
              {PRODUCT.minorUnits.toLocaleString()} MINOR UNITS
            </span>
            <span data-hero-serial>PR 88 04 DEMO</span>
          </div>

          {/* ——— Portrait ——— */}
          <div className="relative mx-auto mt-3 w-full max-w-[430px]" data-parallax="26">
            <Denomination className="absolute -left-1 top-3 z-20 sm:left-2" />
            <Denomination className="absolute -right-1 top-3 z-20 sm:right-2" />

            <div
              data-hero-portrait
              className="relative aspect-[560/610] w-full"
              role="img"
              aria-label="Engraved portrait of the Auralis N°1 headphones, the object this note certifies"
            >
              <svg
                viewBox="0 0 560 610"
                className="absolute inset-0 h-full w-full"
                aria-hidden="true"
                focusable="false"
              >
                <g fill="none" stroke="var(--ink)" strokeWidth="0.5" opacity="0.55">
                  <ellipse cx="280" cy="305" rx="238" ry="272" />
                  <ellipse cx="280" cy="305" rx="230" ry="264" />
                  <path d={ovalRosePath(280, 305, 222, 254, 0.035, 14)} />
                  <path d={ovalRosePath(280, 305, 214, 246, 0.03, 18)} />
                </g>
              </svg>
              <EngravedHeadphones className="absolute inset-0 m-auto h-[86%] w-[86%]" />
              <span
                aria-hidden="true"
                className="engraved pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 -rotate-[16deg] text-[clamp(3rem,11vw,7rem)] font-black uppercase tracking-[0.18em] text-transparent"
                style={{ WebkitTextStroke: "1.5px rgba(34,29,18,0.28)" }}
              >
                Specimen
              </span>
            </div>
          </div>

          {/* ——— Bottom of the note ——— */}
          <div data-hero-bottom className="relative mt-1">
            <Rule draw thick={1.5} />
            <div className="flex flex-col items-center gap-3 pt-3 sm:grid sm:grid-cols-[auto_1fr_auto] sm:items-center sm:gap-6 sm:pt-4">
              <div className="hidden flex-col items-center gap-1 sm:flex">
                <Seal size={92} center="A" sub="GRADE" />
              </div>
              <span className="font-ledger text-[8px] uppercase tracking-[0.2em] text-ink-soft sm:hidden">
                Seal · Grade A · Certified Open Box
              </span>

              <div className="text-center">
                <p className="engraved text-base font-semibold uppercase leading-tight tracking-[0.06em] text-ink sm:text-2xl">
                  {spellDollars(PRODUCT.msrp)}
                </p>
                <p className="mx-auto mt-2 max-w-[34ch] font-ledger text-[9px] uppercase leading-relaxed tracking-[0.14em] text-ink-soft sm:text-[10px]">
                  Payable to the bearer upon return —{" "}
                  <span className="text-pr-green">grade A restores 100% of this note</span>
                </p>
              </div>

              <div className="text-center font-ledger text-[8px] uppercase leading-[1.9] tracking-[0.16em] text-ink-soft sm:text-right sm:text-[9px]">
                <p>Plate 01</p>
                <p>{PRODUCT.sku}</p>
                <p>PP-2026-0038-A</p>
              </div>
            </div>
          </div>

          <div className="pointer-events-none absolute inset-x-2 bottom-1 hidden sm:block">
            <MicrotextStrip text="CONDITION PASSPORT · GRADE A · B · C · D · THE CURVE IS THE CONTRACT" repeat={30} />
          </div>
        </div>
      </div>

      {/* ——— The counter (below the note) ——— */}
      <div data-hero-counter className="relative z-10 mt-8 flex max-w-3xl flex-col items-center px-4 text-center">
        <p className="engraved-text max-w-[46ch] text-base italic leading-relaxed text-ink-soft sm:text-lg">
          Every store shows you the price. This one prints the money-back curve on its face —{" "}
          <span className="text-ink not-italic">before</span> you buy.
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-4">
          <a
            href="#object"
            data-cursor="open"
            className="btn-engraved btn-engraved-solid"
          >
            Inspect the object — Plate I
          </a>
          <a href="#curve" data-cursor="open" className="btn-engraved">
            Read the refund curve — Plate II
          </a>
        </div>
        <p className="mt-5 flex items-center gap-3 font-ledger text-[9px] uppercase tracking-[0.3em] text-ink-soft">
          <span className="h-px w-10 bg-ink/40" aria-hidden="true" />
          Turn the page
          <span className="h-px w-10 bg-ink/40" aria-hidden="true" />
        </p>
        {!reduced && (
          <motion.span
            aria-hidden="true"
            className="mt-2 block h-8 w-px bg-pr-green"
            animate={{ scaleY: [1, 0.4, 1], opacity: [1, 0.4, 1] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
            style={{ transformOrigin: "top" }}
          />
        )}
      </div>
    </section>
  );
}
