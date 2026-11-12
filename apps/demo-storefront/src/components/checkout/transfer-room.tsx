"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Odometer } from "@/components/circ/odometer";
import { Stamp } from "@/components/ornament/ornaments";
import { CHECKOUT, formatUSD } from "@/lib/data";
import { useLedger, type SealedOrder } from "@/lib/store";
import { cn } from "@/lib/utils";

type Phase = "press" | "confirmed";

/**
 * One press run. Mounts inside the dialog (fresh state every time the room
 * opens), runs the simulated PayPal Sandbox sequence, and seals the order.
 */
function TransferRun({
  total,
  qty,
  onClose,
}: {
  total: number;
  qty: number;
  onClose: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("press");
  const [step, setStep] = useState(0);
  const [order, setOrder] = useState<SealedOrder | null>(null);
  const sealOrder = useLedger((s) => s.sealOrder);
  const pushToast = useLedger((s) => s.pushToast);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    // The simulated pressing sequence — each step of the run.
    let acc = 700;
    CHECKOUT.paypal.steps.forEach((_, i) => {
      acc += i === 0 ? 1250 : 1050;
      timers.current.push(window.setTimeout(() => setStep(i + 1), acc));
    });
    timers.current.push(
      window.setTimeout(() => {
        const sealed: SealedOrder = {
          ref: "ord_demo_1",
          tx: `SANDBOX-DEMO-${Date.now().toString(36).toUpperCase()}`,
          sealedAt: new Date().toISOString(),
          total,
        };
        if (typeof window !== "undefined") {
          localStorage.setItem(
            "proofreturn_active_order",
            JSON.stringify({
              order_id: "ord_demo_1",
              passport_id: "pass_demo_1",
              sku: "PR-HP-XM5",
              amount_minor: 38000,
              merchant_id: "merch_a",
              account_id: "shopper_1",
              policy_version: "pol_electronics_us_v1",
              paypal_order_id: sealed.tx,
              sealed_at: sealed.sealedAt,
            })
          );
        }
        setOrder(sealed);
        setPhase("confirmed");
        sealOrder(sealed);
      }, acc + 750),
    );
    const stash = timers.current;
    return () => stash.forEach((t) => window.clearTimeout(t));
  }, [total, sealOrder]);

  const abandon = () => {
    pushToast({ kind: "red", title: "Transfer abandoned", line: "Nothing was charged — simulation only." });
    onClose();
  };

  const done = phase === "confirmed";

  return (
    <AnimatePresence mode="wait">
      {!done ? (
        <motion.div
          key="press"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, y: -8 }}
          className="px-6 py-6"
        >
          <div className="border-b border-dashed border-ink/40 pb-4">
            <p className="font-ledger text-[9px] uppercase tracking-[0.22em] text-ink-soft">
              Authorizing to ProofReturn
            </p>
            <Odometer value={total} className="mt-1.5 text-4xl" />
            <p className="mt-1 font-ledger text-[9px] uppercase tracking-[0.18em] text-ink-soft">
              {qty} × unit · insured shipping · tax {formatUSD(CHECKOUT.tax)}
            </p>
          </div>

          <ol className="mt-5 space-y-4" aria-live="polite">
            {CHECKOUT.paypal.steps.map((s, i) => {
              const state = step > i ? "done" : step === i ? "active" : "waiting";
              return (
                <li key={s.line} className="flex items-center gap-3.5">
                  <span
                    aria-hidden="true"
                    className={cn(
                      "flex h-6 w-6 shrink-0 items-center justify-center border font-ledger text-[10px]",
                      state === "done" && "border-pr-green bg-pr-green text-sheet",
                      state === "active" && "border-pr-green text-pr-green",
                      state === "waiting" && "border-ink/40 text-ink/40",
                    )}
                  >
                    {state === "done" ? "✓" : i + 1}
                  </span>
                  <span
                    className={cn(
                      "font-ledger text-[11.5px] tracking-[0.04em]",
                      state === "waiting" ? "text-ink/40" : "text-ink",
                    )}
                  >
                    {s.line}
                  </span>
                  {state === "active" && (
                    <motion.span
                      aria-hidden="true"
                      className="ml-auto block h-4 w-4 rounded-full border border-dashed border-pr-green"
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1.1, repeat: Infinity, ease: "linear" }}
                    />
                  )}
                </li>
              );
            })}
          </ol>

          <div className="mt-7 flex items-center justify-between border-t border-ink/40 pt-4">
            <button
              onClick={abandon}
              className="font-ledger text-[10px] font-semibold uppercase tracking-[0.2em] text-pr-red underline-offset-4 hover:underline"
            >
              Abandon transfer
            </button>
            <p className="max-w-[24ch] text-right font-ledger text-[8px] uppercase leading-[1.7] tracking-[0.14em] text-ink-soft">
              No PayPal session opens · nothing is charged
            </p>
          </div>
        </motion.div>
      ) : (
        <motion.div
          key="confirmed"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="px-6 py-6"
        >
          <div className="border-[1.5px] border-pr-green bg-sheet p-5 text-center">
            <p className="font-ledger text-[9px] font-semibold uppercase tracking-[0.3em] text-pr-green">
              Payment sealed — order record
            </p>
            <p className="engraved mt-3 text-3xl font-bold text-ink">{order?.ref}</p>
            <dl className="mx-auto mt-4 max-w-[30ch] space-y-1.5 text-left">
              <div className="ledger-row !py-1.5">
                <dt>Sealed at</dt>
                <dd>{order ? new Date(order.sealedAt).toLocaleString() : ""}</dd>
              </div>
              <div className="ledger-row !py-1.5">
                <dt>Sandbox reference</dt>
                <dd className="text-[10px]">{order?.tx}</dd>
              </div>
              <div className="ledger-row !border-b-0 !py-1.5">
                <dt>Total</dt>
                <dd className="font-bold text-pr-green">{formatUSD(order?.total ?? 0)}</dd>
              </div>
            </dl>
            <motion.div
              initial={{ scale: 1.7, opacity: 0, rotate: -10 }}
              animate={{ scale: 1, opacity: 1, rotate: -4 }}
              transition={{ type: "spring", stiffness: 280, damping: 16, delay: 0.25 }}
              className="mt-4"
            >
              <Stamp tone="green" size="lg" rotate={-4}>
                Paid · simulated
              </Stamp>
            </motion.div>
          </div>
          <p className="mt-4 text-center font-ledger text-[8.5px] uppercase leading-[1.8] tracking-[0.14em] text-ink-soft">
            A real integration would require PayPal order creation and server-side capture.
            None ran here — this record is a local fixture.
          </p>
          <div className="mt-5 space-y-2">
            <Link
              href="/shopper"
              onClick={onClose}
              className="flex items-center justify-center gap-2 rounded-lg bg-indigo py-2.5 font-ledger text-[11px] font-semibold uppercase tracking-wider text-white hover:bg-indigo/90 transition-colors w-full"
            >
              <span>Test Shopper Return Portal (R0) ➔</span>
            </Link>
            <div className="flex gap-2">
              <Link
                href="/merchant"
                onClick={onClose}
                className="flex-1 flex items-center justify-center rounded-lg border border-ink/30 bg-sheet py-2 font-ledger text-[10px] text-ink hover:border-ink transition-colors"
              >
                <span>Merchant Console</span>
              </Link>
              <button
                onClick={() => {
                  onClose();
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
                className="flex-1 rounded-lg border border-ink/30 bg-sheet py-2 font-ledger text-[10px] text-ink hover:border-ink transition-colors"
              >
                <span>Stay on Storefront</span>
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/**
 * THE TRANSFER ROOM — a PayPal Sandbox checkout, simulated honestly:
 * no session opens, no payment occurs, and the paperwork says so.
 */
export function TransferRoom({
  open,
  onOpenChange,
  total,
  qty,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  total: number;
  qty: number;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-md gap-0 overflow-hidden border-[1.5px] border-ink bg-paper p-0 sm:max-w-md"
        aria-describedby="transfer-desc"
      >
        <DialogDescription id="transfer-desc" className="sr-only">
          Simulated PayPal Sandbox checkout. No real payment is processed.
        </DialogDescription>

        <div className="border-b border-ink/50 bg-sheet px-6 py-4">
          <div className="flex items-center justify-between gap-3">
            <DialogTitle className="engraved text-xl font-semibold uppercase tracking-tight text-ink">
              The Transfer Room
            </DialogTitle>
            <Stamp tone="red" rotate={2}>
              Sandbox · simulated
            </Stamp>
          </div>
          <p className="mt-1 font-ledger text-[9px] uppercase tracking-[0.22em] text-ink-soft">
            PayPal checkout — demonstration only
          </p>
        </div>

        {open ? <TransferRun total={total} qty={qty} onClose={() => onOpenChange(false)} /> : null}
      </DialogContent>
    </Dialog>
  );
}
