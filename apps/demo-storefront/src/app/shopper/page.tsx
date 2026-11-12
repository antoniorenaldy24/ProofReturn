"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Camera,
  ShieldAlert,
  ShieldCheck,
  Clock,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Sparkles,
  QrCode,
  DollarSign,
  Gift,
  XCircle,
  RefreshCw,
  FileText,
  Lock,
} from "lucide-react";
import { useDemoContext } from "@/lib/demo-context";
import { cn } from "@/lib/utils";
import { getLivePolicy } from "@/lib/api";
import Link from "next/link";

type Step = "DECLARATION" | "KEEP_OFFER" | "EVIDENCE" | "DECISION" | "SETTLED";

export default function ShopperReturnPage() {
  const { state, declareReturn, submitEvidence, settleR0Refund, cancelReturn } = useDemoContext();

  const [step, setStep] = useState<Step>("DECLARATION");
  const [grade, setGrade] = useState<"A" | "B" | "C" | "D" | "DEF">("B");
  const [accessories, setAccessories] = useState({
    case: true,
    cable: true,
    adapter: true,
  });
  const [reason, setReason] = useState("Fit not ideal for daily commute");
  const [termsAccepted, setTermsAccepted] = useState(true);

  // Evidence capture timer
  const [timeLeft, setTimeLeft] = useState(30);
  const [isCapturing, setIsCapturing] = useState(false);
  const [photoCaptured, setPhotoCaptured] = useState(false);
  const [generatedHash, setGeneratedHash] = useState("");

  // Keep offer amount ($76.00 = 20% of $380)
  const keepOfferAmount = 76.0;

  // Query live policy directly from FastAPI backend / SQLite
  useEffect(() => {
    getLivePolicy("ord_demo_1").then((policy) => {
      if (policy && policy.policy_version) {
        console.log("[ProofReturn] Live backend policy verified:", policy);
      }
    });
  }, []);

  // Countdown timer effect during EVIDENCE step
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (step === "EVIDENCE" && timeLeft > 0 && !photoCaptured) {
      timer = setInterval(() => setTimeLeft((t) => t - 1), 1000);
    }
    return () => clearInterval(timer);
  }, [step, timeLeft, photoCaptured]);

  const handleStartReturn = () => {
    declareReturn(grade, accessories);
    setStep("KEEP_OFFER");
  };

  const handleDeclineKeepOffer = () => {
    setTimeLeft(30);
    setPhotoCaptured(false);
    setStep("EVIDENCE");
  };

  const handleAcceptKeepOffer = () => {
    alert("Keep offer accepted! $76.00 credited instantly to your account. You keep the headphones.");
    setStep("SETTLED");
  };

  const handleCapturePhoto = () => {
    setIsCapturing(true);
    setTimeout(() => {
      const mockHash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
      setGeneratedHash(mockHash);
      setPhotoCaptured(true);
      setIsCapturing(false);
      submitEvidence(mockHash);
    }, 1000);
  };

  const handleFinalizeSettlement = () => {
    settleR0Refund();
    setStep("DECISION");
  };

  return (
    <div className="min-h-[calc(100vh-93px)] bg-paper pb-20">
      {/* Sub-Header */}
      <section className="border-b border-line bg-panel/60 py-6 px-4 sm:px-6">
        <div className="mx-auto flex max-w-[1200px] flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="grid h-5 w-5 place-items-center rounded bg-indigo/10 font-tech text-[10px] font-bold text-indigo">
                03
              </span>
              <span className="font-tech text-xs uppercase tracking-widest text-faint">
                Consumer Intake · Fast-Lane Sovereign Return (SSOT F-03 & F-05)
              </span>
            </div>
            <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-ink mt-1">
              Shopper Return Portal
            </h1>
            <p className="font-tech text-xs text-dim mt-0.5">
              Self-service return with instant R0 liquidity, anti-replay photo challenge, and zero delay
            </p>
          </div>

          {/* Stepper Progress Pill */}
          <div className="flex items-center gap-1 rounded-full border border-line bg-panel p-1 font-tech text-[11px]">
            <span
              className={cn(
                "rounded-full px-3 py-1 font-medium transition-colors",
                step === "DECLARATION" ? "bg-indigo text-white" : "text-faint"
              )}
            >
              1. Declare
            </span>
            <span
              className={cn(
                "rounded-full px-3 py-1 font-medium transition-colors",
                step === "KEEP_OFFER" ? "bg-indigo text-white" : "text-faint"
              )}
            >
              2. Option
            </span>
            <span
              className={cn(
                "rounded-full px-3 py-1 font-medium transition-colors",
                step === "EVIDENCE" ? "bg-indigo text-white" : "text-faint"
              )}
            >
              3. Evidence
            </span>
            <span
              className={cn(
                "rounded-full px-3 py-1 font-medium transition-colors",
                step === "DECISION" ? "bg-indigo text-white" : "text-faint"
              )}
            >
              4. Payout
            </span>
          </div>
        </div>
      </section>

      {/* Main Container */}
      <main className="mx-auto max-w-[1200px] px-4 sm:px-6 pt-8">
        <AnimatePresence mode="wait">
          {/* STEP 1: DECLARATION */}
          {step === "DECLARATION" && (
            <motion.div
              key="step-declaration"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="grid grid-cols-1 lg:grid-cols-12 gap-8"
            >
              <div className="lg:col-span-8 space-y-6">
                <div className="rounded-xl border border-line bg-panel p-6 shadow-xs">
                  <h2 className="font-display text-lg font-bold text-ink">
                    1. Declare Physical Condition Honestly
                  </h2>
                  <p className="font-tech text-xs text-dim mt-1">
                    ProofReturn matches your declared condition with optical proof to unlock instant R0 refund ($365.00).
                  </p>

                  {/* Grade Selector */}
                  <div className="mt-6 space-y-2">
                    <label className="font-tech text-xs font-semibold text-ink uppercase tracking-wider">
                      Observed Item Condition:
                    </label>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-tech">
                      <button
                        type="button"
                        onClick={() => setGrade("A")}
                        className={cn(
                          "rounded-lg border p-4 text-left transition-all cursor-pointer",
                          grade === "A"
                            ? "border-indigo bg-indigo/5 ring-1 ring-indigo"
                            : "border-line bg-paper hover:border-dim"
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-ink">Grade A · Pristine</span>
                          <span className="text-[10px] font-semibold text-ok">100% Refund</span>
                        </div>
                        <p className="text-[11px] text-dim mt-1">Flawless, no visible cosmetic micro-marks.</p>
                      </button>

                      <button
                        type="button"
                        onClick={() => setGrade("B")}
                        className={cn(
                          "rounded-lg border p-4 text-left transition-all cursor-pointer",
                          grade === "B"
                            ? "border-indigo bg-indigo/5 ring-1 ring-indigo"
                            : "border-line bg-paper hover:border-dim"
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-ink">Grade B · Light Wear</span>
                          <span className="text-[10px] font-semibold text-indigo">95% ($365)</span>
                        </div>
                        <p className="text-[11px] text-dim mt-1">Minor contact marks on headband/pads.</p>
                      </button>

                      <button
                        type="button"
                        onClick={() => setGrade("C")}
                        className={cn(
                          "rounded-lg border p-4 text-left transition-all cursor-pointer",
                          grade === "C"
                            ? "border-indigo bg-indigo/5 ring-1 ring-indigo"
                            : "border-line bg-paper hover:border-dim"
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-ink">Grade C · Moderate</span>
                          <span className="text-[10px] font-semibold text-warn">80% Refund</span>
                        </div>
                        <p className="text-[11px] text-dim mt-1">Visible scratches or scuffs on earcups.</p>
                      </button>
                    </div>
                  </div>

                  {/* Included Accessories */}
                  <div className="mt-6 border-t border-line pt-5">
                    <label className="font-tech text-xs font-semibold text-ink uppercase tracking-wider block mb-3">
                      Included Accessories Checklist:
                    </label>
                    <div className="space-y-2 font-tech text-xs">
                      <label className="flex items-center gap-2.5 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={accessories.case}
                          onChange={(e) => setAccessories({ ...accessories, case: e.target.checked })}
                          className="h-4 w-4 rounded border-line text-indigo focus:ring-indigo"
                        />
                        <span className="text-ink">Original Hard Carrying Case</span>
                      </label>
                      <label className="flex items-center gap-2.5 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={accessories.cable}
                          onChange={(e) => setAccessories({ ...accessories, cable: e.target.checked })}
                          className="h-4 w-4 rounded border-line text-indigo focus:ring-indigo"
                        />
                        <span className="text-ink">USB-C Fast Charging Cable</span>
                      </label>
                      <label className="flex items-center gap-2.5 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={accessories.adapter}
                          onChange={(e) => setAccessories({ ...accessories, adapter: e.target.checked })}
                          className="h-4 w-4 rounded border-line text-indigo focus:ring-indigo"
                        />
                        <span className="text-ink">3.5mm Gold-Plated Audio Cord</span>
                      </label>
                    </div>
                  </div>

                  {/* Reason Text */}
                  <div className="mt-6 border-t border-line pt-5">
                    <label className="font-tech text-xs font-semibold text-ink uppercase tracking-wider block mb-2">
                      Reason for Return:
                    </label>
                    <input
                      type="text"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      className="w-full rounded-lg border border-line bg-paper px-3.5 py-2.5 font-tech text-xs text-ink focus:border-indigo focus:outline-none"
                    />
                  </div>

                  {/* Terms */}
                  <div className="mt-6 rounded-lg border border-line bg-paper p-4">
                    <label className="flex items-start gap-2.5 cursor-pointer font-tech text-xs">
                      <input
                        type="checkbox"
                        checked={termsAccepted}
                        onChange={(e) => setTermsAccepted(e.target.checked)}
                        className="mt-0.5 h-4 w-4 rounded border-line text-indigo focus:ring-indigo"
                      />
                      <span className="text-dim">
                        I understand that <strong className="text-ink">$15.00</strong> will be temporarily held in escrow as a misdeclaration fee. If the physical item matches my declaration upon arrival at the packing dock, the full holdback is released.
                      </span>
                    </label>
                  </div>

                  {/* Submit Button */}
                  <div className="mt-6 flex justify-end">
                    <button
                      onClick={handleStartReturn}
                      disabled={!termsAccepted}
                      className="flex items-center gap-2 rounded-lg bg-indigo px-6 py-3 font-tech text-xs font-semibold uppercase tracking-wider text-white shadow-xs hover:bg-indigo/90 cursor-pointer disabled:opacity-50"
                    >
                      <span>Proceed to Verification ➔</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Order Context Sidebar */}
              <div className="lg:col-span-4 space-y-6">
                <div className="rounded-xl border border-line bg-panel p-6 shadow-xs">
                  <h3 className="font-display text-base font-bold text-ink border-b border-line pb-3">
                    Active Order Item
                  </h3>
                  <div className="mt-4 space-y-3 font-tech text-xs">
                    <div className="flex justify-between">
                      <span className="text-dim">Order Reference:</span>
                      <span className="font-semibold text-ink">{state.order.id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-dim">Item:</span>
                      <span className="font-semibold text-ink">{state.order.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-dim">Original Purchase:</span>
                      <span className="font-bold text-ink">${(state.order.priceMinor / 100).toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between border-t border-line/60 pt-2">
                      <span className="text-dim">Estimated R0 Refund:</span>
                      <span className="font-bold text-ok">
                        ${(state.returnClaim.r0TrancheMinor / 100).toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* STEP 1.5: KEEP-OFFER CARD */}
          {step === "KEEP_OFFER" && (
            <motion.div
              key="step-keep-offer"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              className="mx-auto max-w-[650px] space-y-6"
            >
              <div className="rounded-xl border border-teal/40 bg-panel p-8 shadow-md text-center relative overflow-hidden">
                <div className="absolute -top-12 -right-12 h-36 w-36 rounded-full bg-teal/10 blur-2xl" />

                <div className="inline-grid h-12 w-12 place-items-center rounded-full bg-teal/10 text-teal mb-4">
                  <Gift className="h-6 w-6" />
                </div>

                <h2 className="font-display text-2xl font-bold text-ink">
                  Keep the Item & Get ${keepOfferAmount.toFixed(2)} Cash Instantly
                </h2>

                <p className="mt-2 font-tech text-xs text-dim max-w-[45ch] mx-auto">
                  ProofReturn Keep-Offer (SSOT F-08): Avoid the hassle of boxing and shipping. Accept an immediate $76.00 PayPal refund and keep your headphones.
                </p>

                <div className="my-6 rounded-lg border border-teal/20 bg-teal/[0.04] p-5 font-tech">
                  <div className="text-[10px] uppercase text-teal font-semibold tracking-wider">
                    Instant Credit Value
                  </div>
                  <div className="text-4xl font-bold text-teal mt-1">
                    ${keepOfferAmount.toFixed(2)}
                  </div>
                  <div className="text-[11px] text-faint mt-1">
                    No return shipment needed · Valid for next 24 hours
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row gap-3 justify-center">
                  <button
                    onClick={handleAcceptKeepOffer}
                    className="flex items-center justify-center gap-2 rounded-lg bg-teal px-6 py-3 font-tech text-xs font-semibold uppercase tracking-wider text-white hover:bg-teal/90 shadow-sm cursor-pointer"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Accept ${keepOfferAmount.toFixed(2)} & Keep Item</span>
                  </button>
                  <button
                    onClick={handleDeclineKeepOffer}
                    className="flex items-center justify-center gap-2 rounded-lg border border-line bg-paper px-6 py-3 font-tech text-xs font-semibold text-dim hover:text-ink cursor-pointer"
                  >
                    <span>No, Proceed with Return ➔</span>
                  </button>
                </div>
              </div>
            </motion.div>
          )}

          {/* STEP 2: EVIDENCE CAPTURE (30s FORENSIC CHALLENGE) */}
          {step === "EVIDENCE" && (
            <motion.div
              key="step-evidence"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="mx-auto max-w-[750px] space-y-6"
            >
              <div className="rounded-xl border border-line bg-panel p-6 shadow-xs">
                <div className="flex items-center justify-between border-b border-line pb-4">
                  <div className="flex items-center gap-2">
                    <Camera className="h-4 w-4 text-indigo" />
                    <h2 className="font-display text-base font-bold text-ink">
                      30-Second Forensic Photo Challenge (SSOT F-03)
                    </h2>
                  </div>

                  {/* Countdown Timer */}
                  <div className="flex items-center gap-1.5 rounded-full border border-sig/40 bg-sig/10 px-3 py-1 font-tech text-xs font-bold text-sig">
                    <Clock className="h-3.5 w-3.5 animate-pulse" />
                    <span>{timeLeft}s REMAINING</span>
                  </div>
                </div>

                {/* Simulated Camera Viewfinder */}
                <div className="mt-6 relative aspect-video w-full rounded-lg border-2 border-dashed border-line bg-neutral-900 flex flex-col items-center justify-center overflow-hidden">
                  {/* Privacy shield watermark */}
                  <div className="absolute top-3 left-3 flex items-center gap-1.5 rounded bg-black/60 px-2 py-1 font-tech text-[9px] text-emerald-400">
                    <Lock className="h-3 w-3" />
                    CLIENT PRIVACY SHIELD: FACES & BG BLURRED
                  </div>

                  {/* Challenge Nonce overlay */}
                  <div className="absolute top-3 right-3 font-mono text-[9px] text-neutral-400 bg-black/60 px-2 py-1 rounded">
                    CHALLENGE: NONCE-PROOFRTN-92
                  </div>

                  {/* Viewfinder Reticle */}
                  <div className="relative h-48 w-48 border border-white/20 rounded-lg flex items-center justify-center">
                    <div className="absolute inset-0 border-t-2 border-b-2 border-indigo/60" />
                    <div className="font-tech text-[10px] text-white/50 text-center px-4">
                      {photoCaptured ? (
                        <div className="text-emerald-400 font-semibold flex flex-col items-center gap-2">
                          <CheckCircle2 className="h-8 w-8" />
                          <span>FORENSIC PHOTO MATCHED</span>
                        </div>
                      ) : (
                        "Align Product & Tamper Seal Inside Box"
                      )}
                    </div>
                  </div>

                  {photoCaptured && (
                    <div className="absolute bottom-3 inset-x-3 rounded bg-black/80 p-2 font-mono text-[9px] text-emerald-300 break-all text-center">
                      SHA256: {generatedHash}
                    </div>
                  )}
                </div>

                <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
                  <p className="font-tech text-xs text-dim">
                    Anti-Replay Security: Photo must be taken live within the 30s challenge window.
                  </p>

                  <div className="flex gap-2 w-full sm:w-auto">
                    {!photoCaptured ? (
                      <button
                        onClick={handleCapturePhoto}
                        disabled={isCapturing || timeLeft === 0}
                        className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-lg bg-indigo px-6 py-3 font-tech text-xs font-semibold uppercase tracking-wider text-white hover:bg-indigo/90 cursor-pointer disabled:opacity-50"
                      >
                        <Camera className="h-4 w-4" />
                        <span>{isCapturing ? "Analyzing Frame..." : "Capture Photo Proof"}</span>
                      </button>
                    ) : (
                      <button
                        onClick={handleFinalizeSettlement}
                        className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-lg bg-ok px-6 py-3 font-tech text-xs font-semibold uppercase tracking-wider text-white hover:bg-ok/90 cursor-pointer"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        <span>Confirm & Release R0 Refund ➔</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* STEP 3: DECISION & INSTANT R0 SETTLEMENT */}
          {step === "DECISION" && (
            <motion.div
              key="step-decision"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              className="grid grid-cols-1 lg:grid-cols-12 gap-8"
            >
              <div className="lg:col-span-8 space-y-6">
                <div className="rounded-xl border border-ok/40 bg-panel p-6 shadow-sm">
                  <div className="flex items-center justify-between border-b border-line pb-4">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-5 w-5 text-ok" />
                      <h2 className="font-display text-lg font-bold text-ink">
                        Refund Decision: Fast-Lane Approved (R0 Instant)
                      </h2>
                    </div>
                    <span className="rounded-full border border-ok/40 bg-ok/10 px-3 py-0.5 font-tech text-[10px] font-bold text-ok uppercase">
                      SETTLED TO PAYPAL
                    </span>
                  </div>

                  {/* Tranche Breakdown */}
                  <div className="mt-6 space-y-3 font-tech">
                    <div className="rounded-lg border border-ok/30 bg-ok/[0.04] p-4 flex items-center justify-between">
                      <div>
                        <div className="text-xs font-bold text-ink">
                          Tranche 1: Instant Liquid Release (R0)
                        </div>
                        <div className="text-[11px] text-faint">
                          Immediate transfer to your funding account
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-xl font-bold text-ok">
                          +${(state.returnClaim.r0TrancheMinor / 100).toFixed(2)}
                        </div>
                        <span className="text-[9px] uppercase tracking-wider text-ok font-semibold">
                          PAID INSTANTLY
                        </span>
                      </div>
                    </div>

                    <div className="rounded-lg border border-line bg-paper p-4 flex items-center justify-between">
                      <div>
                        <div className="text-xs font-bold text-ink">
                          Tranche 2: Misdeclaration Escrow Holdback
                        </div>
                        <div className="text-[11px] text-faint">
                          Released when physical box arrives at dock
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-base font-semibold text-sig">
                          ${(state.returnClaim.holdbackMinor / 100).toFixed(2)}
                        </div>
                        <span className="text-[9px] uppercase tracking-wider text-faint">
                          IN ESCROW
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Plain Language Explanation */}
                  <div className="mt-6 rounded-lg border border-line bg-paper p-4 font-tech text-xs">
                    <span className="text-[10px] uppercase font-bold text-dim block mb-1">
                      Decision Rationale:
                    </span>
                    <p className="text-ink">
                      {state.returnClaim.plainLanguageExplanation}
                    </p>
                  </div>

                  {/* Shipping Barcode Simulation */}
                  <div className="mt-6 border-t border-line pt-6">
                    <div className="flex items-center justify-between">
                      <span className="font-display text-sm font-bold text-ink">
                        Prepaid Return Carrier Label
                      </span>
                      <button
                        onClick={() => window.print()}
                        className="flex items-center gap-1 rounded border border-line bg-panel px-3 py-1 font-tech text-xs text-dim hover:text-ink cursor-pointer"
                      >
                        <FileText className="h-3 w-3" />
                        <span>Print Shipping Slip</span>
                      </button>
                    </div>

                    <div className="mt-3 rounded-lg border border-dashed border-line bg-paper p-5 flex flex-col sm:flex-row items-center justify-between gap-4 font-tech">
                      <div>
                        <div className="text-xs font-bold text-ink">TRACKING: PR-9400-8831-US</div>
                        <div className="text-[11px] text-dim mt-0.5">Carrier: Express Priority Return</div>
                        <div className="text-[10px] text-faint mt-1">Free 5-day dropoff at any certified postal station</div>
                      </div>
                      <div className="grid h-16 w-16 place-items-center rounded border border-line bg-white">
                        <QrCode className="h-12 w-12 text-ink" />
                      </div>
                    </div>
                  </div>

                  {/* Free Cancellation per FR-88 */}
                  <div className="mt-6 flex items-center justify-between border-t border-line pt-4 font-tech text-xs">
                    <button
                      onClick={() => {
                        cancelReturn();
                        setStep("DECLARATION");
                      }}
                      className="text-bad hover:underline cursor-pointer flex items-center gap-1"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      <span>Cancel Return (Free per FR-88)</span>
                    </button>

                    <Link
                      href="/packing"
                      className="inline-flex items-center gap-1.5 rounded-lg bg-teal px-4 py-2 font-semibold text-white hover:bg-teal/90 cursor-pointer"
                    >
                      <span>Simulate Inbound Dock Arrival ➔</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                </div>
              </div>

              {/* Sidebar */}
              <div className="lg:col-span-4 space-y-6">
                <div className="rounded-xl border border-line bg-panel p-6 shadow-xs">
                  <h3 className="font-display text-base font-bold text-ink border-b border-line pb-3">
                    Cryptographic Receipt
                  </h3>
                  <div className="mt-4 space-y-3 font-tech text-xs divide-y divide-line/60">
                    <div className="flex justify-between pt-2">
                      <span className="text-dim">Receipt Hash:</span>
                      <span className="font-mono text-[10px] text-ink">0x7f2a...88e1</span>
                    </div>
                    <div className="flex justify-between pt-2">
                      <span className="text-dim">Payer:</span>
                      <span className="font-semibold text-ink">ProofReturn Liquidity Pool</span>
                    </div>
                    <div className="flex justify-between pt-2">
                      <span className="text-dim">Net Issued:</span>
                      <span className="font-bold text-ok">
                        ${(state.returnClaim.r0TrancheMinor / 100).toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {step === "SETTLED" && (
            <motion.div
              key="step-settled"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="mx-auto max-w-[600px] text-center rounded-xl border border-teal/30 bg-panel p-8 shadow-xs"
            >
              <CheckCircle2 className="mx-auto h-12 w-12 text-teal" />
              <h2 className="mt-4 font-display text-2xl font-bold text-ink">
                Transaction Completed
              </h2>
              <p className="mt-2 font-tech text-xs text-dim">
                The keep-offer has been disbursed to your account. No further actions required.
              </p>
              <button
                onClick={() => setStep("DECLARATION")}
                className="mt-6 rounded-lg border border-line bg-paper px-4 py-2 font-tech text-xs text-ink hover:border-dim cursor-pointer"
              >
                Start New Return
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
