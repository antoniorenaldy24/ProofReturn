"use client";

import { useEffect, useRef, useState } from "react";
import {
  AnimatePresence,
  motion,
  useMotionValue,
  useSpring,
} from "framer-motion";
import { ArrowRight, Copy, RefreshCcw, RotateCw, Play, Sparkles } from "lucide-react";
import { PASSPORT } from "@/lib/data";
import { useLedger } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Bracket, Chip, LED, Panel, Rise, SectionHead } from "@/components/chrome/hud";

/* ————————————————— passport card ————————————————— */

function PassportCard() {
  const pushToast = useLedger((s) => s.pushToast);
  const [flipped, setFlipped] = useState(false);
  const rx = useSpring(useMotionValue(0), { stiffness: 180, damping: 22 });
  const ry = useSpring(useMotionValue(0), { stiffness: 180, damping: 22 });

  const onMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width;
    const py = (e.clientY - rect.top) / rect.height;
    rx.set((0.5 - py) * 14);
    ry.set((px - 0.5) * 16);
    e.currentTarget.style.setProperty("--mx", `${px * 100}%`);
    e.currentTarget.style.setProperty("--my", `${py * 100}%`);
    e.currentTarget.style.setProperty("--ang", `${px * 360}deg`);
  };
  const onLeave = () => {
    rx.set(0);
    ry.set(0);
  };

  const copyHash = async () => {
    try {
      await navigator.clipboard.writeText(PASSPORT.serialHash);
      pushToast({
        kind: "green",
        title: "Digest copied",
        line: "Serial hash copied to clipboard — demo fixture value.",
      });
    } catch {
      pushToast({ kind: "ink", title: "Clipboard unavailable", line: "The browser blocked clipboard access." });
    }
  };

  return (
    <div className="flip-scene [perspective:1400px]">
      <motion.div
        className="flip-inner passport-tilt relative h-[420px] w-full"
        style={{ rotateX: rx, rotateY: flipped ? 180 : ry }}
        animate={{ rotateY: flipped ? 180 : undefined }}
        transition={{ type: "spring", stiffness: 160, damping: 20 }}
        onPointerMove={flipped ? undefined : onMove}
        onPointerLeave={onLeave}
        data-cursor="inspect"
      >
        {/* FRONT */}
        <div
          className="flip-face panel absolute inset-0 overflow-hidden"
          style={{ boxShadow: "0 24px 56px -20px rgba(13,148,136,0.35), 0 2px 6px rgba(21,23,26,0.05)" }}
        >
          {/* teal identity band */}
          <div
            aria-hidden
            className="absolute inset-x-0 top-0 h-1.5"
            style={{ background: "linear-gradient(90deg, var(--teal), var(--indigo), var(--teal))" }}
          />
          <div className="holo-rainbow" />
          <div className="holo-sheen" />
          <div className="relative flex h-full flex-col p-5 sm:p-6">
            <div className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2 font-tech text-[10px] font-semibold uppercase tracking-[0.22em] text-teal">
                <LED color="teal" pulse /> Condition Passport
              </span>
              <span className="rounded-full border border-teal/30 bg-teal/[0.07] px-2 py-0.5 font-tech text-[11px] tabular-nums text-teal">
                {PASSPORT.ref}
              </span>
            </div>

            <h3 className="mt-4 font-display text-xl font-semibold leading-tight text-ink">
              {PASSPORT.product}
            </h3>
            <p className="font-tech text-[10px] uppercase tracking-[0.18em] text-faint">
              {PASSPORT.sku} · issued {PASSPORT.issued}
            </p>

            <dl className="mt-5">
              <div className="data-row">
                <dt>Origin weight</dt>
                <dd className="tabular-nums">{PASSPORT.originWeight} g</dd>
              </div>
              <div className="data-row">
                <dt>Measured at intake</dt>
                <dd className="tabular-nums">
                  {PASSPORT.measuredWeight} g{" "}
                  <span className="text-ok">
                    (Δ −{(PASSPORT.originWeight - PASSPORT.measuredWeight).toFixed(1)} g · within ±{PASSPORT.weightTolerance} g)
                  </span>
                </dd>
              </div>
              <div className="data-row">
                <dt>Packaging seal</dt>
                <dd className="flex items-center justify-end gap-2">
                  <LED color="ok" pulse /> {PASSPORT.seal.status} · {PASSPORT.seal.method}
                </dd>
              </div>
            </dl>

            <div className="mt-5 flex items-center gap-4">
              <span
                className="grid h-16 w-16 shrink-0 place-items-center rounded-2xl font-display text-3xl font-bold text-ok"
                style={{
                  background: "color-mix(in srgb, var(--ok) 9%, transparent)",
                  boxShadow: "inset 0 0 0 2.5px color-mix(in srgb, var(--ok) 60%, transparent)",
                }}
              >
                {PASSPORT.condition.grade}
              </span>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <code className="truncate rounded-md bg-panel-2 px-2 py-1 font-tech text-[12px] text-ink">
                    {PASSPORT.serialHash.slice(0, 14)}…
                    {PASSPORT.serialHash.slice(-6)}
                  </code>
                  <button
                    type="button"
                    onClick={copyHash}
                    aria-label="Copy full serial hash"
                    className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-line text-dim transition-colors hover:border-teal hover:text-teal"
                  >
                    <Copy className="h-3.5 w-3.5" strokeWidth={1.5} />
                  </button>
                </div>
                <p className="mt-1 font-tech text-[10px] uppercase tracking-[0.16em] text-faint">
                  {PASSPORT.hashAlgo}
                </p>
              </div>
            </div>

            <div className="mt-auto">
              <div className="barcode h-9 w-full max-w-[260px] rounded-md opacity-80" aria-hidden />
              <div className="mt-3 flex items-center justify-between">
                <span className="font-tech text-[9px] uppercase tracking-[0.22em] text-faint">
                  Hover to tilt · flip for the log
                </span>
                <button
                  type="button"
                  onClick={() => setFlipped(true)}
                  className="btn-ghost !border-teal/50 !px-3.5 !py-2 !text-teal hover:!bg-teal hover:!text-white"
                  aria-label="Flip passport to inspection log"
                >
                  <RotateCw className="h-3.5 w-3.5" strokeWidth={1.5} /> Inspection log
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* BACK */}
        <div className="flip-face flip-back panel absolute inset-0 overflow-hidden">
          <div
            aria-hidden
            className="absolute inset-x-0 top-0 h-1.5"
            style={{ background: "linear-gradient(90deg, var(--teal), var(--indigo), var(--teal))" }}
          />
          <div className="flex h-full flex-col p-5 sm:p-6">
            <div className="flex items-center justify-between gap-3">
              <span className="font-tech text-[10px] font-semibold uppercase tracking-[0.22em] text-teal">
                Inspection log — {PASSPORT.inspections.length} points
              </span>
              <button
                type="button"
                onClick={() => setFlipped(false)}
                className="btn-ghost !border-teal/50 !px-3.5 !py-2 !text-teal hover:!bg-teal hover:!text-white"
                aria-label="Flip passport back to identity face"
              >
                <RotateCw className="h-3.5 w-3.5" strokeWidth={1.5} /> Card face
              </button>
            </div>
            <ul className="mt-4 max-h-[300px] space-y-2.5 overflow-y-auto pr-1">
              {PASSPORT.inspections.map((ins) => (
                <li
                  key={ins.zone}
                  className="rounded-xl border border-line bg-panel-2/60 p-3 transition-colors hover:border-teal/40"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-tech text-[11px] font-semibold text-ink">
                      {ins.zone}
                    </span>
                    <Chip tone={ins.result === "PASS" ? "ok" : "warn"}>
                      {ins.result}
                    </Chip>
                  </div>
                  <p className="mt-1.5 font-display text-[12.5px] leading-relaxed text-dim">
                    {ins.detail}
                  </p>
                  <p className="mt-1 font-tech text-[9px] uppercase tracking-[0.16em] text-faint">
                    {ins.inspector} · {ins.date}
                  </p>
                </li>
              ))}
            </ul>
            <div className="mt-3 border-t border-dashed border-line pt-3">
              <span className="font-tech text-[9px] uppercase tracking-[0.22em] text-faint">
                Custody chain
              </span>
              <div className="mt-2 space-y-1">
                {PASSPORT.custody.map((c) => (
                  <p key={c.event} className="font-tech text-[10px] text-dim">
                    <span className="text-teal">{c.date}</span> · {c.event}{" "}
                    <span className="text-faint">— {c.actor}</span>
                  </p>
                ))}
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

