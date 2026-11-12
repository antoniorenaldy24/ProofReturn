"use client";

import { useEffect, useState } from "react";
import { PlateFrame } from "@/components/ornament/plate-frame";
import { MicrotextStrip, Rule, Stamp } from "@/components/ornament/ornaments";
import { Odometer } from "@/components/circ/odometer";
import { TransferRoom } from "@/components/checkout/transfer-room";
import { CHECKOUT, CIRC_GRADES, formatUSD, PRODUCT } from "@/lib/data";
import { useLedger } from "@/lib/store";
import { cn } from "@/lib/utils";

/**
 * PLATE IV — THE COUNTING HOUSE.
 * The cart as a ledger entry: receipt with the curve printed on it,
 * Fast-Lane eligibility fed by the passport, and a simulated transfer.
 */
export function LedgerPlate() {
  const qty = useLedger((s) => s.qty);
  const setQty = useLedger((s) => s.setQty);
  const removeFromLedger = useLedger((s) => s.removeFromLedger);
  const passportVerified = useLedger((s) => s.passportVerified);
  const lastOrder = useLedger((s) => s.lastOrder);

  const [roomOpen, setRoomOpen] = useState(false);
  // Date is computed lazily; hydration text may differ and is intentionally unsuppressed-critical.
  const [today] = useState(() => new Date().toLocaleDateString("en-US", { dateStyle: "long" }));

  const subtotal = PRODUCT.msrp * qty;
  const total = subtotal + CHECKOUT.tax;

  const fastLane = [
    { key: "passport", label: CHECKOUT.fastLaneRules[0].label, ok: passportVerified, fix: "#passport" },
    { key: "grade", label: CHECKOUT.fastLaneRules[1].label, ok: true, fix: null },
    { key: "value", label: CHECKOUT.fastLaneRules[2].label, ok: subtotal >= 250, fix: "#object" },
  ];
  const eligible = fastLane.every((r) => r.ok);

  return (
    <PlateFrame
      id="counting-house"
      numeral="IV"
      title="The Counting House"
      kicker="Plate IV — Ledger, Fast-Lane & simulated checkout"
    >
      <div className="grid gap-10 lg:grid-cols-2 lg:gap-12">
        {/* ——— The receipt ——— */}
        <div data-reveal className="perf-top relative border border-ink/70 bg-sheet shadow-[6px_6px_0_rgba(34,29,18,0.12)]">
          <div className="border-b border-ink/50 px-6 pb-4 pt-7 text-center">
            <p className="engraved text-2xl font-semibold uppercase tracking-[0.06em] text-ink">ProofReturn</p>
            <p className="mt-1 font-ledger text-[8.5px] uppercase tracking-[0.3em] text-ink-soft">
              Counting house · ledger entry {lastOrder ? `· last: ${lastOrder.ref}` : "— open"}
            </p>
            <p className="mt-0.5 font-ledger text-[8.5px] uppercase tracking-[0.24em] text-ink-soft">{today || "…"}</p>
          </div>

          {qty === 0 ? (
            <div className="flex flex-col items-center px-6 py-12 text-center">
              <p className="engraved-text text-lg italic text-ink-soft">Your ledger is blank.</p>
              <p className="mt-2 max-w-[36ch] font-ledger text-[10px] leading-relaxed uppercase tracking-[0.14em] text-ink-soft">
                Stamp the Object in Plate I — its refund curve is printed on this receipt the moment it lands.
              </p>
              <a href="#object" data-cursor="open" className="btn-engraved mt-6">
                Stamp the Object — Plate I
              </a>
            </div>
          ) : (
            <div className="px-6 py-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-ledger text-[12px] font-semibold text-ink">
                    {PRODUCT.name} — {PRODUCT.tagline}
                  </p>
                  <p className="mt-0.5 font-ledger text-[9px] uppercase tracking-[0.18em] text-ink-soft">
                    {PRODUCT.sku} · Grade A origin · Passport PP-2026-0038-A
                  </p>
                </div>
                <p className="shrink-0 font-ledger text-[12px] font-semibold">{formatUSD(PRODUCT.msrp)} / ea</p>
              </div>

              <div className="mt-4 flex items-center justify-between">
                <div className="flex items-center border border-ink" role="group" aria-label="Quantity in ledger">
                  <button
                    onClick={() => setQty(Math.max(1, qty - 1))}
                    className="h-10 w-10 font-ledger text-lg transition-colors hover:bg-paper-3"
                    aria-label="Decrease quantity"
                  >
                    –
                  </button>
                  <span className="w-9 text-center font-ledger text-sm font-semibold" aria-live="polite">
                    {qty}
                  </span>
                  <button
                    onClick={() => setQty(Math.min(3, qty + 1))}
                    className="h-10 w-10 font-ledger text-lg transition-colors hover:bg-paper-3"
                    aria-label="Increase quantity"
                  >
                    +
                  </button>
                </div>
                <button
                  onClick={removeFromLedger}
                  className="font-ledger text-[9px] font-semibold uppercase tracking-[0.18em] text-pr-red underline-offset-4 hover:underline"
                >
                  Strike from ledger
                </button>
              </div>

              <Rule className="my-5" thick={1} />

              <dl>
                <div className="ledger-row">
                  <dt>Subtotal — {qty} × {formatUSD(PRODUCT.msrp)}</dt>
                  <dd>{formatUSD(subtotal)}</dd>
                </div>
                <div className="ledger-row">
                  <dt>Shipping</dt>
                  <dd className="text-pr-green">{CHECKOUT.shipping}</dd>
                </div>
                <div className="ledger-row">
                  <dt>Tax</dt>
                  <dd>{formatUSD(CHECKOUT.tax)} — demo fixture</dd>
                </div>
              </dl>

              <div className="mt-5 flex items-end justify-between border-t-2 border-ink pt-4">
                <p className="font-ledger text-[10px] font-semibold uppercase tracking-[0.26em] text-ink">Total due</p>
                <Odometer value={total} className="text-4xl" />
              </div>

              {/* the curve, printed on the receipt */}
              <div className="mt-5 border border-dashed border-ink/50 bg-paper-2/50 p-3.5">
                <p className="font-ledger text-[8.5px] font-semibold uppercase tracking-[0.24em] text-ink-soft">
                  Refund readiness — printed per unit, per the curve (Plate II)
                </p>
                <div className="mt-2 grid grid-cols-4 gap-1.5">
                  {CIRC_GRADES.map((g) => (
                    <div key={g.grade} className="border border-ink/30 bg-sheet px-1 py-1.5 text-center">
                      <p className="font-ledger text-[8px] uppercase tracking-[0.2em] text-ink-soft">Grade {g.grade}</p>
                      <p className={cn("font-ledger text-[11.5px] font-bold", g.grade === "A" ? "text-pr-green" : "text-ink")}>
                        {formatUSD(g.refund)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-4">
                <MicrotextStrip
                  text="THIS RECEIPT IS A DEMONSTRATION RECORD · NO PURCHASE HAS OCCURRED · SIMULATED CHECKOUT"
                  repeat={22}
                />
              </div>
            </div>
          )}
        </div>

        {/* ——— Fast-Lane + checkout ——— */}
        <div data-reveal data-delay="0.1" className="flex flex-col gap-8">
          <div className="plate-panel p-6 sm:p-7">
            <div className="flex items-center justify-between gap-3">
              <h3 className="engraved text-2xl font-semibold uppercase tracking-tight text-ink">Fast-Lane</h3>
              {eligible ? (
                <Stamp tone="green" rotate={-2.5}>
                  Eligible · demo
                </Stamp>
              ) : (
                <Stamp tone="red" rotate={2}>
                  Pending
                </Stamp>
              )}
            </div>
            <p className="mt-2 font-ledger text-[10px] uppercase leading-relaxed tracking-[0.14em] text-ink-soft">
              One-tap checkout path. Demonstration eligibility model — three checks, all visible.
            </p>
            <ul className="mt-5 space-y-3">
              {fastLane.map((r) => (
                <li key={r.key} className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-3 font-ledger text-[11.5px] text-ink">
                    <span
                      aria-hidden="true"
                      className={cn(
                        "flex h-5 w-5 items-center justify-center border text-[9px]",
                        r.ok ? "border-pr-green bg-pr-green text-sheet" : "border-ink/40 text-transparent",
                      )}
                    >
                      ✓
                    </span>
                    {r.label}
                  </span>
                  {!r.ok && r.fix && (
                    <a
                      href={r.fix}
                      className="font-ledger text-[9px] font-semibold uppercase tracking-[0.16em] text-pr-red underline-offset-4 hover:underline"
                    >
                      {r.key === "passport" ? "Verify — Plate III →" : "Add value — Plate I →"}
                    </a>
                  )}
                </li>
              ))}
            </ul>
            {eligible && (
              <p className="mt-5 border-t border-dashed border-ink/40 pt-4 font-ledger text-[10px] leading-relaxed text-pr-green">
                ✓ Passport verified · Grade A origin · value satisfied — the Fast-Lane is open for this ledger.
              </p>
            )}
          </div>

          <div className="border-[1.5px] border-ink p-6 sm:p-7">
            <h3 className="engraved text-2xl font-semibold uppercase tracking-tight text-ink">Settlement</h3>
            <p className="mt-2 max-w-[42ch] font-ledger text-[11px] leading-relaxed text-ink-soft">
              {CHECKOUT.paypal.disclaimer}
            </p>
            <button
              onClick={() => setRoomOpen(true)}
              disabled={qty === 0}
              data-cursor="open"
              className="btn-engraved btn-engraved-solid mt-6 w-full !py-5 !text-[12px]"
              aria-label="Open the simulated PayPal Sandbox checkout"
            >
              Checkout with PayPal — Sandbox
              <span aria-hidden="true">↗</span>
            </button>
            <p className="mt-3 text-center font-ledger text-[8.5px] uppercase tracking-[0.2em] text-ink-soft">
              Simulated flow · no real payment · no data leaves this browser
            </p>
          </div>

          <div className="border border-dashed border-ink/50 p-5">
            <p className="font-ledger text-[9px] font-semibold uppercase tracking-[0.24em] text-ink-soft">
              What is real in this room
            </p>
            <ul className="mt-3 space-y-1.5 font-ledger text-[10px] leading-relaxed text-ink-soft">
              <li>— Product, prices, grades: local fixtures (demo data).</li>
              <li>— Refund arithmetic: computed live from those fixtures.</li>
              <li>— Passport digest & seal: demonstration strings.</li>
              <li>— Payment: a front-end simulation of the Sandbox experience.</li>
            </ul>
          </div>
        </div>
      </div>

      <TransferRoom open={roomOpen} onOpenChange={setRoomOpen} total={total} qty={qty} />
    </PlateFrame>
  );
}
