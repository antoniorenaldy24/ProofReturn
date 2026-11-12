"use client";

import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  CIRC_GRADES,
  GRADE_COLORS,
  JURISDICTIONS,
  MISDECLARATION,
  PRODUCT,
  formatUSD,
} from "@/lib/data";
import { cn } from "@/lib/utils";
import { Bracket, Chip, Panel, Rise, SectionHead } from "@/components/chrome/hud";
import { RollingNumber } from "./odometer";
import { ConditionLever } from "./condition-lever";

/* SVG geometry — stepped refund ladder */
const NODE_X = [110, 250, 390, 530];
const TIER_Y = CIRC_GRADES.map((g) => 60 + (1 - g.rate) * 400);
const COLS: Array<[number, number]> = [
  [36, 180],
  [180, 320],
  [320, 460],
  [460, 604],
];
const STEP_PATH = `M 36 ${TIER_Y[0]} H 180 V ${TIER_Y[1]} H 320 V ${TIER_Y[2]} H 460 V ${TIER_Y[3]} H 604`;

function CurveSvg({
  idx,
  onSelect,
}: {
  idx: number;
  onSelect: (i: number) => void;
}) {
  const active = GRADE_COLORS[idx];
  return (
    <svg
      viewBox="0 0 680 380"
      className="h-auto w-full"
      role="img"
      aria-label={`Refund ladder: Grade A ${formatUSD(CIRC_GRADES[0].refund)}, B ${formatUSD(CIRC_GRADES[1].refund)}, C ${formatUSD(CIRC_GRADES[2].refund)}, D ${formatUSD(CIRC_GRADES[3].refund)}. Selected grade ${CIRC_GRADES[idx].grade}.`}
    >
      <defs>
        <linearGradient id="circ-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={active} stopOpacity={0.14} />
          <stop offset="100%" stopColor={active} stopOpacity={0.01} />
        </linearGradient>
      </defs>

      {/* grid */}
      {TIER_Y.map((y, i) => (
        <line key={i} x1={36} x2={604} y1={y} y2={y} stroke="#e4e5dd" strokeDasharray="3 5" />
      ))}
      {NODE_X.map((x) => (
        <line key={x} x1={x} x2={x} y1={40} y2={310} stroke="#efefe9" />
      ))}

      {/* soft area under the selected tier */}
      <motion.path
        d={`${STEP_PATH} V 310 H 36 Z`}
        fill="url(#circ-fill)"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6 }}
      />

      {/* stepped curve draws in */}
      <motion.path
        d={STEP_PATH}
        fill="none"
        stroke={active}
        strokeWidth={2.5}
        strokeLinecap="round"
        initial={{ pathLength: 0 }}
        whileInView={{ pathLength: 1 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 1.4, ease: "easeInOut" }}
        animate={{ stroke: active }}
        style={{ filter: `drop-shadow(0 2px 8px ${active}40)` }}
      />

      {/* pointer columns */}
      {COLS.map(([x1, x2], i) => (
        <motion.rect
          key={i}
          x={x1}
          y={30}
          width={x2 - x1}
          height={290}
          fill={i === idx ? active : "transparent"}
          opacity={i === idx ? 0.05 : 0}
          rx={8}
          style={{ cursor: "pointer" }}
          animate={{ opacity: i === idx ? 0.06 : 0 }}
          transition={{ duration: 0.3 }}
          onPointerDown={() => onSelect(i)}
        />
      ))}

      {/* nodes */}
      {CIRC_GRADES.map((g, i) => (
        <g key={g.grade} onPointerDown={() => onSelect(i)} style={{ cursor: "pointer" }}>
          <circle
            cx={NODE_X[i]}
            cy={TIER_Y[i]}
            r={i === idx ? 7.5 : 5.5}
            fill={i === idx ? GRADE_COLORS[i] : "#ffffff"}
            stroke={GRADE_COLORS[i]}
            strokeWidth={i === idx ? 3 : 1.75}
            style={{
              transition: "r 0.25s ease, stroke-width 0.25s ease",
              filter: i === idx ? `drop-shadow(0 1px 6px ${GRADE_COLORS[i]}66)` : undefined,
            }}
          />
          {i === idx ? (
            <circle cx={NODE_X[i]} cy={TIER_Y[i]} r={12} fill="none" stroke={GRADE_COLORS[i]} strokeWidth={1.2} opacity={0.5}>
              <animate attributeName="r" values="10;17;10" dur="1.8s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.55;0.08;0.55" dur="1.8s" repeatCount="indefinite" />
            </circle>
          ) : null}
        </g>
      ))}

      {/* drop line + crosshair marker */}
      <motion.g
        animate={{ x: NODE_X[idx], y: TIER_Y[idx] }}
        transition={{ type: "spring", stiffness: 280, damping: 28 }}
      >
        <motion.line y1={0} stroke={active} strokeWidth={1.25} strokeDasharray="2 4" opacity={0.6} animate={{ y2: 310 - TIER_Y[idx] }} />
        <line x1={-14} x2={14} y1={0} y2={0} stroke={active} strokeWidth={1.25} />
        <line x1={0} x2={0} y1={-14} y2={14} stroke={active} strokeWidth={1.25} />
      </motion.g>

      {/* labels: grade letters + exact amounts */}
      {CIRC_GRADES.map((g, i) => (
        <g key={g.grade}>
          <text
            x={NODE_X[i]}
            y={336}
            textAnchor="middle"
            fontSize={13}
            fontWeight={700}
            fill={i === idx ? GRADE_COLORS[i] : "#8b9087"}
            style={{ fontFamily: "var(--font-jbmono), monospace" }}
          >
            GRADE {g.grade}
          </text>
          <text
            x={NODE_X[i]}
            y={356}
            textAnchor="middle"
            fontSize={12}
            fontWeight={i === idx ? 700 : 400}
            fill={i === idx ? GRADE_COLORS[i] : "#585e55"}
            style={{ fontFamily: "var(--font-jbmono), monospace" }}
          >
            {formatUSD(g.refund)}
          </text>
        </g>
      ))}

      {/* rate labels */}
      {CIRC_GRADES.map((g, i) => (
        <text
          key={g.grade}
          x={614}
          y={TIER_Y[i] + 4}
          fontSize={12}
          fontWeight={i === idx ? 700 : 400}
          fill={i === idx ? GRADE_COLORS[i] : "#8b9087"}
          style={{ fontFamily: "var(--font-jbmono), monospace" }}
        >
          {Math.round(g.rate * 100)}%
        </text>
      ))}
    </svg>
  );
}