/* ————————————————— verification rig ————————————————— */

type RigLine = { text: string; kind: "info" | "ok" | "verdict" };

const SCRIPT: RigLine[] = [
  { text: "boot: verification rig v2.1 — local demo, no network", kind: "info" },
  { text: "recomputing digest over inspection payload … OK", kind: "ok" },
  { text: "seal serialization cross-reference … OK (SEAL 04-7A)", kind: "ok" },
  { text: "custody chain continuity … OK (3 events, no gaps)", kind: "ok" },
  { text: "weight delta −0.2 g within ±0.5 g tolerance … OK", kind: "ok" },
  { text: "inspection log integrity: 7/7 points recorded … OK", kind: "ok" },
  { text: "verdict: PASSPORT VALID — GRADE A", kind: "verdict" },
];

function VerificationRig() {
  const setVerified = useLedger((s) => s.setPassportVerified);
  const [status, setStatus] = useState<"idle" | "running" | "done">("idle");
  const [lines, setLines] = useState<RigLine[]>([]);
  const [pct, setPct] = useState(0);
  const runId = useRef(0);
  const reduced = useRef(false);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    reduced.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    return () => {
      runId.current += 1;
      cleanupRef.current?.();
    };
  }, []);

  /* Timeline-driven typewriter: reveal positions are computed from elapsed
     time, so clamped/throttled timers can never stall the sequence — each
     tick catches up to where the clock says it should be. */
  const run = () => {
    const id = ++runId.current;
    cleanupRef.current?.();
    setStatus("running");
    setPct(0);
    if (reduced.current || document.visibilityState !== "visible") {
      setLines(SCRIPT);
      setPct(100);
      setStatus("done");
      setVerified();
      return;
    }
    const CHAR_MS = 13;
    const LINE_GAP = 240;
    const starts: number[] = [];
    let acc = 0;
    for (const line of SCRIPT) {
      starts.push(acc);
      acc += line.text.length * CHAR_MS + LINE_GAP;
    }
    const total = acc;
    const startedAt = performance.now();
    const timer = window.setInterval(() => {
      if (runId.current !== id) {
        window.clearInterval(timer);
        return;
      }
      const e = performance.now() - startedAt;
      let i = 0;
      for (let k = SCRIPT.length - 1; k >= 0; k--) {
        if (e >= starts[k]) {
          i = k;
          break;
        }
      }
      const chars = Math.min(
        Math.floor((e - starts[i]) / CHAR_MS),
        SCRIPT[i].text.length,
      );
      setLines([...SCRIPT.slice(0, i), { ...SCRIPT[i], text: SCRIPT[i].text.slice(0, chars) }]);
      setPct(Math.min(100, Math.round((e / total) * 100)));
      if (e >= total) {
        window.clearInterval(timer);
        cleanupRef.current = null;
        setLines(SCRIPT);
        setPct(100);
        setStatus("done");
        setVerified();
      }
    }, 50);
    cleanupRef.current = () => window.clearInterval(timer);
  };

  return (
    <Panel
      label="Verification rig — runs locally, proves nothing on-chain"
      accent="teal"
      right={
        <Chip tone={status === "done" ? "ok" : status === "running" ? "teal" : "line"}>
          {status === "done" ? "Valid" : status === "running" ? "Running" : "Idle"}
        </Chip>
      }
      className="h-full"
    >
      <div className="flex h-full flex-col">
        <div
          className="min-h-[300px] flex-1 space-y-1.5 overflow-y-auto rounded-b-2xl bg-panel-2/60 p-4 font-tech text-[12px] leading-relaxed sm:p-5"
          aria-live="polite"
        >
          {lines.length === 0 ? (
            <p className="text-faint">
              &gt; press <span className="text-teal">Run verification</span> — the
              rig checks the passport&apos;s digest, seal, custody chain and
              weights. All simulated locally, this is the demo&apos;s favorite part.
            </p>
          ) : (
            lines.map((l, i) => (
              <p
                key={i}
                className={cn(
                  "whitespace-pre-wrap",
                  l.kind === "info" && "text-faint",
                  l.kind === "ok" && "text-dim",
                  l.kind === "verdict" && "font-semibold text-ok glow-ok",
                  i === lines.length - 1 && status === "running" && "term-cursor",
                )}
              >
                <span className="mr-2 text-teal">{">"}</span>
                {l.text}
              </p>
            ))
          )}
        </div>

        <div className="border-t border-line p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3 font-tech text-[10px] uppercase tracking-[0.18em] text-faint">
            <span>Rig progress</span>
            <span className="tabular-nums text-dim">{pct}%</span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-line">
            <motion.div
              className="h-full rounded-full"
              style={{
                background:
                  "linear-gradient(90deg, var(--teal), var(--ok))",
              }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.3 }}
            />
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              data-cursor="run"
              onClick={run}
              disabled={status === "running"}
              className="btn-hud"
              style={{ ["--btn" as string]: "var(--teal)" }}
            >
              {status === "running" ? (
                "Verifying…"
              ) : status === "done" ? (
                <>
                  <RefreshCcw className="h-3.5 w-3.5" strokeWidth={1.5} /> Re-run
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5" strokeWidth={1.5} /> Run verification
                </>
              )}
            </button>
            <AnimatePresence>
              {status === "done" ? (
                <motion.span
                  initial={{ scale: 2.2, opacity: 0, rotate: -18 }}
                  animate={{ scale: 1, opacity: 1, rotate: -4 }}
                  transition={{ type: "spring", stiffness: 320, damping: 15 }}
                  className="stamp text-ok"
                >
                  Passport valid — Grade A
                </motion.span>
              ) : null}
            </AnimatePresence>
          </div>
          <a
            href="#checkout"
            className="group mt-4 inline-flex items-center gap-2 font-tech text-[10px] font-semibold uppercase tracking-[0.18em] text-teal transition-colors hover:text-ink"
          >
            <Sparkles className="h-3.5 w-3.5" strokeWidth={1.5} />
            This unlocks Fast-Lane settlement in 04
            <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" strokeWidth={1.5} />
          </a>
        </div>
      </div>
    </Panel>
  );
}

