"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Scale,
  Barcode,
  ShieldCheck,
  Printer,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Sparkles,
  ArrowRight,
  Fingerprint,
  Radio,
  Layers,
  Package,
} from "lucide-react";
import { useDemoContext } from "@/lib/demo-context";
import { cn } from "@/lib/utils";
import { getLivePassport } from "@/lib/api";
import Link from "next/link";

export default function PackingStationPage() {
  const { state, mintPassport, processDockCheckIn } = useDemoContext();
  const [mode, setMode] = useState<"PACKING" | "RECEIVING">("PACKING");

  // Packing mode states
  const [scaleWeight, setScaleWeight] = useState<number>(250.0);
  const [isStable, setIsStable] = useState<boolean>(true);
  const [selfTestPassed, setSelfTestPassed] = useState<boolean>(true);
  const [minted, setMinted] = useState<boolean>(false);
  const [printingLabel, setPrintingLabel] = useState<boolean>(false);

  // Receiving mode states
  const [dockWeight, setDockWeight] = useState<number>(249.8);
  const [sealIntact, setSealIntact] = useState<boolean>(true);
  const [observedGrade, setObservedGrade] = useState<"A" | "B" | "C" | "D" | "DEF">("B");
  const [dockProcessed, setDockProcessed] = useState<"PASSED" | "FLAGGED" | null>(null);

  // Fetch live passport data from backend/SQLite if available
  useEffect(() => {
    getLivePassport("pass_demo_1").then((live) => {
      if (live && typeof live.weight_g === "number") {
        setScaleWeight(live.weight_g);
      }
    });
  }, []);

  // Subtle live scale jitter simulation for realism
  useEffect(() => {
    const timer = setInterval(() => {
      if (mode === "PACKING" && !minted) {
        const jitter = (Math.random() - 0.5) * 0.2;
        setScaleWeight(Number((250.0 + jitter).toFixed(1)));
      }
    }, 2400);
    return () => clearInterval(timer);
  }, [mode, minted]);

  const handleMintPassport = () => {
    setPrintingLabel(true);
    setTimeout(() => {
      mintPassport({
        id: "pass_demo_1",
        serialNumber: "SN-DEMO-XM5-001",
        weightGrams: scaleWeight,
        sealIntact: true,
        functionalSelfTestPassed: selfTestPassed,
      });
      setMinted(true);
      setPrintingLabel(false);
    }, 1200);
  };

  const handleDockAction = (passed: boolean) => {
    processDockCheckIn(passed, dockWeight, observedGrade);
    setDockProcessed(passed ? "PASSED" : "FLAGGED");
  };

  return (
    <div className="min-h-[calc(100vh-93px)] bg-paper pb-20">
      {/* Station Sub-Header */}
      <section className="border-b border-line bg-panel/60 py-6 px-4 sm:px-6">
        <div className="mx-auto flex max-w-[1300px] flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="grid h-5 w-5 place-items-center rounded bg-teal/10 font-tech text-[10px] font-bold text-teal">
                02
              </span>
              <span className="font-tech text-xs uppercase tracking-widest text-faint">
                Warehouse Operations · Origin Rig & Inbound Dock
              </span>
            </div>
            <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-ink mt-1">
              Packing Station & Dock Terminal
            </h1>
            <p className="font-tech text-xs text-dim mt-0.5">
              Physical-Digital Provenance Binding & Tamper Seal Verification (SSOT F-01 & F-06)
            </p>
          </div>

          {/* Mode Switcher Tabs */}
          <div className="flex items-center rounded-lg border border-line bg-paper p-1 font-tech text-xs shadow-xs">
            <button
              onClick={() => setMode("PACKING")}
              className={cn(
                "flex items-center gap-2 rounded-md px-4 py-2 font-medium transition-all cursor-pointer",
                mode === "PACKING"
                  ? "bg-panel text-ink shadow-xs border border-line"
                  : "text-dim hover:text-ink"
              )}
            >
              <Package className="h-3.5 w-3.5 text-teal" />
              <span>Origin Minting (F-01)</span>
            </button>
            <button
              onClick={() => setMode("RECEIVING")}
              className={cn(
                "flex items-center gap-2 rounded-md px-4 py-2 font-medium transition-all cursor-pointer",
                mode === "RECEIVING"
                  ? "bg-panel text-ink shadow-xs border border-line"
                  : "text-dim hover:text-ink"
              )}
            >
              <Layers className="h-3.5 w-3.5 text-sig" />
              <span>Inbound Dock Check-In (F-06)</span>
            </button>
          </div>
        </div>
      </section>

      {/* Main Content Area */}
      <main className="mx-auto max-w-[1300px] px-4 sm:px-6 pt-8">
        <AnimatePresence mode="wait">
          {mode === "PACKING" ? (
            <motion.div
              key="packing-mode"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="grid grid-cols-1 lg:grid-cols-12 gap-8"
            >
              {/* Left Column: Live Scale & Verification Rig */}
              <div className="lg:col-span-7 space-y-6">
                {/* Scale Console Card */}
                <div className="rounded-xl border border-line bg-panel p-6 shadow-xs">
                  <div className="flex items-center justify-between border-b border-line pb-4">
                    <div className="flex items-center gap-2.5">
                      <Scale className="h-4 w-4 text-teal" />
                      <h2 className="font-display text-base font-bold text-ink">
                        Precision Load Cell Telemetry
                      </h2>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="flex items-center gap-1.5 rounded-full border border-ok/40 bg-ok/10 px-2 py-0.5 font-tech text-[10px] font-semibold text-ok uppercase">
                        <span className="h-1.5 w-1.5 rounded-full bg-ok animate-pulse" />
                        Calibrated ISO-17025
                      </span>
                    </div>
                  </div>

                  {/* Weight Readout */}
                  <div className="mt-6 flex flex-col items-center justify-center rounded-lg border border-line/80 bg-paper/60 p-8 text-center relative overflow-hidden">
                    <div className="absolute top-3 left-3 flex items-center gap-1.5 font-tech text-[10px] text-faint">
                      <Radio className="h-3 w-3 text-teal animate-spin" />
                      LIVE TARE: 0.0g
                    </div>

                    <div className="font-tech text-6xl sm:text-7xl font-bold tracking-tight text-ink tabular-nums">
                      {scaleWeight.toFixed(1)}
                      <span className="text-2xl sm:text-3xl text-dim font-normal ml-2">g</span>
                    </div>

                    <p className="mt-2 font-tech text-xs uppercase tracking-widest text-dim">
                      Origin Specimen Mass · Tolerance ±1.5g
                    </p>

                    <div className="mt-5 flex gap-2">
                      <button
                        onClick={() => {
                          setScaleWeight(250.0);
                          setIsStable(true);
                        }}
                        className="rounded border border-line bg-panel px-3 py-1 font-tech text-[11px] text-dim hover:text-ink cursor-pointer"
                      >
                        Tare & Zero
                      </button>
                      <button
                        onClick={() => {
                          const delta = (Math.random() - 0.5) * 1.0;
                          setScaleWeight(Number((250.0 + delta).toFixed(1)));
                        }}
                        className="rounded border border-line bg-panel px-3 py-1 font-tech text-[11px] text-dim hover:text-ink cursor-pointer"
                      >
                        Simulate Item Re-seat
                      </button>
                    </div>
                  </div>

                  {/* Hardware & Sensor Checklist */}
                  <div className="mt-6 space-y-3 font-tech text-xs">
                    <div className="flex items-center justify-between rounded-md border border-line bg-paper px-3.5 py-2.5">
                      <span className="text-ink">1. Acoustic Frequency Self-Test (ANC sweep)</span>
                      <span className="font-semibold text-ok">PASSED (99.8%)</span>
                    </div>
                    <div className="flex items-center justify-between rounded-md border border-line bg-paper px-3.5 py-2.5">
                      <span className="text-ink">2. Dual Micro-optical Tamper Seal Affixed</span>
                      <span className="font-semibold text-teal">SEAL #TS-8840-X</span>
                    </div>
                    <label className="flex items-center justify-between rounded-md border border-line bg-paper px-3.5 py-2.5 cursor-pointer">
                      <span className="text-ink">3. Functional Quality Inspection Verified</span>
                      <input
                        type="checkbox"
                        checked={selfTestPassed}
                        onChange={(e) => setSelfTestPassed(e.target.checked)}
                        className="h-4 w-4 rounded border-line text-teal focus:ring-teal cursor-pointer"
                      />
                    </label>
                  </div>
                </div>

                {/* Passport Minting Action */}
                <div className="rounded-xl border border-line bg-panel p-6 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
                  <div>
                    <h3 className="font-display text-sm font-bold text-ink">
                      Cryptographic Passport Minting (F-01)
                    </h3>
                    <p className="font-tech text-xs text-dim mt-0.5">
                      Binds Physical Weight ({scaleWeight}g) + Serial + Nonce into Immutable Passport
                    </p>
                  </div>
                  <button
                    onClick={handleMintPassport}
                    disabled={printingLabel || minted}
                    className={cn(
                      "flex items-center gap-2 rounded-lg px-5 py-3 font-tech text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer whitespace-nowrap",
                      minted
                        ? "border border-ok/40 bg-ok/10 text-ok cursor-default"
                        : "bg-teal text-white hover:bg-teal/90 shadow-sm"
                    )}
                  >
                    {printingLabel ? (
                      <>
                        <Printer className="h-4 w-4 animate-bounce" />
                        <span>Generating Passport...</span>
                      </>
                    ) : minted ? (
                      <>
                        <CheckCircle2 className="h-4 w-4 text-ok" />
                        <span>Passport Minted</span>
                      </>
                    ) : (
                      <>
                        <Fingerprint className="h-4 w-4" />
                        <span>Mint Condition Passport ➔</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Right Column: Physical Item Dossier & Minted Certificate */}
              <div className="lg:col-span-5 space-y-6">
                <div className="rounded-xl border border-line bg-panel p-6 shadow-xs">
                  <div className="flex items-center justify-between border-b border-line pb-4">
                    <div className="flex items-center gap-2">
                      <Barcode className="h-4 w-4 text-faint" />
                      <h2 className="font-display text-base font-bold text-ink">
                        Specimen Dossier
                      </h2>
                    </div>
                    <span className="font-tech text-[10px] text-faint">
                      ORDER: {state.order.id}
                    </span>
                  </div>

                  <dl className="mt-5 space-y-3 font-tech text-xs divide-y divide-line/60">
                    <div className="flex justify-between pt-2">
                      <dt className="text-dim">Product SKU</dt>
                      <dd className="font-semibold text-ink">{state.order.sku}</dd>
                    </div>
                    <div className="flex justify-between pt-2">
                      <dt className="text-dim">Device Model</dt>
                      <dd className="font-semibold text-ink">{state.order.name}</dd>
                    </div>
                    <div className="flex justify-between pt-2">
                      <dt className="text-dim">Serial Number</dt>
                      <dd className="font-semibold text-ink">{state.passport.serialNumber}</dd>
                    </div>
                    <div className="flex justify-between pt-2">
                      <dt className="text-dim">Origin Nonce</dt>
                      <dd className="font-mono text-teal">{state.passport.originNonce}</dd>
                    </div>
                    <div className="flex justify-between pt-2">
                      <dt className="text-dim">Passport ID</dt>
                      <dd className="font-mono text-ink">{state.passport.id}</dd>
                    </div>
                  </dl>

                  {/* Minted Security Certificate Visual */}
                  <div className="mt-6 rounded-lg border-2 border-dashed border-teal/40 bg-teal/[0.03] p-5">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="h-5 w-5 text-teal" />
                        <span className="font-display text-xs font-bold uppercase tracking-wider text-teal">
                          Digital Condition Passport
                        </span>
                      </div>
                      <span className="font-tech text-[9px] uppercase tracking-widest text-dim">
                        TIER 1 · FULL
                      </span>
                    </div>

                    <div className="mt-4 rounded border border-line bg-panel p-3 font-tech text-[10px] space-y-1">
                      <div className="text-faint text-[9px] uppercase">Cryptographic Origin Hash:</div>
                      <div className="font-mono text-[9px] break-all text-dim">
                        {state.passport.serialHash}
                      </div>
                    </div>

                    <div className="mt-3 flex items-center justify-between text-[10px] font-tech text-dim">
                      <span>Certified Mass: <strong>{scaleWeight} g</strong></span>
                      <span>Integrity: <strong className="text-ok">SEALED</strong></span>
                    </div>
                  </div>

                  {minted && (
                    <motion.div
                      initial={{ opacity: 0, y: 5 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mt-4 p-3 rounded-lg border border-ok/30 bg-ok/5 text-center"
                    >
                      <p className="font-tech text-xs text-ok font-semibold">
                        ✓ Passport Active in Demonstration Context
                      </p>
                      <p className="font-tech text-[10px] text-dim mt-0.5">
                        You can now navigate to Shopper Return or Merchant Console to test the full lifecycle.
                      </p>
                      <div className="mt-3 flex justify-center gap-2">
                        <Link
                          href="/shopper"
                          className="inline-flex items-center gap-1 rounded border border-line bg-panel px-3 py-1 font-tech text-xs text-ink hover:border-indigo cursor-pointer"
                        >
                          <span>Open Shopper Return</span>
                          <ArrowRight className="h-3 w-3" />
                        </Link>
                      </div>
                    </motion.div>
                  )}
                </div>
              </div>
            </motion.div>
          ) : (
            /* Mode 2: Inbound Dock Check-In */
            <motion.div
              key="receiving-mode"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="grid grid-cols-1 lg:grid-cols-12 gap-8"
            >
              <div className="lg:col-span-7 space-y-6">
                <div className="rounded-xl border border-line bg-panel p-6 shadow-xs">
                  <div className="flex items-center justify-between border-b border-line pb-4">
                    <div className="flex items-center gap-2">
                      <Layers className="h-4 w-4 text-sig" />
                      <h2 className="font-display text-base font-bold text-ink">
                        Inbound Package Physical Inspection (F-06)
                      </h2>
                    </div>
                    <span className="font-tech text-[10px] rounded border border-line bg-paper px-2 py-0.5 text-dim">
                      RETURN: {state.returnClaim.returnId}
                    </span>
                  </div>

                  <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {/* Weight Comparison Tile */}
                    <div className="rounded-lg border border-line bg-paper p-4">
                      <span className="font-tech text-[10px] uppercase text-faint">
                        Origin Mass vs Return Mass
                      </span>
                      <div className="mt-2 flex items-baseline justify-between">
                        <div>
                          <span className="font-tech text-2xl font-bold text-ink">{dockWeight}</span>
                          <span className="font-tech text-xs text-dim ml-1">g</span>
                          <span className="font-tech text-[10px] text-faint block">Received at Dock</span>
                        </div>
                        <div className="text-right">
                          <span className="font-tech text-base text-dim">{state.passport.weightGrams}</span>
                          <span className="font-tech text-xs text-faint ml-1">g</span>
                          <span className="font-tech text-[10px] text-faint block">Expected (Minted)</span>
                        </div>
                      </div>
                      <div className="mt-3 flex items-center justify-between border-t border-line/60 pt-2 font-tech text-[10px]">
                        <span className="text-faint">Variance Delta:</span>
                        <span className="font-semibold text-ok">
                          {(dockWeight - state.passport.weightGrams).toFixed(1)}g (Within ±2.0g)
                        </span>
                      </div>
                    </div>

                    {/* Tamper Seal Inspection Tile */}
                    <div className="rounded-lg border border-line bg-paper p-4">
                      <span className="font-tech text-[10px] uppercase text-faint">
                        Tamper-Evident Seal State
                      </span>
                      <div className="mt-2 flex items-center justify-between">
                        <span className="font-display text-base font-bold text-ink">
                          {sealIntact ? "Seal Intact & Unbroken" : "Seal Tampered / Compromised"}
                        </span>
                        <span
                          className={cn(
                            "grid h-7 w-7 place-items-center rounded-full text-white",
                            sealIntact ? "bg-ok" : "bg-bad"
                          )}
                        >
                          {sealIntact ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                        </span>
                      </div>
                      <button
                        onClick={() => setSealIntact(!sealIntact)}
                        className="mt-3 w-full rounded border border-line bg-panel py-1 font-tech text-[10px] text-dim hover:text-ink cursor-pointer"
                      >
                        Simulate: {sealIntact ? "Toggle Tamper Alert" : "Mark Seal Intact"}
                      </button>
                    </div>
                  </div>

                  {/* Physical Condition Grade Picker */}
                  <div className="mt-6 border-t border-line pt-5">
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-display text-sm font-bold text-ink">
                        Inspector Observed Cosmetic Grade
                      </span>
                      <span className="font-tech text-xs text-faint">
                        Shopper Declared: <strong>Grade {state.returnClaim.declaredGrade}</strong>
                      </span>
                    </div>

                    <div className="grid grid-cols-5 gap-2 font-tech">
                      {(["A", "B", "C", "D", "DEF"] as const).map((grade) => (
                        <button
                          key={grade}
                          onClick={() => setObservedGrade(grade)}
                          className={cn(
                            "rounded-lg border p-3 text-center transition-all cursor-pointer",
                            observedGrade === grade
                              ? "border-teal bg-teal/10 text-teal font-bold shadow-xs"
                              : "border-line bg-paper text-dim hover:border-faint"
                          )}
                        >
                          <div className="text-base font-bold">{grade}</div>
                          <div className="text-[9px] uppercase tracking-wider text-faint mt-0.5">
                            {grade === "A"
                              ? "Mint"
                              : grade === "B"
                              ? "Light Wear"
                              : grade === "C"
                              ? "Scuffs"
                              : grade === "D"
                              ? "Heavy"
                              : "Defective"}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="mt-8 flex flex-col sm:flex-row gap-3">
                    <button
                      onClick={() => handleDockAction(true)}
                      className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-ok py-3 font-tech text-xs font-semibold uppercase tracking-wider text-white shadow-xs hover:bg-ok/90 cursor-pointer"
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      <span>Dock Check-In Passed ➔ Release Escrow ($15.00)</span>
                    </button>
                    <button
                      onClick={() => handleDockAction(false)}
                      className="flex items-center justify-center gap-2 rounded-lg border border-bad/40 bg-bad/10 px-4 py-3 font-tech text-xs font-semibold uppercase tracking-wider text-bad hover:bg-bad/20 cursor-pointer"
                    >
                      <AlertTriangle className="h-4 w-4" />
                      <span>Flag Discrepancy</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Right Column: Dock Resolution Status */}
              <div className="lg:col-span-5 space-y-6">
                <div className="rounded-xl border border-line bg-panel p-6 shadow-xs">
                  <h3 className="font-display text-base font-bold text-ink border-b border-line pb-3">
                    Settlement & Escrow Resolution
                  </h3>

                  <div className="mt-4 space-y-4 font-tech text-xs">
                    <div className="rounded-lg border border-line bg-paper p-4 space-y-2">
                      <div className="flex justify-between">
                        <span className="text-dim">Instant Refund (R0) Paid:</span>
                        <span className="font-semibold text-ink">${(state.returnClaim.r0TrancheMinor / 100).toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-dim">Holdback Escrow ({state.policy.misdeclarationFeeMinor ? "$15.00" : "$15.00"}):</span>
                        <span className="font-semibold text-sig">
                          {dockProcessed === "PASSED" ? "RELEASED TO BUYER" : "HELD IN ESCROW"}
                        </span>
                      </div>
                      <div className="flex justify-between border-t border-line/60 pt-2">
                        <span className="text-ink font-semibold">Net Final Payout:</span>
                        <span className="font-bold text-ok">
                          ${((state.returnClaim.r0TrancheMinor + (dockProcessed === "PASSED" ? 1500 : 0)) / 100).toFixed(2)}
                        </span>
                      </div>
                    </div>

                    {dockProcessed && (
                      <div
                        className={cn(
                          "rounded-lg border p-4 text-center",
                          dockProcessed === "PASSED"
                            ? "border-ok/40 bg-ok/5 text-ok"
                            : "border-bad/40 bg-bad/5 text-bad"
                        )}
                      >
                        <p className="font-bold text-sm">
                          {dockProcessed === "PASSED" ? "✓ Dock Check-in Approved" : "⚠ Discrepancy Escrow Flagged"}
                        </p>
                        <p className="text-[11px] text-dim mt-1">
                          {dockProcessed === "PASSED"
                            ? "Holdback escrow released. The return journey is complete."
                            : "Case routed to Merchant Review Queue for manual inspection."}
                        </p>
                        <div className="mt-3">
                          <Link
                            href="/merchant"
                            className="inline-flex items-center gap-1 font-tech text-xs text-ink hover:underline cursor-pointer"
                          >
                            <span>Inspect in Merchant Console</span>
                            <ArrowRight className="h-3 w-3" />
                          </Link>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