export function CircConsole() {
  const [idx, setIdx] = useState(0);
  const [juris, setJuris] = useState<"US-CA" | "EU">("US-CA");
  const [fValue, setFValue] = useState(MISDECLARATION.demoDefault);

  const tier = CIRC_GRADES[idx];
  const tierColor = GRADE_COLORS[idx];
  const jurisFixture = useMemo(
    () => JURISDICTIONS.find((j) => j.code === juris) ?? JURISDICTIONS[0],
    [juris],
  );

  /* $F scenario: declared grade vs one grade worse as found by the lab */
  const foundIdx = Math.min(idx + 1, 3);
  const foundTier = CIRC_GRADES[foundIdx];
  const netAfterF = Math.max(foundTier.refund - fValue, 0);
  const stepF = (dir: 1 | -1) =>
    setFValue((v) =>
      Math.min(MISDECLARATION.max, Math.max(MISDECLARATION.min, Math.round((v + dir * MISDECLARATION.step) * 10) / 10)),
    );

  return (
    <section id="circ" className="relative scroll-mt-14 overflow-hidden border-t border-line py-20 sm:py-24">
      {/* ambient indigo wash */}
      <div
        aria-hidden
        className="wash right-[-10%] top-[8%] h-[440px] w-[440px]"
        style={{ ["--blob" as string]: "var(--indigo)", ["--blob-o" as string]: 0.08 }}
      />
      <div
        aria-hidden
        className="wash left-[-6%] bottom-[6%] h-[360px] w-[360px]"
        style={{ ["--blob" as string]: "var(--gA)", ["--blob-o" as string]: 0.06, ["--blob-t" as string]: "38s" }}
      />

      <div className="relative mx-auto max-w-[1500px] px-4 sm:px-6">
        <SectionHead
          index="02"
          code="CIRC Console"
          hue="var(--indigo)"
          title={
            <>
              The refund curve,{" "}
              <span className="hl" style={{ ["--hl" as string]: "var(--indigo)" }}>
                printed
              </span>{" "}
              on the instrument.
            </>
          }
          action="drag the lever or tap a grade — the exact dollars you'd get back appear instantly."
          right={
            <div
              className="rounded-2xl border bg-panel px-4 py-3 text-right shadow-[0_10px_28px_-14px_rgba(79,70,229,0.35)]"
              style={{ borderColor: `color-mix(in srgb, ${tierColor} 40%, var(--line))` }}
            >
              <span className="block font-tech text-[9px] uppercase tracking-[0.2em] text-faint">
                Live readout
              </span>
              <span
                className="font-tech text-[13px] font-semibold tabular-nums"
                style={{ color: tierColor }}
              >
                GRADE {tier.grade} · {formatUSD(tier.refund)}
              </span>
            </div>
          }
        />

        <div className="mt-10 grid gap-5 lg:grid-cols-[1.15fr_1fr]">
          {/* ——— curve instrument ——— */}
          <Rise>
            <Panel
              label="Condition-Indexed Refund Curve — specimen MSRP $380.00"
              accent="indigo"
              right={<Chip tone="indigo">Fixture v2</Chip>}
            >
              <div className="p-4 sm:p-6">
                <CurveSvg idx={idx} onSelect={setIdx} />
              </div>
            </Panel>
          </Rise>

          {/* ——— readout column ——— */}
          <div className="flex flex-col gap-5">
            <Rise delay={0.08}>
              <Panel label="Refund at selected grade" accent="indigo">
                <div className="flex flex-wrap items-end justify-between gap-4 p-4 sm:p-6">
                  <div>
                    <RollingNumber value={tier.refund} style={{ color: tierColor }} />
                    <p className="mt-2 font-tech text-[11px] uppercase tracking-[0.16em] text-faint">
                      {Math.round(tier.rate * 100)}% of face value · exact, not an estimate
                    </p>
                  </div>
                  <span
                    className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl font-display text-2xl font-bold"
                    style={{
                      color: tierColor,
                      background: `color-mix(in srgb, ${tierColor} 10%, transparent)`,
                      boxShadow: `inset 0 0 0 2px color-mix(in srgb, ${tierColor} 55%, transparent)`,
                    }}
                  >
                    {tier.grade}
                  </span>
                </div>
              </Panel>
            </Rise>

            <Rise delay={0.14}>
              <Panel label="Grade selector — drag it" accent="indigo">
                <div className="p-4 sm:p-6">
                  <ConditionLever idx={idx} onChange={setIdx} />
                  <p className="mt-3 border-t border-dashed border-line pt-3 font-tech text-[11px] leading-relaxed text-dim">
                    <span className="font-semibold text-ink">{tier.condition}.</span>{" "}
                    {tier.wear}
                  </p>
                </div>
              </Panel>
            </Rise>
          </div>
        </div>

        {/* ——— tier ladder ——— */}
        <Rise delay={0.05}>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {CIRC_GRADES.map((g, i) => {
              const active = i === idx;
              const c = GRADE_COLORS[i];
              return (
                <button
                  key={g.grade}
                  type="button"
                  onClick={() => setIdx(i)}
                  aria-pressed={active}
                  data-cursor="inspect"
                  className="group relative overflow-hidden rounded-2xl border p-4 text-left transition-all duration-300 hover:-translate-y-1"
                  style={{
                    borderColor: active
                      ? `color-mix(in srgb, ${c} 55%, transparent)`
                      : "var(--line)",
                    background: active
                      ? `color-mix(in srgb, ${c} 7%, var(--panel))`
                      : "color-mix(in srgb, var(--panel) 88%, transparent)",
                    boxShadow: active
                      ? `0 16px 36px -16px color-mix(in srgb, ${c} 45%, transparent)`
                      : undefined,
                  }}
                >
                  {/* grade color tab */}
                  <span
                    aria-hidden
                    className="absolute inset-x-0 top-0 h-[3px] transition-opacity"
                    style={{ background: c, opacity: active ? 1 : 0.3 }}
                  />
                  <div className="flex items-center justify-between">
                    <span
                      className="grid h-8 w-8 place-items-center rounded-xl font-display text-lg font-bold"
                      style={{
                        color: c,
                        background: `color-mix(in srgb, ${c} 10%, transparent)`,
                      }}
                    >
                      {g.grade}
                    </span>
                    <RollingNumber
                      value={g.refund}
                      small
                      style={{ color: active ? c : undefined }}
                      className={active ? "" : "text-dim"}
                    />
                  </div>
                  <p className="mt-3 font-tech text-[10px] uppercase leading-relaxed tracking-[0.1em] text-faint">
                    {g.condition}
                  </p>
                  <AnimatePresence initial={false}>
                    {active ? (
                      <motion.p
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.22 }}
                        className="overflow-hidden font-display text-[12.5px] leading-relaxed text-dim"
                      >
                        <span
                          className="mt-2 block border-t border-dashed pt-2"
                          style={{ borderColor: `color-mix(in srgb, ${c} 35%, transparent)` }}
                        >
                          {g.wear}
                        </span>
                      </motion.p>
                    ) : null}
                  </AnimatePresence>
                </button>
              );
            })}
          </div>
        </Rise>

        {/* ——— jurisdiction ——— */}
        <div className="mt-5 grid gap-5 lg:grid-cols-2">
          <Rise>
            <Panel
              label="Jurisdiction fixture — your rights stay yours"
              right={
                <div className="flex overflow-hidden rounded-full border border-line">
                  {JURISDICTIONS.map((j) => (
                    <button
                      key={j.code}
                      type="button"
                      onClick={() => setJuris(j.code)}
                      aria-pressed={juris === j.code}
                      className={cn(
                        "px-3 py-1.5 font-tech text-[10px] font-semibold uppercase tracking-[0.16em] transition-colors",
                        juris === j.code
                          ? "bg-indigo text-white"
                          : "text-dim hover:text-ink",
                      )}
                    >
                      {j.short}
                    </button>
                  ))}
                </div>
              }
            >
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={juris}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.2 }}
                  className="space-y-3 p-4 sm:p-6"
                >
                  <Chip tone="indigo">{jurisFixture.verificationWindow}</Chip>
                  <p className="font-display text-[12.5px] leading-relaxed text-dim">
                    {jurisFixture.statutoryNote}
                  </p>
                  <p className="font-display text-[12.5px] leading-relaxed text-ink/80">
                    {jurisFixture.policyNote}
                  </p>
                  <Chip tone="warn">{jurisFixture.disclaimer}</Chip>
                </motion.div>
              </AnimatePresence>
            </Panel>
          </Rise>

          {/* ——— $F module ——— */}
          <Rise delay={0.08}>
            <Panel
              label="Misdeclaration determinant — $F"
              accent="warn"
              right={<Chip tone="warn">Demo input</Chip>}
            >
              <div className="grid gap-5 p-4 sm:p-6 md:grid-cols-[1fr_auto]">
                <div>
                  <p className="font-display text-[12.5px] leading-relaxed text-dim">
                    {MISDECLARATION.explanation}
                  </p>
                  <p className="mt-3 font-display text-[12px] font-medium leading-relaxed text-warn">
                    {MISDECLARATION.disclaimer}
                  </p>
                </div>
                <div className="flex flex-col gap-3 md:items-end">
                  <div className="flex items-stretch overflow-hidden rounded-full border border-line bg-panel">
                    <button
                      type="button"
                      onClick={() => stepF(-1)}
                      className="grid w-11 place-items-center font-tech text-lg text-dim transition-colors hover:bg-panel-2 hover:text-sig"
                      aria-label="Decrease $F by 0.50"
                    >
                      −
                    </button>
                    <span className="grid min-w-28 place-items-center border-x border-line px-3 py-2 font-tech text-xl font-semibold tabular-nums text-ink">
                      {formatUSD(fValue)}
                    </span>
                    <button
                      type="button"
                      onClick={() => stepF(1)}
                      className="grid w-11 place-items-center font-tech text-lg text-dim transition-colors hover:bg-panel-2 hover:text-sig"
                      aria-label="Increase $F by 0.50"
                    >
                      +
                    </button>
                  </div>
                  <div className="font-tech text-[10px] uppercase tracking-[0.16em] text-faint">
                    Range $0 – $50 · step $0.50
                  </div>
                </div>
              </div>
              <div className="rounded-b-2xl border-t border-line bg-panel-2/60 px-4 py-3 sm:px-6">
                <p className="font-tech text-[10px] uppercase tracking-[0.16em] text-faint">
                  Scenario — you declare {tier.grade}, the lab finds {foundTier.grade}
                </p>
                <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 font-tech text-[12px] text-dim">
                  <span className="tabular-nums">{formatUSD(foundTier.refund)}</span>
                  <span className="text-faint">−</span>
                  <span className="tabular-nums text-warn">{formatUSD(fValue)}</span>
                  <span className="text-faint">=</span>
                  <RollingNumber
                    value={netAfterF}
                    small
                    style={{ color: GRADE_COLORS[foundIdx] }}
                  />
                  <span className="text-[10px] uppercase tracking-[0.14em] text-faint">
                    returned to you
                  </span>
                </div>
              </div>
            </Panel>
          </Rise>
        </div>

        <Rise>
          <Bracket className="mt-6 rounded-2xl border border-line bg-panel/60 p-4" color="line">
            <p className="font-display text-[12.5px] leading-relaxed text-dim">
              The ladder above is ProofReturn&apos;s own contractual policy sketch
              — a fixture for this demo. Statutory consumer rights (withdrawal,
              implied warranty, defect remedies) are a separate lane and are never
              reduced by this curve. Nothing here is legal advice.
            </p>
          </Bracket>
        </Rise>
      </div>
    </section>
  );
}
