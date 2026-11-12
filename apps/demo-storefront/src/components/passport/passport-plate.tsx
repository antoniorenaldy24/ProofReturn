"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { PlateFrame } from "@/components/ornament/plate-frame";
import { MicrotextStrip, Rosette, Rule, Seal, Stamp } from "@/components/ornament/ornaments";
import { PASSPORT } from "@/lib/data";
import { useLedger } from "@/lib/store";
import { cn } from "@/lib/utils";

type Stage = "idle" | "hashing" | "verified";

const HOLD_MS = 1100;
const HASH_GROUPS = PASSPORT.serialHash.match(/.{1,8}/g) ?? [];

/* ——— Hold-to-verify control ——— */
function HoldToVerify({ onComplete, done }: { onComplete: () => void; done: boolean }) {
  const [holding, setHolding] = useState(false);
  const timer = useRef<number | null>(null);
  const start = useRef(0);
  const reduced = useReducedMotion();

  const begin = () => {
    if (done) return;
    setHolding(true);
    start.current = performance.now();
    timer.current = window.setTimeout(() => {
      setHolding(false);
      onComplete();
    }, reduced ? 80 : HOLD_MS);
  };
  const cancel = () => {
    if (done || !holding) return;
    if (timer.current) window.clearTimeout(timer.current);
    setHolding(false);
  };

  useEffect(() => () => { if (timer.current) window.clearTimeout(timer.current); }, []);

  return (
    <button
      type="button"
      onPointerDown={begin}
      onPointerUp={cancel}
      onPointerLeave={cancel}
      onKeyDown={(e) => {
        if ((e.key === " " || e.key === "Enter") && !e.repeat) begin();
      }}
      onKeyUp={(e) => {
        if (e.key === " " || e.key === "Enter") {
          if (performance.now() - start.current >= (reduced ? 0 : HOLD_MS)) return; // timer already fired
          cancel();
        }
      }}
      aria-label={done ? "Verification complete" : "Hold to run the verification sequence"}
      data-cursor="hold"
      className={cn(
        "relative w-full overflow-hidden border-[1.5px] px-5 py-4 font-ledger text-[11px] font-semibold uppercase tracking-[0.24em] transition-colors",
        done
          ? "border-pr-green bg-pr-green text-sheet"
          : holding
            ? "border-pr-green bg-paper-2 text-pr-green"
            : "border-ink bg-transparent text-ink hover:border-pr-green hover:text-pr-green",
      )}
    >
      <span
        aria-hidden="true"
        className="absolute inset-y-0 left-0 bg-pr-green/20"
        style={{
          width: holding ? "100%" : "0%",
          transition: holding ? `width ${HOLD_MS}ms linear` : "width 120ms ease",
        }}
      />
      <span className="relative">{done ? "✓ Seal verified — demo" : holding ? "Recomputing…" : "Hold to verify"}</span>
    </button>
  );
}

