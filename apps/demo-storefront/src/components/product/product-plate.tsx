"use client";

import { useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { PlateFrame } from "@/components/ornament/plate-frame";
import { Stamp } from "@/components/ornament/ornaments";
import { EngravedHeadphones } from "@/components/product/engraved-headphones";
import { CALLOUTS, formatUSD, PRODUCT } from "@/lib/data";
import { useLedger } from "@/lib/store";
import { cn } from "@/lib/utils";

function CalloutCard({ activeId, onClose }: { activeId: string; onClose: () => void }) {
  const c = CALLOUTS.find((x) => x.id === activeId);
  if (!c) return null;
  const flipX = c.x > 280;
  const flipY = c.y > 330;
  return (
    <motion.div
      key={c.id}
      initial={{ opacity: 0, y: flipY ? 10 : -10, rotate: flipX ? -1 : 1 }}
      animate={{ opacity: 1, y: 0, rotate: 0 }}
      exit={{ opacity: 0, scale: 0.97 }}
      transition={{ type: "spring", stiffness: 380, damping: 28 }}
      className="absolute z-30 w-64 border border-ink bg-sheet p-4 shadow-[4px_4px_0_rgba(34,29,18,0.22)]"
      style={{
        left: `${(c.x / 560) * 100}%`,
        top: `${(c.y / 610) * 100}%`,
        transform: `translate(${flipX ? "calc(-100% - 18px)" : "18px"}, ${flipY ? "calc(-100% + 10px)" : "-10px"})`,
      }}
      role="status"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="font-ledger text-[9px] font-semibold uppercase tracking-[0.24em] text-pr-green">
          Point {c.marker} — {c.zone}
        </p>
        <button
          onClick={onClose}
          aria-label="Close inspection record"
          className="font-ledger text-[10px] text-ink-soft hover:text-pr-red"
        >
          ✕
        </button>
      </div>
      <p className="mt-2 font-ledger text-[11px] leading-relaxed text-ink">{c.note}</p>
      <div className="mt-3 flex items-center justify-between border-t border-dashed border-ink/40 pt-2 font-ledger text-[8.5px] uppercase tracking-[0.18em] text-ink-soft">
        <span>{c.inspector}</span>
        <span>{c.date}</span>
        <span className={cn(c.result === "PASS" ? "text-pr-green" : "text-pr-bronze")}>{c.result}</span>
      </div>
    </motion.div>
  );
}

/**
 * PLATE I — THE OBJECT.
 * The engraved portrait becomes a working assay document: seven inspection
 * points open their records, and the product ledger stands beside it.
 */
export function ProductPlate() {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [qty, setQty] = useState(1);
  const inLedger = useLedger((s) => s.qty);
  const stamp = useLedger((s) => s.stamp);
  const reduced = useReducedMotion();
  const tiltRef = useRef<HTMLDivElement>(null);

  const onTilt = (e: React.PointerEvent) => {
    if (reduced || e.pointerType !== "mouse") return;
    const el = tiltRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const nx = (e.clientX - r.left) / r.width - 0.5;
    const ny = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `perspective(1100px) rotateX(${(-ny * 3).toFixed(2)}deg) rotateY(${(nx * 3.6).toFixed(2)}deg)`;
  };
  const resetTilt = () => {
    if (tiltRef.current) tiltRef.current.style.transform = "perspective(1100px)";
  };

  return (
    <PlateFrame id="object" numeral="I" title="The Object" kicker="Plate I — Assay of the merchandise">
      <div className="grid gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:gap-14">
        {/* ——— The working portrait ——— */}
        <div data-reveal className="relative">
          <div
            ref={tiltRef}
            onPointerMove={onTilt}
            onPointerLeave={resetTilt}
            className="relative border border-ink/70 bg-sheet p-3 shadow-[6px_6px_0_rgba(34,29,18,0.14)] transition-transform duration-300 will-change-transform sm:p-5"
            data-cursor="inspect"
          >
            <div className="border border-ink/40 p-1">
              <EngravedHeadphones
                interactive
                activeId={activeId}
                onSelect={setActiveId}
                className="block h-auto w-full"
              />
            </div>
            <p className="mt-3 flex items-center justify-between font-ledger text-[8.5px] uppercase tracking-[0.22em] text-ink-soft">
              <span>Working copy — 7 inspection points</span>
              <span>Tap a rosette to read its record</span>
            </p>
            <div className="pointer-events-none absolute inset-1.5 sm:inset-2.5">
              <AnimatePresence>{activeId && <CalloutCard activeId={activeId} onClose={() => setActiveId(null)} />}</AnimatePresence>
            </div>
          </div>
        </div>

        {/* ——— The product ledger ——— */}
        <div data-reveal data-delay="0.12" className="flex flex-col">
          <div className="flex flex-wrap items-center gap-2.5">
            <Stamp tone="green" rotate={-2}>
              Certified open-box
            </Stamp>
            <Stamp tone="ink" rotate={1.5}>
              {PRODUCT.condition.label}
            </Stamp>
            <Stamp tone="bronze" rotate={-1}>
              Passport {PRODUCT.provenanceBadge.ref}
            </Stamp>
          </div>

          <h3 className="engraved mt-5 text-4xl font-semibold leading-[1.02] text-ink sm:text-5xl">
            {PRODUCT.name}
          </h3>
          <p className="engraved-text mt-2 text-base italic text-ink-soft">{PRODUCT.tagline}</p>

          <dl className="mt-6">
            <div className="ledger-row">
              <dt>Face value / MSRP</dt>
              <dd className="engraved text-2xl font-bold text-ink">{formatUSD(PRODUCT.msrp)}</dd>
            </div>
            <div className="ledger-row">
              <dt>Minor units</dt>
              <dd>{PRODUCT.minorUnits.toLocaleString()}</dd>
            </div>
            <div className="ledger-row">
              <dt>SKU</dt>
              <dd>{PRODUCT.sku}</dd>
            </div>
            <div className="ledger-row">
              <dt>Origin</dt>
              <dd className="max-w-[26ch] text-right">{PRODUCT.origin}</dd>
            </div>
            <div className="ledger-row">
              <dt>Condition</dt>
              <dd className="text-pr-green">{PRODUCT.condition.note}</dd>
            </div>
          </dl>

          {/* Specs */}
          <div className="mt-6 border border-ink/60">
            <p className="border-b border-ink/60 bg-paper-2 px-4 py-2 font-ledger text-[9px] font-semibold uppercase tracking-[0.26em] text-ink">
              Specification table
            </p>
            <dl className="divide-y divide-ink/15 px-4">
              {PRODUCT.specs.map((s) => (
                <div key={s.label} className="ledger-row !border-b-0 !py-2.5">
                  <dt>{s.label}</dt>
                  <dd className="max-w-[24ch] text-right text-[12px]">{s.value}</dd>
                </div>
              ))}
            </dl>
          </div>

          {/* Provenance pointer */}
          <a
            href="#passport"
            data-cursor="read"
            className="group mt-4 flex items-center justify-between border border-dashed border-pr-bronze/70 bg-paper-2/50 px-4 py-3 transition-colors hover:border-pr-bronze"
          >
            <span className="font-ledger text-[10px] uppercase tracking-[0.2em] text-pr-bronze">
              ↳ Condition Passport · {PRODUCT.provenanceBadge.line}
            </span>
            <span className="font-ledger text-[10px] text-pr-bronze transition-transform group-hover:translate-x-1">→</span>
          </a>

          {/* Stamp to ledger */}
          <div className="mt-6 border-t-2 border-ink pt-5">
            <div className="flex flex-wrap items-center gap-5">
              <div className="flex items-center border border-ink" role="group" aria-label="Quantity">
                <button
                  onClick={() => setQty(Math.max(1, qty - 1))}
                  className="h-11 w-11 font-ledger text-lg text-ink transition-colors hover:bg-paper-3"
                  aria-label="Decrease quantity"
                >
                  –
                </button>
                <span className="w-10 text-center font-ledger text-sm font-semibold" aria-live="polite">
                  {qty}
                </span>
                <button
                  onClick={() => setQty(Math.min(3, qty + 1))}
                  className="h-11 w-11 font-ledger text-lg text-ink transition-colors hover:bg-paper-3"
                  aria-label="Increase quantity"
                >
                  +
                </button>
              </div>
              <button
                onClick={() => stamp(qty)}
                data-cursor="open"
                className="btn-engraved btn-engraved-solid flex-1"
              >
                Stamp to ledger — {formatUSD(PRODUCT.msrp * qty)}
              </button>
            </div>
            <p className="mt-3 font-ledger text-[9px] uppercase tracking-[0.18em] text-ink-soft">
              {inLedger > 0
                ? `In ledger: ${inLedger} unit${inLedger > 1 ? "s" : ""} — settle at the Counting House (Plate IV).`
                : "Refund readiness is printed on your receipt — see Plate II for the curve."}
            </p>
          </div>
        </div>
      </div>
    </PlateFrame>
  );
}
