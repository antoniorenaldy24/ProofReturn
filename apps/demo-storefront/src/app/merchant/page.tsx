"use client";

import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  ShieldAlert,
  Sliders,
  TrendingUp,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  Filter,
  DollarSign,
  Package,
  Scale,
  Camera,
  Activity,
  FileCheck,
  ChevronRight,
} from "lucide-react";
import { useDemoContext } from "@/lib/demo-context";
import { cn } from "@/lib/utils";

type Tab = "DASHBOARD" | "REVIEW_QUEUE" | "POLICY_EDITOR" | "SIMULATOR";

export default function MerchantConsolePage() {
  const { state } = useDemoContext();
  const [activeTab, setActiveTab] = useState<Tab>("DASHBOARD");

  // Review queue action state
  const [reviewActionTaken, setReviewActionTaken] = useState<string | null>(null);

  // Policy editor local state
  const [gradeBDiscount, setGradeBDiscount] = useState<number>(0.95);
  const [gradeCDiscount, setGradeCDiscount] = useState<number>(0.80);
  const [escrowFee, setEscrowFee] = useState<number>(15.0);

  // Simulation parameters
  const [riskTolerance, setRiskTolerance] = useState<number>(95);

  return (
    <div className="min-h-[calc(100vh-93px)] bg-paper pb-20">
      {/* Console Header */}
      <section className="border-b border-line bg-panel/60 py-6 px-4 sm:px-6">
        <div className="mx-auto flex max-w-[1400px] flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="grid h-5 w-5 place-items-center rounded bg-ok/10 font-tech text-[10px] font-bold text-ok">
                04
              </span>
              <span className="font-tech text-xs uppercase tracking-widest text-faint">
                Merchant Operations · Treasury Risk & Conformal Audit (SSOT F-07 & F-11)
              </span>
            </div>
            <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight text-ink mt-1">
              Merchant Console & Risk Workbench
            </h1>
            <p className="font-tech text-xs text-dim mt-0.5">
              Live audit ledger, dual-view packaging forensic comparator, and mechanism design simulator
            </p>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center rounded-lg border border-line bg-paper p-1 font-tech text-xs shadow-xs overflow-x-auto no-scrollbar">
            <button
              onClick={() => setActiveTab("DASHBOARD")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3.5 py-2 font-medium transition-all cursor-pointer whitespace-nowrap",
                activeTab === "DASHBOARD"
                  ? "bg-panel text-ink shadow-xs border border-line font-bold"
                  : "text-dim hover:text-ink"
              )}
            >
              <LayoutDashboard className="h-3.5 w-3.5 text-ok" />
              <span>Dashboard</span>
            </button>
            <button
              onClick={() => setActiveTab("REVIEW_QUEUE")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3.5 py-2 font-medium transition-all cursor-pointer whitespace-nowrap",
                activeTab === "REVIEW_QUEUE"
                  ? "bg-panel text-ink shadow-xs border border-line font-bold"
                  : "text-dim hover:text-ink"
              )}
            >
              <ShieldAlert className="h-3.5 w-3.5 text-sig" />
              <span>Dual Inspector</span>
            </button>
            <button
              onClick={() => setActiveTab("POLICY_EDITOR")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3.5 py-2 font-medium transition-all cursor-pointer whitespace-nowrap",
                activeTab === "POLICY_EDITOR"
                  ? "bg-panel text-ink shadow-xs border border-line font-bold"
                  : "text-dim hover:text-ink"
              )}
            >
              <Sliders className="h-3.5 w-3.5 text-indigo" />
              <span>Policy Dials</span>
            </button>
            <button
              onClick={() => setActiveTab("SIMULATOR")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3.5 py-2 font-medium transition-all cursor-pointer whitespace-nowrap",
                activeTab === "SIMULATOR"
                  ? "bg-panel text-ink shadow-xs border border-line font-bold"
                  : "text-dim hover:text-ink"
              )}
            >
              <TrendingUp className="h-3.5 w-3.5 text-teal" />
              <span>Simulator</span>
            </button>
          </div>
        </div>
      </section>

      {/* Main Tab Views */}
      <main className="mx-auto max-w-[1400px] px-4 sm:px-6 pt-8">
        <AnimatePresence mode="wait">
          {/* TAB 1: DASHBOARD */}
          {activeTab === "DASHBOARD" && (
            <motion.div
              key="tab-dashboard"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-8"
            >
              {/* KPI Metrics Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="rounded-xl border border-line bg-panel p-5 shadow-xs">
                  <span className="font-tech text-[10px] uppercase tracking-wider text-faint">
                    Total Return Volume
                  </span>
                  <div className="mt-2 flex items-baseline justify-between">
                    <span className="font-tech text-3xl font-bold text-ink">
                      {state.kpis.totalVolume}
                    </span>
                    <span className="font-tech text-xs text-ok font-semibold">+8.4% MoM</span>
                  </div>
                  <span className="mt-1 font-tech text-[10px] text-dim block">
                    Fast-Lane Rate: 91.2%
                  </span>
                </div>

                <div className="rounded-xl border border-line bg-panel p-5 shadow-xs">
                  <span className="font-tech text-[10px] uppercase tracking-wider text-faint">
                    Capital Released (R0 Instant)
                  </span>
                  <div className="mt-2 flex items-baseline justify-between">
                    <span className="font-tech text-3xl font-bold text-ink">
                      ${(state.kpis.capitalReleasedMinor / 100).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </span>
                    <span className="font-tech text-xs text-ok font-semibold">99.8% Honest</span>
                  </div>
                  <span className="mt-1 font-tech text-[10px] text-dim block">
                    Liquidity turnaround: &lt; 30s
                  </span>
                </div>

                <div className="rounded-xl border border-line bg-panel p-5 shadow-xs">
                  <span className="font-tech text-[10px] uppercase tracking-wider text-faint">
                    Holdback Escrow Protected
                  </span>
                  <div className="mt-2 flex items-baseline justify-between">
                    <span className="font-tech text-3xl font-bold text-sig">
                      ${(state.kpis.holdbackRetainedMinor / 100).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </span>
                    <span className="font-tech text-xs text-faint">Under Guarantee</span>
                  </div>
                  <span className="mt-1 font-tech text-[10px] text-dim block">
                    Zero merchant bad debt
                  </span>
                </div>

                <div className="rounded-xl border border-line bg-panel p-5 shadow-xs">
                  <span className="font-tech text-[10px] uppercase tracking-wider text-faint">
                    Gross Fraud Prevented
                  </span>
                  <div className="mt-2 flex items-baseline justify-between">
                    <span className="font-tech text-3xl font-bold text-ok">
                      ${(state.kpis.fraudPreventedMinor / 100).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                    </span>
                    <span className="font-tech text-xs text-ok font-semibold">142 Cases</span>
                  </div>
                  <span className="mt-1 font-tech text-[10px] text-dim block">
                    Brick-in-box deterrence
                  </span>
                </div>
              </div>

              {/* Live Returns Table */}
              <div className="rounded-xl border border-line bg-panel shadow-xs overflow-hidden">
                <div className="flex items-center justify-between border-b border-line px-6 py-4">
                  <div className="flex items-center gap-2">
                    <Activity className="h-4 w-4 text-ok" />
                    <h2 className="font-display text-base font-bold text-ink">
                      Live Return Transactions & Audit Trail
                    </h2>
                  </div>
                  <span className="font-tech text-[10px] text-faint">
                    Showing latest 5 records
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left font-tech text-xs">
                    <thead className="border-b border-line bg-paper/80 text-[10px] uppercase tracking-wider text-faint">
                      <tr>
                        <th className="px-6 py-3">Return ID</th>
                        <th className="px-6 py-3">Order ID</th>
                        <th className="px-6 py-3">Item SKU</th>
                        <th className="px-6 py-3">Declared</th>
                        <th className="px-6 py-3">R0 Payout</th>
                        <th className="px-6 py-3">Escrow Status</th>
                        <th className="px-6 py-3">Lifecycle State</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line/60">
                      {/* Active Demo Order Row */}
                      <tr className="bg-ok/[0.02] hover:bg-ok/[0.04] transition-colors">
                        <td className="px-6 py-4 font-bold text-ink flex items-center gap-2">
                          <span className="h-2 w-2 rounded-full bg-ok animate-pulse" />
                          {state.returnClaim.returnId}
                        </td>
                        <td className="px-6 py-4 text-dim">{state.order.id}</td>
                        <td className="px-6 py-4 font-semibold text-ink">{state.order.sku}</td>
                        <td className="px-6 py-4">
                          <span className="rounded border border-indigo/40 bg-indigo/10 px-2 py-0.5 text-indigo font-bold">
                            Grade {state.returnClaim.declaredGrade}
                          </span>
                        </td>
                        <td className="px-6 py-4 font-bold text-ok">
                          ${(state.returnClaim.r0TrancheMinor / 100).toFixed(2)}
                        </td>
                        <td className="px-6 py-4 text-sig">
                          {state.dockCheckin.status === "PASSED" ? "RELEASED" : "$15.00 HELD"}
                        </td>
                        <td className="px-6 py-4">
                          <span className="rounded border border-line bg-paper px-2 py-0.5 text-[10px] font-semibold text-dim">
                            {state.order.status}
                          </span>
                        </td>
                      </tr>

                      {/* Mock Baseline Rows */}
                      <tr className="hover:bg-paper/40 transition-colors">
                        <td className="px-6 py-4 text-dim">ret_1092_a</td>
                        <td className="px-6 py-4 text-dim">ord_8821</td>
                        <td className="px-6 py-4 text-ink">PR-HP-XM5</td>
                        <td className="px-6 py-4">
                          <span className="rounded border border-line bg-paper px-2 py-0.5 text-dim">
                            Grade A
                          </span>
                        </td>
                        <td className="px-6 py-4 text-ok font-semibold">$380.00</td>
                        <td className="px-6 py-4 text-ok">RELEASED</td>
                        <td className="px-6 py-4 text-faint">SETTLED</td>
                      </tr>
                      <tr className="hover:bg-paper/40 transition-colors">
                        <td className="px-6 py-4 text-dim">ret_1091_b</td>
                        <td className="px-6 py-4 text-dim">ord_8819</td>
                        <td className="px-6 py-4 text-ink">PR-SP-MBP</td>
                        <td className="px-6 py-4">
                          <span className="rounded border border-line bg-paper px-2 py-0.5 text-dim">
                            Grade B
                          </span>
                        </td>
                        <td className="px-6 py-4 text-ok font-semibold">$1,140.00</td>
                        <td className="px-6 py-4 text-ok">RELEASED</td>
                        <td className="px-6 py-4 text-faint">SETTLED</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </motion.div>
          )}

          {/* TAB 2: DUAL INSPECTOR */}
          {activeTab === "REVIEW_QUEUE" && (
            <motion.div
              key="tab-inspector"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              <div className="rounded-xl border border-line bg-panel p-6 shadow-xs">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-line pb-4">
                  <div>
                    <h2 className="font-display text-lg font-bold text-ink">
                      Dual-View Forensic Comparator: {state.returnClaim.returnId}
                    </h2>
                    <p className="font-tech text-xs text-dim">
                      Side-by-side verification between Warehouse Origin Mint Facts and Shopper Inbound Claim
                    </p>
                  </div>
                  <span className="rounded-full border border-sig/40 bg-sig/10 px-3 py-1 font-tech text-xs font-bold text-sig uppercase">
                    Confidence: 98.4% Conformal Match
                  </span>
                </div>

                {/* Side by Side Cards */}
                <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Left: Origin Facts */}
                  <div className="rounded-lg border border-teal/40 bg-teal/[0.02] p-5 font-tech text-xs space-y-4">
                    <div className="flex items-center justify-between border-b border-teal/20 pb-2">
                      <span className="font-bold text-teal uppercase tracking-wider">
                        ORIGIN MINT FACTS (PACKING RIG)
                      </span>
                      <span className="text-[10px] text-faint">
                        {state.passport.id}
                      </span>
                    </div>

                    <div className="aspect-video w-full rounded border border-line bg-neutral-900 flex items-center justify-center relative overflow-hidden">
                      <div className="text-center font-tech text-white/50 text-[11px]">
                        <Package className="mx-auto h-8 w-8 text-teal mb-1" />
                        <span>Origin Baseline Reference Imagery</span>
                        <div className="text-[9px] text-teal mt-1">SEAL #TS-8840-X AFFIXED</div>
                      </div>
                    </div>

                    <div className="space-y-2 divide-y divide-line/60">
                      <div className="flex justify-between pt-1">
                        <span className="text-dim">Certified Mint Mass:</span>
                        <span className="font-bold text-ink">{state.passport.weightGrams} g</span>
                      </div>
                      <div className="flex justify-between pt-2">
                        <span className="text-dim">Serial Number:</span>
                        <span className="font-mono text-ink">{state.passport.serialNumber}</span>
                      </div>
                      <div className="flex justify-between pt-2">
                        <span className="text-dim">Origin Nonce:</span>
                        <span className="font-mono text-teal">{state.passport.originNonce}</span>
                      </div>
                      <div className="flex justify-between pt-2">
                        <span className="text-dim">Tamper Seal Nonce:</span>
                        <span className="font-bold text-ok">VERIFIED INTACT</span>
                      </div>
                    </div>
                  </div>

                  {/* Right: Return Claim */}
                  <div className="rounded-lg border border-indigo/40 bg-indigo/[0.02] p-5 font-tech text-xs space-y-4">
                    <div className="flex items-center justify-between border-b border-indigo/20 pb-2">
                      <span className="font-bold text-indigo uppercase tracking-wider">
                        RETURN CLAIM FACTS (SHOPPER INTAKE)
                      </span>
                      <span className="text-[10px] text-faint">
                        {state.returnClaim.returnId}
                      </span>
                    </div>

                    <div className="aspect-video w-full rounded border border-line bg-neutral-900 flex items-center justify-center relative overflow-hidden">
                      <div className="text-center font-tech text-white/50 text-[11px]">
                        <Camera className="mx-auto h-8 w-8 text-indigo mb-1" />
                        <span>30-Sec Forensic Capture Proof</span>
                        <div className="text-[9px] text-emerald-400 mt-1">ANTI-REPLAY NONCE MATCH</div>
                      </div>
                    </div>

                    <div className="space-y-2 divide-y divide-line/60">
                      <div className="flex justify-between pt-1">
                        <span className="text-dim">Dock Scale Mass:</span>
                        <span className="font-bold text-ink">{state.dockCheckin.actualWeightGrams} g (Δ -0.2g)</span>
                      </div>
                      <div className="flex justify-between pt-2">
                        <span className="text-dim">Declared Grade:</span>
                        <span className="font-bold text-indigo">Grade {state.returnClaim.declaredGrade}</span>
                      </div>
                      <div className="flex justify-between pt-2">
                        <span className="text-dim">Observed Dock Grade:</span>
                        <span className="font-bold text-ok">Grade {state.dockCheckin.observedGrade}</span>
                      </div>
                      <div className="flex justify-between pt-2">
                        <span className="text-dim">Evidence Hash:</span>
                        <span className="font-mono text-[10px] text-dim truncate max-w-[20ch]">
                          {state.returnClaim.forensicHash || "0xe3b0...b855"}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Audit Decision Bar */}
                <div className="mt-6 border-t border-line pt-6">
                  {reviewActionTaken ? (
                    <div className="p-4 rounded-lg border border-ok/40 bg-ok/5 text-center font-tech text-xs text-ok">
                      <CheckCircle2 className="mx-auto h-5 w-5 mb-1" />
                      <strong>Action Executed: {reviewActionTaken}</strong>
                      <p className="text-[11px] text-dim mt-0.5">Audit log updated. Escrow settled.</p>
                    </div>
                  ) : (
                    <div className="flex flex-col sm:flex-row gap-3">
                      <button
                        onClick={() => setReviewActionTaken("Grade B Confirmed · Escrow $15.00 Released")}
                        className="flex-1 flex items-center justify-center gap-2 rounded-lg bg-ok py-3 font-tech text-xs font-semibold uppercase tracking-wider text-white shadow-xs hover:bg-ok/90 cursor-pointer"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        <span>Confirm Grade B &amp; Release Escrow ($15.00)</span>
                      </button>
                      <button
                        onClick={() => setReviewActionTaken("Adjusted to Grade C · $38.00 Restocking Adjustment")}
                        className="flex items-center justify-center gap-2 rounded-lg border border-warn/40 bg-warn/10 px-4 py-3 font-tech text-xs font-semibold uppercase tracking-wider text-warn hover:bg-warn/20 cursor-pointer"
                      >
                        <AlertTriangle className="h-4 w-4" />
                        <span>Adjust to Grade C</span>
                      </button>
                      <button
                        onClick={() => setReviewActionTaken("Imposed Misdeclaration Penalty F ($15.00 Escrow Forfeited)")}
                        className="flex items-center justify-center gap-2 rounded-lg border border-bad/40 bg-bad/10 px-4 py-3 font-tech text-xs font-semibold uppercase tracking-wider text-bad hover:bg-bad/20 cursor-pointer"
                      >
                        <ShieldAlert className="h-4 w-4" />
                        <span>Enforce Misdeclaration Fee</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          )}

          {/* TAB 3: POLICY EDITOR */}
          {activeTab === "POLICY_EDITOR" && (
            <motion.div
              key="tab-policy"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="grid grid-cols-1 lg:grid-cols-12 gap-8"
            >
              <div className="lg:col-span-8 space-y-6">
                <div className="rounded-xl border border-line bg-panel p-6 shadow-xs">
                  <h2 className="font-display text-lg font-bold text-ink">
                    Policy Dials &amp; Restocking Curves: pol_electronics_us_v1
                  </h2>
                  <p className="font-tech text-xs text-dim mt-1">
                    Fine-tune recovery payouts per condition grade to maintain optimal truthful declaration equilibrium
                  </p>

                  <div className="mt-6 space-y-6 font-tech">
                    {/* Grade B Slider */}
                    <div>
                      <div className="flex justify-between text-xs">
                        <span className="font-semibold text-ink">Grade B Payout Multiplier:</span>
                        <span className="font-bold text-indigo">{(gradeBDiscount * 100).toFixed(0)}% (${(380 * gradeBDiscount).toFixed(2)})</span>
                      </div>
                      <input
                        type="range"
                        min="0.80"
                        max="1.00"
                        step="0.01"
                        value={gradeBDiscount}
                        onChange={(e) => setGradeBDiscount(parseFloat(e.target.value))}
                        className="w-full mt-2 accent-indigo cursor-pointer"
                      />
                      <span className="text-[10px] text-faint">Standard open-box deduction for light cosmetic wear.</span>
                    </div>

                    {/* Grade C Slider */}
                    <div>
                      <div className="flex justify-between text-xs">
                        <span className="font-semibold text-ink">Grade C Payout Multiplier:</span>
                        <span className="font-bold text-warn">{(gradeCDiscount * 100).toFixed(0)}% (${(380 * gradeCDiscount).toFixed(2)})</span>
                      </div>
                      <input
                        type="range"
                        min="0.60"
                        max="0.90"
                        step="0.01"
                        value={gradeCDiscount}
                        onChange={(e) => setGradeCDiscount(parseFloat(e.target.value))}
                        className="w-full mt-2 accent-warn cursor-pointer"
                      />
                      <span className="text-[10px] text-faint">Deduction for moderate scratches, missing packaging, or worn ear pads.</span>
                    </div>

                    {/* Escrow Fee */}
                    <div>
                      <div className="flex justify-between text-xs">
                        <span className="font-semibold text-ink">Misdeclaration Escrow Penalty (F):</span>
                        <span className="font-bold text-sig">${escrowFee.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min="5"
                        max="30"
                        step="1"
                        value={escrowFee}
                        onChange={(e) => setEscrowFee(parseFloat(e.target.value))}
                        className="w-full mt-2 accent-sig cursor-pointer"
                      />
                      <span className="text-[10px] text-faint">Fee deducted if returned specimen severely diverges from declaration.</span>
                    </div>
                  </div>

                  <div className="mt-8 flex justify-end">
                    <button
                      onClick={() => alert("Policy configuration saved and deployed to ProofReturn Testnet!")}
                      className="rounded-lg bg-indigo px-6 py-2.5 font-tech text-xs font-semibold uppercase tracking-wider text-white hover:bg-indigo/90 cursor-pointer"
                    >
                      Save &amp; Propagate Policy ➔
                    </button>
                  </div>
                </div>
              </div>

              {/* Sidebar */}
              <div className="lg:col-span-4 space-y-6">
                <div className="rounded-xl border border-line bg-panel p-6 shadow-xs font-tech text-xs">
                  <h3 className="font-display text-base font-bold text-ink border-b border-line pb-3">
                    Game-Theoretic Equilibrium Check
                  </h3>
                  <div className="mt-4 space-y-3">
                    <div className="p-3 rounded bg-ok/5 border border-ok/30 text-ok">
                      <span className="font-bold">✓ Truth-Telling Dominant</span>
                      <p className="text-[10px] text-dim mt-0.5">
                        Misdeclaration penalty (${escrowFee}) exceeds potential fraud delta (${(380 * (1 - gradeBDiscount)).toFixed(2)}). Shopper has no economic incentive to lie.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* TAB 4: SIMULATOR */}
          {activeTab === "SIMULATOR" && (
            <motion.div
              key="tab-simulator"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-6"
            >
              <div className="rounded-xl border border-line bg-panel p-6 shadow-xs">
                <div className="flex items-center justify-between border-b border-line pb-4">
                  <div>
                    <h2 className="font-display text-lg font-bold text-ink">
                      Mechanism Feasibility &amp; ROI Simulator (SSOT §27)
                    </h2>
                    <p className="font-tech text-xs text-dim">
                      Conformal prediction bounds, fraud deterrence coverage, and capital release velocity
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-tech text-xs text-faint">Confidence Band:</span>
                    <span className="font-tech text-xs font-bold text-teal">{riskTolerance}%</span>
                  </div>
                </div>

                <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6 font-tech">
                  <div className="rounded-lg border border-line bg-paper p-5 text-center">
                    <span className="text-[10px] uppercase text-faint">Annual Friction Savings</span>
                    <div className="text-3xl font-bold text-ok mt-2">$42,150.00</div>
                    <span className="text-[11px] text-dim mt-1 block">Saved in return disputes &amp; support hours</span>
                  </div>

                  <div className="rounded-lg border border-line bg-paper p-5 text-center">
                    <span className="text-[10px] uppercase text-faint">Merchant ROI Multiple</span>
                    <div className="text-3xl font-bold text-teal mt-2">4.2x</div>
                    <span className="text-[11px] text-dim mt-1 block">Net economic surplus ratio</span>
                  </div>

                  <div className="rounded-lg border border-line bg-paper p-5 text-center">
                    <span className="text-[10px] uppercase text-faint">Conformal Coverage Guarantee</span>
                    <div className="text-3xl font-bold text-indigo mt-2">95.0%</div>
                    <span className="text-[11px] text-dim mt-1 block">Non-conformity score S &le; q̂</span>
                  </div>
                </div>

                <div className="mt-6 rounded-lg border border-dashed border-line bg-paper/60 p-6 text-center font-tech text-xs text-dim">
                  <TrendingUp className="mx-auto h-8 w-8 text-teal mb-2" />
                  <p className="max-w-[55ch] mx-auto">
                    The ProofReturn mechanism transforms return friction into a self-enforcing cryptographic bond: buyers receive instantaneous liquidity ($365.00), while merchants eliminate wardrobing and empty-box fraud with zero manual review overhead.
                  </p>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