/* ——— Verification sequence ——— */
function VerifySequence({ onDone }: { onDone: () => void }) {
  const [reveal, setReveal] = useState(0);
  const [checkIdx, setCheckIdx] = useState(-1);
  const onDoneRef = useRef(onDone);

  useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  // Hash reveal — the digest rebuilds itself, group by group.
  useEffect(() => {
    const total = PASSPORT.serialHash.length;
    const iv = window.setInterval(() => {
      setReveal((r) => {
        if (r + 4 >= total) {
          window.clearInterval(iv);
          window.setTimeout(() => setCheckIdx(0), 260);
          return total;
        }
        return r + 4;
      });
    }, 22);
    return () => window.clearInterval(iv);
  }, []);

  // Checks land one by one, then the sequence confesses completion upward.
  useEffect(() => {
    if (checkIdx < 0) return;
    if (checkIdx >= PASSPORT.verification.checks.length) {
      onDoneRef.current();
      return;
    }
    const t = window.setTimeout(() => setCheckIdx((i) => i + 1), 430);
    return () => window.clearTimeout(t);
  }, [checkIdx]);

  return (
    <div className="border border-ink/50 bg-sheet p-4" aria-live="polite">
      <p className="font-ledger text-[9px] font-semibold uppercase tracking-[0.26em] text-ink-soft">
        Verification record — {PASSPORT.hashAlgo}
      </p>
      <div className="mt-2 break-all font-ledger text-[10.5px] leading-[1.9] tracking-[0.06em]">
        {HASH_GROUPS.map((grp, gi) => {
          const before = gi * 8;
          const shown = Math.max(0, Math.min(8, reveal - before));
          return (
            <span key={gi} className="mr-2 inline-block">
              <span className={cn(shown > 0 ? "text-pr-green" : "text-ink/25")}>{grp.slice(0, shown)}</span>
              <span className="text-ink/25">{grp.slice(shown)}</span>
            </span>
          );
        })}
      </div>
      <ul className="mt-3 space-y-1.5">
        {PASSPORT.verification.checks.map((c, i) => {
          const done = i < checkIdx;
          const current = i === checkIdx;
          return (
            <li
              key={c}
              className={cn(
                "flex items-center gap-2.5 font-ledger text-[10px] uppercase tracking-[0.14em] transition-colors",
                done ? "text-pr-green" : current ? "text-ink" : "text-ink/30",
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  "flex h-4 w-4 items-center justify-center border text-[8px]",
                  done ? "border-pr-green bg-pr-green text-sheet" : "border-ink/40",
                )}
              >
                {done ? "✓" : ""}
              </span>
              {c}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * PLATE III — THE PASSPORT.
 * A certificate you can put under a lamp: hold to recompute the seal,
 * watch the digest rebuild, and find what is printed in invisible ink.
 */
export function PassportPlate() {
  const [lampOn, setLampOn] = useState(false);
  const [stage, setStage] = useState<Stage>("idle");
  const setPassportVerified = useLedger((s) => s.setPassportVerified);

  const finishSequence = useCallback(() => {
    setStage("verified");
    setPassportVerified();
  }, [setPassportVerified]);

  return (
    <PlateFrame id="passport" numeral="III" title="The Passport" kicker="Plate III — Condition Passport · provenance">
      <p data-reveal className="mx-auto -mt-4 mb-10 max-w-[58ch] text-center font-ledger text-[12px] leading-relaxed text-ink-soft">
        This object carries its history in the open. Hold the seal to recompute it, and try the lamp —
        some records only answer to light.
      </p>

      {/* ——— The certificate ——— */}
      <div
        data-reveal
        className="lamp-scene relative mx-auto max-w-4xl overflow-hidden border-[1.5px] border-ink bg-sheet p-1 shadow-[8px_8px_0_rgba(34,29,18,0.14)] transition-colors duration-700"
        data-lamp={lampOn ? "on" : "off"}
      >
        <div className="relative overflow-hidden border border-ink/60 px-5 py-6 sm:px-9 sm:py-8">
          {/* hidden under daylight — revealed under the lamp */}
          <div className="lamp-hidden pointer-events-none absolute inset-0 z-20">
            <span
              aria-hidden="true"
              className="engraved lamp-glow-green absolute -right-4 bottom-6 rotate-[-14deg] text-[9rem] font-black leading-none opacity-25"
            >
              PR
            </span>
            <span className="lamp-glow-bronze absolute left-6 top-1/3 font-ledger text-[9px] uppercase tracking-[0.3em]">
              UV 04-7A · seal intact · intake 258.1 g
            </span>
            <span className="lamp-glow-red absolute right-8 top-24 font-ledger text-[8px] uppercase tracking-[0.34em]">
              fiber cluster α · fiber cluster β
            </span>
          </div>

          {/* header */}
          <div className="lamp-ink relative z-10 flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="font-ledger text-[9px] font-semibold uppercase tracking-[0.3em] text-pr-red">
                ProofReturn registry · demo document
              </p>
              <h3 className="engraved mt-1.5 text-3xl font-semibold uppercase tracking-tight text-ink sm:text-4xl">
                Condition Passport
              </h3>
              <p className="mt-1.5 font-ledger text-[10px] uppercase tracking-[0.2em] text-ink-soft">
                {PASSPORT.ref} · issued {PASSPORT.issued} · {PASSPORT.sku}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Stamp tone="red" rotate={2}>
                Specimen
              </Stamp>
              <button
                role="switch"
                aria-checked={lampOn}
                onClick={() => setLampOn((v) => !v)}
                data-cursor="inspect"
                className="group flex items-center gap-2.5"
                aria-label="Inspect the certificate under the UV lamp"
              >
                <span className="font-ledger text-[9px] font-semibold uppercase tracking-[0.22em] text-ink-soft transition-colors group-hover:text-ink">
                  Lamp {lampOn ? "on" : "off"}
                </span>
                <span
                  aria-hidden="true"
                  className={cn(
                    "relative flex h-6 w-12 items-center border border-ink px-0.5 transition-colors",
                    lampOn && "border-pr-green",
                  )}
                >
                  <span
                    className={cn(
                      "block h-4 w-4 transition-all duration-300",
                      lampOn ? "translate-x-6 bg-pr-green" : "translate-x-0 bg-ink/50",
                    )}
                  />
                </span>
              </button>
            </div>
          </div>

          <Rule className="lamp-fade mt-5" />

          <div className="relative z-10 mt-6 grid gap-8 md:grid-cols-[1.25fr_1fr]">
            {/* left — identity + inspections */}
            <div className="lamp-ink">
              <dl>
                <div className="ledger-row">
                  <dt>Object</dt>
                  <dd className="max-w-[30ch] text-right text-[11.5px]">{PASSPORT.product}</dd>
                </div>
                <div className="ledger-row">
                  <dt>Serial digest</dt>
                  <dd className="font-semibold text-pr-green">
                    {PASSPORT.serialHash.slice(0, 10).toUpperCase()}…{PASSPORT.serialHash.slice(-6).toUpperCase()}
                  </dd>
                </div>
                <div className="ledger-row">
                  <dt>Origin weight / measured</dt>
                  <dd>
                    {PASSPORT.originWeight} g /{" "}
                    <span className="text-pr-green">{PASSPORT.measuredWeight} g ✓</span>
                    <span className="text-ink-soft"> (±{PASSPORT.weightTolerance} g)</span>
                  </dd>
                </div>
                <div className="ledger-row">
                  <dt>Packaging seal</dt>
                  <dd className="text-pr-green">
                    {PASSPORT.seal.status} — {PASSPORT.seal.method}
                  </dd>
                </div>
                <div className="ledger-row !border-b-0">
                  <dt>Condition</dt>
                  <dd className="max-w-[34ch] text-right text-[11px] leading-relaxed">{PASSPORT.condition.summary}</dd>
                </div>
              </dl>

              <p className="mt-6 border-b border-ink/50 pb-2 font-ledger text-[9px] font-semibold uppercase tracking-[0.26em] text-ink-soft">
                Tamper-evident inspection history — 6 records
              </p>
              <ul className="max-h-72 divide-y divide-ink/15 overflow-y-auto pr-1">
                {PASSPORT.inspections.map((r) => (
                  <li key={r.zone} className="py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-ledger text-[11px] font-semibold text-ink">{r.zone}</p>
                      <span
                        className={cn(
                          "border px-1.5 py-0.5 font-ledger text-[8px] font-semibold uppercase tracking-[0.18em]",
                          r.result === "PASS" ? "border-pr-green text-pr-green" : "border-pr-bronze text-pr-bronze",
                        )}
                      >
                        {r.result}
                      </span>
                    </div>
                    <p className="mt-1 font-ledger text-[10.5px] leading-relaxed text-ink-soft">{r.detail}</p>
                    <p className="mt-1 font-ledger text-[8.5px] uppercase tracking-[0.18em] text-ink-soft/80">
                      {r.inspector} · {r.date}
                    </p>
                  </li>
                ))}
              </ul>
            </div>

            {/* right — seal, verify, custody */}
            <div className="lamp-ink flex flex-col gap-6">
              <div className="lamp-seal flex justify-center border border-dashed border-ink/40 p-4">
                <Seal size={124} center="A" sub="GRADE" />
              </div>

              <div>
                <HoldToVerify done={stage === "verified"} onComplete={() => setStage("hashing")} />
                <AnimatePresence>
                  {stage !== "idle" && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      exit={{ opacity: 0, height: 0 }}
                      className="mt-4 overflow-hidden"
                    >
                      <VerifySequence onDone={finishSequence} />
                    </motion.div>
                  )}
                </AnimatePresence>
                {stage === "verified" && (
                  <motion.div
                    initial={{ scale: 1.6, opacity: 0, rotate: -8 }}
                    animate={{ scale: 1, opacity: 1, rotate: -3 }}
                    transition={{ type: "spring", stiffness: 300, damping: 18 }}
                    className="mt-4 flex justify-center"
                  >
                    <Stamp tone="green" size="lg" rotate={-3}>
                      Seal verified · demonstration
                    </Stamp>
                  </motion.div>
                )}
              </div>

              <div>
                <p className="border-b border-ink/50 pb-2 font-ledger text-[9px] font-semibold uppercase tracking-[0.26em] text-ink-soft">
                  Chain of custody
                </p>
                <ol className="mt-3 space-y-0">
                  {PASSPORT.custody.map((c, i) => (
                    <li key={c.event} className="relative flex gap-3.5 pb-4">
                      <span
                        aria-hidden="true"
                        className={cn(
                          "absolute left-[5px] top-3 h-full w-px border-l border-dashed",
                          i === PASSPORT.custody.length - 1 ? "border-transparent" : "border-ink/40",
                        )}
                      />
                      <span aria-hidden="true" className="mt-1.5 h-[9px] w-[9px] shrink-0 rounded-full border border-ink bg-sheet" />
                      <div>
                        <p className="font-ledger text-[10.5px] font-semibold text-ink">{c.event}</p>
                        <p className="font-ledger text-[8.5px] uppercase tracking-[0.16em] text-ink-soft">
                          {c.date} · {c.actor}
                        </p>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </div>

          <Rule className="lamp-fade mt-6" />
          <div className="lamp-fade mt-2.5">
            <MicrotextStrip
              text="PROOFRETURN · CONDITION PASSPORT · SPECIMEN · DIGEST IS A DEMONSTRATION · NO CRYPTOGRAPHIC SERVICE IS RUNNING"
              repeat={26}
            />
          </div>
        </div>

        {/* resting guilloché */}
        <Rosette
          size={340}
          count={6}
          className="lamp-fade pointer-events-none absolute -right-16 -top-10 opacity-[0.07]"
        />
      </div>

      <p data-reveal className="mx-auto mt-8 max-w-[60ch] text-center font-ledger text-[10px] leading-relaxed uppercase tracking-[0.16em] text-ink-soft">
        The digest above is a demonstration string — no cryptographic service runs in this storefront.
        Verified seals feed the Fast-Lane check in the Counting House.
      </p>
    </PlateFrame>
  );
}
