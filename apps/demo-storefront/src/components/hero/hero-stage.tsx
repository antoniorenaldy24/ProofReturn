"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowDown, Copy, Layers, MousePointerClick, RotateCw, ShoppingCart } from "lucide-react";
import { CALLOUTS, HERO_HOTSPOTS, PRODUCT, formatUSD } from "@/lib/data";
import { useLedger } from "@/lib/store";
import { Bracket, Chip, LED, Rise } from "@/components/chrome/hud";
import type { AnchorRegistry, NodeRegistry } from "./headphones-3d";

const HeadsetScene = dynamic(() => import("./headphones-3d"), {
  ssr: false,
  loading: () => (
    <div className="grid h-full w-full place-items-center bg-grid">
      <span className="font-tech text-[11px] uppercase tracking-[0.3em] text-faint led-pulse">
        Calibrating optical bay…
      </span>
    </div>
  ),
});

export function HeroStage() {
  const stamp = useLedger((s) => s.stamp);
  const [selected, setSelected] = useState<string | null>(null);
  const [explode, setExplode] = useState(false);
  const [autoRotate, setAutoRotate] = useState(true);
  const azRef = useRef<HTMLSpanElement>(null);
  const anchors = useRef<AnchorRegistry>({});
  const nodes = useRef<NodeRegistry>({});
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const raf = requestAnimationFrame(() => {
      setReduced(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    });
    return () => cancelAnimationFrame(raf);
  }, []);

  const callout = useMemo(
    () => CALLOUTS.find((c) => c.id === selected) ?? null,
    [selected],
  );

  return (
    <section id="specimen" className="relative overflow-hidden pt-14">
      {/* ambient washes — the bay breathes */}
      <div
        aria-hidden
        className="wash left-[-8%] top-[6%] h-[420px] w-[420px]"
        style={{ ["--blob" as string]: "var(--sig)", ["--blob-o" as string]: 0.1 }}
      />
      <div
        aria-hidden
        className="wash right-[-6%] bottom-[-4%] h-[380px] w-[380px]"
        style={{ ["--blob" as string]: "var(--teal)", ["--blob-o" as string]: 0.07, ["--blob-t" as string]: "36s" }}
      />

      <div className="relative grid min-h-[calc(100svh-3.5rem)] lg:grid-cols-[420px_1fr] xl:grid-cols-[460px_1fr]">
        {/* ——— HUD panel ——— */}
        <div className="order-2 flex flex-col justify-between gap-6 border-t border-line px-4 py-6 sm:px-6 lg:order-1 lg:border-t-0 lg:border-r lg:py-10">
          <div>
            <Rise>
              <div className="flex items-center justify-between gap-3 font-tech text-[10px] uppercase tracking-[0.22em] text-faint">
                <span className="flex items-center gap-2">
                  <LED color="ok" pulse /> Unit PR-0038 · on the rig
                </span>
                <span className="rounded-full border border-line px-2 py-0.5">BAY 01</span>
              </div>

              <h1 className="mt-6 font-display text-5xl font-bold leading-[0.98] tracking-tight text-ink sm:text-6xl xl:text-7xl">
                Auralis
                <span className="hl" style={{ ["--hl" as string]: "var(--sig)" }}>
                  {" "}N°1
                </span>
              </h1>
              <p className="mt-3 max-w-sm font-display text-[13.5px] leading-relaxed text-dim">
                {PRODUCT.tagline} — certified open-box. Every claim on this page
                is a <span className="font-semibold text-ink">live instrument</span>,
                not marketing copy.
              </p>

              <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-3">
                <span className="font-display text-4xl font-bold tracking-tight text-ink">
                  {formatUSD(PRODUCT.msrp)}
                </span>
                <Chip tone="ok">Grade A origin</Chip>
                <Chip tone="sig">Open-box certified</Chip>
              </div>
            </Rise>

            <Rise delay={0.08}>
              <dl className="mt-6">
                <div className="data-row">
                  <dt>Origin / measured weight</dt>
                  <dd className="tabular-nums">
                    {PRODUCT.condition.grade === "A" ? "258.3 g → 258.1 g" : "—"}
                  </dd>
                </div>
                <div className="data-row">
                  <dt>Packaging seal</dt>
                  <dd className="flex items-center justify-end gap-2">
                    <LED color="ok" /> SEAL 04-7A · INTACT
                  </dd>
                </div>
                <div className="data-row">
                  <dt>Condition Passport</dt>
                  <dd>PP-2026-0038-A</dd>
                </div>
                <div className="data-row border-b-0">
                  <dt>SKU</dt>
                  <dd className="text-dim">{PRODUCT.sku}</dd>
                </div>
              </dl>
            </Rise>
          </div>

          {/* selected scan point readout */}
          <Rise delay={0.14}>
            <Bracket className="panel-inset p-4" color={callout ? "sig" : "line"}>
              <div className="flex min-h-[92px] flex-col justify-center">
                <AnimatePresence mode="wait" initial={false}>
                  {callout ? (
                    <motion.div
                      key={callout.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      transition={{ duration: 0.18 }}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="flex items-center gap-2 font-tech text-[11px] font-semibold uppercase tracking-[0.14em] text-ink">
                          <span
                            className="grid h-5 w-5 place-items-center rounded-full text-[10px] text-white"
                            style={{ background: "var(--sig)" }}
                          >
                            {callout.marker}
                          </span>
                          {callout.zone}
                        </span>
                        <Chip tone={callout.result === "PASS" ? "ok" : "warn"}>
                          {callout.result}
                        </Chip>
                      </div>
                      <p className="mt-2 font-display text-[12.5px] leading-relaxed text-dim">
                        {callout.note}
                      </p>
                      <p className="mt-2 font-tech text-[10px] uppercase tracking-[0.14em] text-faint">
                        {callout.inspector} · {callout.date}
                      </p>
                    </motion.div>
                  ) : (
                    <motion.p
                      key="idle"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="font-display text-[12.5px] leading-relaxed text-faint"
                    >
                      <MousePointerClick
                        className="mr-1.5 inline h-3.5 w-3.5 text-sig"
                        strokeWidth={1.5}
                      />
                      Tap a numbered marker on the headphones to read its
                      inspection record.
                    </motion.p>
                  )}
                </AnimatePresence>
              </div>
            </Bracket>
          </Rise>

          <Rise delay={0.2}>
            <div className="flex flex-wrap gap-2.5">
              <button
                type="button"
                onClick={() => setExplode((v) => !v)}
                aria-pressed={explode}
                className={`btn-ghost ${explode ? "!border-sig !text-sig" : ""}`}
              >
                <Layers className="h-3.5 w-3.5" strokeWidth={1.5} />
                {explode ? "Assemble" : "Explode view"}
              </button>
              <button
                type="button"
                onClick={() => setAutoRotate((v) => !v)}
                aria-pressed={autoRotate}
                className={`btn-ghost ${autoRotate ? "!border-sig !text-sig" : ""}`}
              >
                <RotateCw className="h-3.5 w-3.5" strokeWidth={1.5} />
                Turntable {autoRotate ? "on" : "off"}
              </button>
            </div>
            <div className="mt-3 flex flex-wrap gap-2.5">
              <button
                type="button"
                data-cursor="open"
                onClick={() => stamp(1)}
                className="btn-hud flex-1 sm:flex-none"
              >
                <ShoppingCart className="h-3.5 w-3.5" strokeWidth={2} />
                Add to order — {formatUSD(PRODUCT.msrp)}
              </button>
              <a href="#circ" className="btn-ghost">
                See your refund future
                <ArrowDown className="h-3.5 w-3.5" strokeWidth={1.5} />
              </a>
            </div>
            <p className="mt-4 flex items-center gap-2 font-tech text-[10px] uppercase tracking-[0.16em] text-faint">
              <Copy className="h-3 w-3" /> Drag to orbit · markers ①–⑤ are clickable
            </p>
          </Rise>
        </div>

        {/* ——— optical bay ——— */}
        <div className="relative order-1 h-[58svh] lg:order-2 lg:h-auto lg:min-h-[calc(100svh-3.5rem)]">
          <div className="absolute inset-0 bg-grid" />
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_42%,rgba(214,58,0,0.07),transparent_55%)]" />
          <HeadsetScene
            explode={explode}
            autoRotate={autoRotate}
            reducedMotion={reduced}
            selectedId={selected}
            azimuthRef={azRef}
            anchors={anchors}
            nodes={nodes}
          />

          {/* projected scan-point buttons (positions driven by the scene) */}
          <div className="pointer-events-none absolute inset-0 z-10">
            {HERO_HOTSPOTS.map((h) => {
              const c = CALLOUTS.find((x) => x.id === h.id);
              const active = selected === h.id;
              return (
                <button
                  key={h.id}
                  type="button"
                  ref={(el) => {
                    nodes.current[h.id] = el;
                  }}
                  data-cursor="inspect"
                  onClick={() => setSelected((cur) => (cur === h.id ? null : h.id))}
                  aria-pressed={active}
                  aria-label={`Scan point ${c?.marker ?? ""} — ${c?.zone ?? ""}`}
                  style={{ transform: "translate3d(-9999px, -9999px, 0)" }}
                  className={`absolute top-0 left-0 flex items-center gap-1.5 rounded-full border px-2 py-1 font-tech text-[10px] font-semibold tracking-[0.14em] shadow-sm backdrop-blur-sm transition-all duration-200 ${
                    active
                      ? "border-sig bg-sig/20 text-sig scale-110"
                      : "border-faint/60 bg-paper/85 text-dim hover:border-sig/70 hover:text-sig hover:scale-105"
                  }`}
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      active ? "bg-sig led-pulse" : "bg-faint"
                    }`}
                  />
                  {c?.marker}
                </button>
              );
            })}
          </div>

          {/* HUD corners + readouts */}
          <span aria-hidden className="pointer-events-none absolute top-4 left-4 h-3 w-3 rounded-tl border-t border-l border-sig/60" />
          <span aria-hidden className="pointer-events-none absolute top-4 right-4 h-3 w-3 rounded-tr border-t border-r border-sig/60" />
          <span aria-hidden className="pointer-events-none absolute bottom-4 left-4 h-3 w-3 rounded-bl border-b border-l border-sig/60" />
          <span aria-hidden className="pointer-events-none absolute bottom-4 right-4 h-3 w-3 rounded-br border-b border-r border-sig/60" />
          <div className="pointer-events-none absolute top-5 left-6 rounded-full border border-line bg-paper/70 px-2.5 py-1 font-tech text-[10px] uppercase tracking-[0.2em] text-faint backdrop-blur-sm">
            Optical bay 02
          </div>
          <div className="pointer-events-none absolute top-5 right-6 rounded-full border border-line bg-paper/70 px-2.5 py-1 font-tech text-[10px] tabular-nums tracking-[0.16em] text-dim backdrop-blur-sm">
            AZ <span ref={azRef} className="text-sig tabular-nums">38.0</span>°
          </div>
          <div className="pointer-events-none absolute bottom-5 left-6 rounded-full border border-line bg-paper/70 px-2.5 py-1 font-tech text-[10px] uppercase tracking-[0.2em] text-faint backdrop-blur-sm">
            {explode ? "Exploded · service layout" : "Assembled · seal intact"}
          </div>
          <div className="pointer-events-none absolute bottom-5 right-6 rounded-full border border-line bg-paper/70 px-2.5 py-1 font-tech text-[10px] uppercase tracking-[0.2em] text-dim backdrop-blur-sm">
            Scan <span className="text-sig">active</span>
          </div>
          <span aria-hidden className="pointer-events-none absolute top-1/2 left-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2">
            <span className="absolute top-1/2 h-px w-full -translate-y-1/2 bg-sig/25" />
            <span className="absolute left-1/2 h-full w-px -translate-x-1/2 bg-sig/25" />
          </span>
        </div>
      </div>

      {/* spec strip */}
      <div className="relative grid grid-cols-2 border-t border-line bg-panel/50 lg:grid-cols-4">
        {[
          { k: "Drivers", v: "40 mm beryllium" },
          { k: "Noise cancelling", v: "Hybrid −38 dB" },
          { k: "Battery", v: "32 h ANC on" },
          { k: "Codecs", v: "LDAC · aptX · AAC" },
        ].map((s, i) => (
          <div
            key={s.k}
            className={`px-4 py-3.5 sm:px-6 ${i > 0 ? "border-l border-line max-lg:[&:nth-child(3)]:border-l-0" : ""} max-lg:[&:nth-child(n+3)]:border-t max-lg:[&:nth-child(odd)]:border-l-0 max-lg:border-line`}
          >
            <span className="block font-tech text-[9px] uppercase tracking-[0.2em] text-faint">
              {s.k}
            </span>
            <span className="mt-1 block font-tech text-[12px] font-medium text-ink">
              {s.v}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
