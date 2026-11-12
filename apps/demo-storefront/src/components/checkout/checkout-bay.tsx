"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUpRight, Minus, Plus, ShieldCheck, Sparkles, X } from "lucide-react";
import { CHECKOUT, PASSPORT, PRODUCT, formatUSD } from "@/lib/data";
import { useLedger } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Bracket, Chip, LED, Panel, Rise, SectionHead } from "@/components/chrome/hud";
import { RollingNumber } from "@/components/circ/odometer";
import { Switch } from "@/components/ui/switch";

/* mini line-art of the unit */
function UnitGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden fill="none">
      <path d="M8 28a16 16 0 0 1 32 0" stroke="currentColor" strokeWidth="2" />
      <rect x="4" y="27" width="9" height="13" rx="3" stroke="currentColor" strokeWidth="1.5" />
      <rect x="35" y="27" width="9" height="13" rx="3" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="8.5" cy="33.5" r="1.5" fill="currentColor" />
      <circle cx="39.5" cy="33.5" r="1.5" fill="currentColor" />
    </svg>
  );
}

/* ————————————————— fast-lane gauge ————————————————— */

function FastLane({ total }: { total: number }) {
  const passportVerified = useLedger((s) => s.passportVerified);
  const rules = [
    {
      key: "passport",
      label: CHECKOUT.fastLaneRules[0].label,
      ok: passportVerified,
      hint: "run the rig in 03 →",
      href: "#passport",
    },
    { key: "grade", label: CHECKOUT.fastLaneRules[1].label, ok: true, hint: "", href: undefined },
    {
      key: "value",
      label: CHECKOUT.fastLaneRules[2].label,
      ok: total >= 250,
      hint: "add value in 01 →",
      href: "#specimen",
    },
  ];
  const satisfied = rules.filter((r) => r.ok).length;
  const fast = satisfied === 3;
  const deg = -90 + (satisfied / 3) * 180;

  return (
    <Panel
      label="Fast-Lane qualification"
      accent="ok"
      right={<Chip tone={fast ? "ok" : "warn"}>{fast ? "Qualified" : `${satisfied}/3`}</Chip>}
    >
      <div className="grid gap-6 p-4 sm:p-6 md:grid-cols-[auto_1fr] md:items-center">
        {/* gauge */}
        <div className="relative mx-auto w-[128px]">
          <svg viewBox="0 0 128 86" className="h-auto w-full">
            <path d="M 10 76 A 54 54 0 0 1 118 76" fill="none" stroke="#e4e5dd" strokeWidth="7" strokeLinecap="round" />
            <motion.path
              d="M 10 76 A 54 54 0 0 1 118 76"
              fill="none"
              stroke={fast ? "#0c7a44" : "#d97706"}
              strokeWidth="7"
              strokeLinecap="round"
              strokeDasharray={Math.PI * 54}
              animate={{ strokeDashoffset: Math.PI * 54 * (1 - satisfied / 3) }}
              transition={{ type: "spring", stiffness: 120, damping: 20 }}
              style={{
                filter: `drop-shadow(0 1px 6px ${fast ? "rgba(12,122,68,0.45)" : "rgba(217,119,6,0.4)"})`,
              }}
            />
            <motion.line
              x1={64}
              y1={76}
              x2={64}
              y2={32}
              stroke="#171a1e"
              strokeWidth="2.5"
              strokeLinecap="round"
              animate={{ rotate: deg }}
              style={{ transformOrigin: "64px 76px" }}
              transition={{ type: "spring", stiffness: 120, damping: 18 }}
            />
            <circle cx={64} cy={76} r="4.5" fill="#ffffff" stroke={fast ? "#0c7a44" : "#d97706"} strokeWidth="2.5" />
          </svg>
          <span
            className={cn(
              "mt-1 block text-center font-tech text-[10px] font-semibold uppercase tracking-[0.18em]",
              fast ? "text-ok" : "text-warn",
            )}
          >
            {fast ? "Fast-lane" : "Standard"}
          </span>
        </div>

        <div>
          <AnimatePresence mode="wait" initial={false}>
            <motion.p
              key={fast ? "fast" : "std"}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className={cn(
                "font-display text-2xl font-semibold",
                fast ? "text-ok" : "text-ink",
              )}
            >
              {fast ? "Settlement ≤ 48 hours" : "Settlement 5–7 days"}
            </motion.p>
          </AnimatePresence>
          <ul className="mt-4 space-y-2.5">
            {rules.map((r) => (
              <li
                key={r.key}
                className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5 border-b border-dashed border-line pb-2.5"
              >
                <span className="flex items-center gap-2 font-tech text-[11px] text-dim">
                  <LED color={r.ok ? "ok" : "faint"} pulse={r.ok} /> {r.label}
                </span>
                {r.ok ? (
                  <span className="font-tech text-[9px] font-semibold uppercase tracking-[0.16em] text-ok">
                    OK
                  </span>
                ) : r.href ? (
                  <a
                    href={r.href}
                    className="group inline-flex items-center gap-1 whitespace-nowrap rounded-full bg-warn/[0.08] px-2.5 py-1 font-tech text-[9px] font-semibold uppercase tracking-[0.12em] text-warn transition-colors hover:bg-warn/15 hover:text-ink"
                  >
                    {r.hint}
                    <ArrowUpRight className="h-3 w-3 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
                  </a>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Panel>
  );
}

/* ————————————————— paypal sandbox modal ————————————————— */

function PayPalModal({
  amount,
  onClose,
}: {
  amount: number;
  onClose: () => void;
}) {
  const sealOrder = useLedger((s) => s.sealOrder);
  const pushToast = useLedger((s) => s.pushToast);
  // Freeze at mount: sealOrder empties the ledger mid-flow, which would
  // otherwise re-render the modal with a $0.00 amount.
  const [frozenAmount] = useState(() => amount);
  const [lines, setLines] = useState<Array<{ text: string; detail: string; done: boolean }>>([]);
  const [phase, setPhase] = useState<"running" | "done">("running");
  const [orderRef] = useState(
    () => `PR-ORD-${Math.floor(1000 + Math.random() * 9000)}`,
  );
  const [txRef] = useState(
    () => `SANDBOX-${Math.floor(100000 + Math.random() * 900000)}`,
  );
  const phaseRef = useRef<"running" | "done">("running");
  const closeBtn = useRef<HTMLButtonElement>(null);

  const finish = useCallback(() => {
    setPhase("done");
    phaseRef.current = "done";
    sealOrder({
      ref: orderRef,
      tx: txRef,
      sealedAt: new Date().toLocaleTimeString("en-US", { hour12: false }),
      total: frozenAmount,
    });
    pushToast({
      kind: "green",
      title: "Order sealed — simulated",
      line: `${orderRef} · ${formatUSD(frozenAmount)} · sandbox capture only.`,
    });
  }, [frozenAmount, orderRef, txRef, pushToast, sealOrder]);

  useEffect(() => {
    closeBtn.current?.focus();
    document.body.style.overflow = "hidden";
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && phaseRef.current !== "running") onClose();
    };
    window.addEventListener("keydown", esc);
    let cancelled = false;

    const run = async () => {
      for (const step of CHECKOUT.paypal.steps) {
        if (cancelled) return;
        setLines((l) => [...l, { text: step.line, detail: step.detail, done: false }]);
        await new Promise((r) => setTimeout(r, 650));
        if (cancelled) return;
        setLines((l) => {
          const next = [...l];
          next[next.length - 1] = { text: step.line, detail: step.detail, done: true };
          return next;
        });
      }
      if (cancelled) return;
      finish();
    };
    void run();

    return () => {
      cancelled = true;
      document.body.style.overflow = "";
      window.removeEventListener("keydown", esc);
    };
  }, [finish, onClose]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[80] grid place-items-center bg-paper/80 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="PayPal Sandbox checkout simulation"
    >
          <motion.div
            initial={{ scale: 0.92, y: 16 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.94, y: 10, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 26 }}
            className="panel w-full max-w-lg shadow-[0_24px_64px_rgba(21,23,26,0.16)]"
          >
            <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
              <span className="flex items-center gap-2 font-tech text-[10px] font-semibold uppercase tracking-[0.2em] text-paypal">
                <LED color="sig" pulse={phase === "running"} />
                PayPal Sandbox — simulated
              </span>
              <button
                ref={closeBtn}
                type="button"
                onClick={onClose}
                disabled={phase === "running"}
                className="grid h-8 w-8 place-items-center rounded-full border border-line text-dim transition-colors hover:border-sig hover:text-sig disabled:opacity-30"
                aria-label="Close sandbox window"
              >
                <X className="h-4 w-4" strokeWidth={1.5} />
              </button>
            </header>

            <div className="min-h-[240px] space-y-1.5 rounded-b-2xl bg-panel-2/60 p-4 font-tech text-[12px] sm:p-5">
              <p className="text-faint">
                &gt; amount {formatUSD(frozenAmount)} · passport {PASSPORT.ref} · no network calls
              </p>
              {lines.map((l, i) => (
                <div key={i} className="flex items-start justify-between gap-3">
                  <span className={cn("min-w-0", l.done ? "text-dim" : "text-ink")}>
                    <span className="mr-2 text-paypal">{">"}</span>
                    {l.text}
                    {!l.done ? <span className="term-cursor" /> : (
                      <span className="ml-2 text-ok">✓</span>
                    )}
                  </span>
                  <span className="shrink-0 font-tech text-[10px] text-faint">{l.detail}</span>
                </div>
              ))}
              {phase === "done" ? (
                <motion.div
                  initial={{ scale: 1.6, opacity: 0, rotate: -12 }}
                  animate={{ scale: 1, opacity: 1, rotate: -4 }}
                  transition={{ type: "spring", stiffness: 320, damping: 15 }}
                  className="stamp mt-4 text-ok"
                >
                  Capture completed — simulated
                </motion.div>
              ) : null}
            </div>

            <footer className="space-y-3 border-t border-line p-4 sm:p-5">
              {phase === "done" ? (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="font-tech text-[11px] text-dim">
                    order <span className="font-semibold text-ink">{orderRef}</span> · tx{" "}
                    <span className="font-semibold text-ink">{txRef}</span> · passport on file
                  </div>
                  <div className="flex gap-2">
                    <Chip tone="sig">Demo only</Chip>
                    <button
                      type="button"
                      onClick={onClose}
                      className="btn-hud !px-4 !py-2.5"
                      style={{ ["--btn" as string]: "var(--ok)" }}
                    >
                      Close
                    </button>
                  </div>
                </div>
              ) : (
                <p className="font-display text-[12px] leading-relaxed text-dim">
                  {CHECKOUT.paypal.disclaimer}
                </p>
              )}
            </footer>
          </motion.div>
    </motion.div>
  );
}

/* ————————————————— checkout bay ————————————————— */

export function CheckoutBay() {
  const qty = useLedger((s) => s.qty);
  const setQty = useLedger((s) => s.setQty);
  const stamp = useLedger((s) => s.stamp);
  const [warranty, setWarranty] = useState(false);
  const [payOpen, setPayOpen] = useState(false);
  const closePay = useCallback(() => setPayOpen(false), []);

  const subtotal = qty * PRODUCT.msrp;
  const warrantyCost = warranty && qty > 0 ? CHECKOUT.warranty.price : 0;
  const total = subtotal + warrantyCost;

  return (
    <section id="checkout" className="relative scroll-mt-14 overflow-hidden border-t border-line py-20 sm:py-24">
      {/* ambient green wash */}
      <div
        aria-hidden
        className="wash right-[-8%] top-[10%] h-[440px] w-[440px]"
        style={{ ["--blob" as string]: "var(--ok)", ["--blob-o" as string]: 0.08 }}
      />
      <div
        aria-hidden
        className="wash left-[-6%] bottom-[8%] h-[360px] w-[360px]"
        style={{ ["--blob" as string]: "var(--paypal)", ["--blob-o" as string]: 0.06, ["--blob-t" as string]: "42s" }}
      />

      <div className="relative mx-auto max-w-[1500px] px-4 sm:px-6">
        <SectionHead
          index="04"
          code="Checkout Bay"
          hue="var(--ok)"
          title={
            <>
              Pay for{" "}
              <span className="hl" style={{ ["--hl" as string]: "var(--ok)" }}>
                proof,
              </span>{" "}
              not promises.
            </>
          }
          action="the ledger totals itself in front of you — verify the passport in 03 to save days of settlement."
          right={
            <Chip tone="warn">
              <ShieldCheck className="h-3 w-3" /> Sandbox only — no real payments
            </Chip>
          }
        />

        <div className="mt-10 grid gap-5 lg:grid-cols-[1fr_400px]">
          {/* ——— ledger ——— */}
          <Rise>
            <Panel
              label="Ledger — unit PR-0038"
              accent="ok"
              right={
                <span className="font-tech text-[10px] tabular-nums text-dim">
                  {qty} unit{qty === 1 ? "" : "s"}
                </span>
              }
            >
              {qty === 0 ? (
                <div className="flex flex-col items-center gap-4 p-10 text-center">
                  <span className="grid h-16 w-16 place-items-center rounded-2xl bg-panel-2">
                    <UnitGlyph className="h-9 w-9 text-faint" />
                  </span>
                  <p className="max-w-xs font-display text-[13px] leading-relaxed text-dim">
                    Your ledger is empty. Add the Auralis N°1 from the specimen
                    bay — everything there is already verified.
                  </p>
                  <div className="flex flex-wrap justify-center gap-2.5">
                    <button type="button" onClick={() => stamp(1)} className="btn-hud">
                      <Plus className="h-3.5 w-3.5" strokeWidth={2} /> Stamp unit to ledger
                    </button>
                    <a href="#specimen" className="btn-ghost">
                      Back to 01
                    </a>
                  </div>
                </div>
              ) : (
                <div className="p-4 sm:p-6">
                  <div className="flex flex-wrap items-center gap-4 rounded-2xl border border-line bg-panel-2/50 p-4">
                    <span
                      className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl text-sig"
                      style={{ background: "color-mix(in srgb, var(--sig) 8%, transparent)" }}
                    >
                      <UnitGlyph className="h-8 w-8" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="font-display text-[15px] font-semibold text-ink">
                        {PRODUCT.name} — {PRODUCT.tagline}
                      </p>
                      <p className="mt-0.5 font-tech text-[10px] uppercase tracking-[0.16em] text-faint">
                        {PRODUCT.sku} · Grade A open-box · passport attached
                      </p>
                    </div>
                    <div className="flex items-stretch overflow-hidden rounded-full border border-line">
                      <button
                        type="button"
                        onClick={() => setQty(qty - 1)}
                        className="grid h-10 w-10 place-items-center text-dim transition-colors hover:bg-panel hover:text-sig"
                        aria-label="Remove one unit"
                      >
                        <Minus className="h-3.5 w-3.5" />
                      </button>
                      <span className="grid h-10 w-12 place-items-center border-x border-line font-tech text-[13px] font-semibold tabular-nums">
                        {qty}
                      </span>
                      <button
                        type="button"
                        onClick={() => setQty(qty + 1)}
                        disabled={qty >= 3}
                        className="grid h-10 w-10 place-items-center text-dim transition-colors hover:bg-panel hover:text-sig disabled:opacity-30"
                        aria-label="Add one unit"
                      >
                        <Plus className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <RollingNumber value={subtotal} small className="w-24 text-right text-ink" />
                  </div>

                  <div className="mt-4 flex items-center justify-between gap-4 rounded-2xl border border-line bg-panel-2/50 p-4">
                    <div>
                      <p className="font-tech text-[11px] font-semibold text-ink">
                        {CHECKOUT.warranty.label}{" "}
                        <span className="text-sig">+{formatUSD(CHECKOUT.warranty.price)}</span>
                      </p>
                      <p className="mt-0.5 font-display text-[12px] text-faint">
                        {CHECKOUT.warranty.note}
                      </p>
                    </div>
                    <Switch
                      checked={warranty}
                      onCheckedChange={setWarranty}
                      aria-label="Toggle seal warranty extension"
                    />
                  </div>

                  <dl className="mt-5">
                    <div className="data-row">
                      <dt>Subtotal</dt>
                      <dd className="tabular-nums">{formatUSD(subtotal)}</dd>
                    </div>
                    <div className="data-row">
                      <dt>{CHECKOUT.warranty.label}</dt>
                      <dd className="tabular-nums">{formatUSD(warrantyCost)}</dd>
                    </div>
                    <div className="data-row">
                      <dt>Shipping</dt>
                      <dd className="text-dim">{CHECKOUT.shipping}</dd>
                    </div>
                    <div className="data-row">
                      <dt>Tax</dt>
                      <dd className="tabular-nums">{formatUSD(CHECKOUT.tax)}</dd>
                    </div>
                    <div className="flex items-end justify-between gap-4 pt-4">
                      <span className="font-tech text-[10px] uppercase tracking-[0.2em] text-faint">
                        Total due
                      </span>
                      <RollingNumber value={total} className="text-ink" />
                    </div>
                  </dl>
                </div>
              )}
            </Panel>
          </Rise>

          {/* ——— fast lane + pay ——— */}
          <div className="flex flex-col gap-5">
            <Rise delay={0.08}>
              <FastLane total={total} />
            </Rise>
            <Rise delay={0.14}>
              <Bracket className="panel p-4 sm:p-5" color="sig">
                <button
                  type="button"
                  data-cursor="open"
                  onClick={() => setPayOpen(true)}
                  disabled={qty === 0}
                  className="btn-hud w-full"
                  style={{ ["--btn" as string]: "var(--paypal)" }}
                >
                  <Sparkles className="h-3.5 w-3.5" strokeWidth={1.5} />
                  Checkout with PayPal — Sandbox
                </button>
                <p className="mt-3 font-display text-[12px] leading-relaxed text-dim">
                  {qty === 0
                    ? "Stamp at least one unit to enable the sandbox flow."
                    : "Opens a simulated sandbox terminal. Nothing is charged, ever."}
                </p>
              </Bracket>
            </Rise>
          </div>
        </div>
      </div>

      <AnimatePresence>
        {payOpen ? <PayPalModal amount={total} onClose={closePay} /> : null}
      </AnimatePresence>
    </section>
  );
}