export function PassportRig() {
  return (
    <section id="passport" className="relative scroll-mt-14 overflow-hidden border-t border-line py-20 sm:py-24">
      {/* ambient teal washes */}
      <div
        aria-hidden
        className="wash left-[-8%] top-[10%] h-[460px] w-[460px]"
        style={{ ["--blob" as string]: "var(--teal)", ["--blob-o" as string]: 0.09 }}
      />
      <div
        aria-hidden
        className="wash right-[-6%] bottom-[4%] h-[380px] w-[380px]"
        style={{ ["--blob" as string]: "var(--indigo)", ["--blob-o" as string]: 0.06, ["--blob-t" as string]: "40s" }}
      />

      <div className="relative mx-auto max-w-[1500px] px-4 sm:px-6">
        <SectionHead
          index="03"
          code="Passport Rig"
          hue="var(--teal)"
          title={
            <>
              Every unit carries{" "}
              <span className="hl" style={{ ["--hl" as string]: "var(--teal)" }}>
                its own record.
              </span>
            </>
          }
          action="flip the card, hover to catch the foil, then run the rig to unlock Fast-Lane."
          right={
            <Bracket className="panel px-4 py-3" color="sig">
              <span className="block font-tech text-[9px] uppercase tracking-[0.2em] text-faint">
                Open the record
              </span>
              <span className="font-tech text-[12px] font-semibold text-teal">
                Flip · tilt · verify
              </span>
            </Bracket>
          }
        />

        <div className="mt-10 grid gap-5 lg:grid-cols-2">
          <Rise>
            <PassportCard />
          </Rise>
          <Rise delay={0.1}>
            <VerificationRig />
          </Rise>
        </div>
      </div>
    </section>
  );
}
