"use client";

import { useState } from "react";
import { PlateFrame } from "@/components/ornament/plate-frame";
import { Stamp, Rule } from "@/components/ornament/ornaments";
import { Odometer } from "@/components/circ/odometer";
import { GradeLever } from "@/components/circ/grade-lever";
import { RefundCurve } from "@/components/circ/refund-curve";
import { CIRC_GRADES, formatUSD, JURISDICTIONS, MISDECLARATION, PRODUCT } from "@/lib/data";
import { cn } from "@/lib/utils";

function FieldSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="font-ledger text-[9px] font-semibold uppercase tracking-[0.22em] text-ink-soft">{label}</span>
      <span className="relative inline-block">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full cursor-pointer appearance-none border border-ink bg-sheet px-3 py-2.5 pr-8 font-ledger text-[12px] font-medium text-ink transition-colors hover:border-pr-green"
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <span aria-hidden="true" className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[9px] text-ink-soft">
          ▼
        </span>
      </span>
    </label>
  );
}

/**
 * PLATE II — THE CURVE (CIRC).
 * Financial transparency as an instrument: drag the grading needle,
 * watch the odometer count, read the fixture law beside the contract.
 */
export function CircPlate() {
  const [gradeIndex, setGradeIndex] = useState(0);
  const [jurIndex, setJurIndex] = useState(0);
  const [declared, setDeclared] = useState("A");
  const [actual, setActual] = useState("C");
  const [fee, setFee] = useState(MISDECLARATION.demoDefault);

  const grade = CIRC_GRADES[gradeIndex];
  const jur = JURISDICTIONS[jurIndex];
  const declaredTier = CIRC_GRADES.find((g) => g.grade === declared)!;
  const actualTier = CIRC_GRADES.find((g) => g.grade === actual)!;
  const mismatch = declared !== actual;
  const net = actualTier.refund - fee;
  const pct = Math.round(grade.rate * 100);

  return (
    <PlateFrame
      id="curve"
      numeral="II"
      title="The Curve"
      kicker="Plate II — Condition-Indexed Refund Curve · CIRC"
    >
      <p data-reveal className="mx-auto -mt-4 mb-10 max-w-[58ch] text-center font-ledger text-[12px] leading-relaxed text-ink-soft">
        Before you buy, the whole refund table is on the table. Drag the needle through the condition
        grades — the amount that returns to you is computed before your eyes, to the cent.
      </p>

      {/* ——— The instrument ——— */}
      <div data-reveal className="plate-panel p-4 sm:p-8">
        {/* tabs + fixture stamp */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div
            role="tablist"
            aria-label="Jurisdiction example"
            className="flex border border-ink"
            onKeyDown={(e) => {
              if (e.key === "ArrowRight") setJurIndex((i) => (i + 1) % JURISDICTIONS.length);
              if (e.key === "ArrowLeft") setJurIndex((i) => (i - 1 + JURISDICTIONS.length) % JURISDICTIONS.length);
            }}
          >
            {JURISDICTIONS.map((j, i) => (
              <button
                key={j.code}
                role="tab"
                aria-selected={i === jurIndex}
                onClick={() => setJurIndex(i)}
                className={cn(
                  "px-4 py-2 font-ledger text-[10px] font-semibold uppercase tracking-[0.2em] transition-colors sm:px-5",
                  i === jurIndex ? "bg-pr-green text-sheet" : "bg-transparent text-ink-soft hover:text-ink",
                )}
              >
                {j.short}
              </button>
            ))}
          </div>
          <Stamp tone="red" rotate={1.5}>
            {jur.disclaimer}
          </Stamp>
        </div>

        {/* curve + odometer */}
        <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_290px] lg:gap-10">
          <RefundCurve gradeIndex={gradeIndex} onChange={setGradeIndex} className="h-auto w-full" />

          <div className="flex flex-col justify-center border border-ink/40 bg-paper-2/60 p-5">
            <p className="font-ledger text-[9px] font-semibold uppercase tracking-[0.24em] text-ink-soft">
              Refund if returned in —
            </p>
            <p className="engraved mt-1 text-3xl font-bold text-ink">Grade {grade.grade}</p>
            <Odometer value={grade.refund} className="mt-4 text-5xl sm:text-[3.4rem]" />
            <p className="mt-3 font-ledger text-[10px] uppercase tracking-[0.18em] text-ink-soft">
              {pct}% of face value retained
            </p>
            <p className="engraved-text mt-3 text-[13px] italic leading-snug text-ink">{grade.condition}.</p>
            <p className="engraved-text text-[13px] italic leading-snug text-ink-soft">{grade.wear}</p>

            <div className="mt-5 border-t border-dashed border-ink/40 pt-4">
              <p className="font-ledger text-[10px] leading-[2] tracking-[0.08em] text-ink">
                {formatUSD(PRODUCT.msrp)} face value
                <br />× {pct}% (grade {grade.grade})
                <br />
                <span className="font-semibold text-pr-green">= {formatUSD(grade.refund)} returned</span>
              </p>
            </div>
          </div>
        </div>

        {/* lever */}
        <div className="mt-8 border-t border-ink/30 pt-8">
          <GradeLever gradeIndex={gradeIndex} onChange={setGradeIndex} />
        </div>
      </div>

      {/* ——— Statute vs contract ——— */}
      <div data-reveal className="mt-12 border border-ink/60 bg-sheet">
        <div className="grid md:grid-cols-2">
          <div className="border-b border-ink/30 p-6 md:border-b-0 md:border-r sm:p-8">
            <p className="font-ledger text-[10px] font-semibold uppercase tracking-[0.26em] text-pr-bronze">
              What statute gives you — {jur.label} · illustrative fixture
            </p>
            <p className="mt-4 font-ledger text-[12.5px] leading-relaxed text-ink">{jur.statutoryNote}</p>
            <p className="mt-4 flex items-center gap-2 font-ledger text-[10px] uppercase tracking-[0.16em] text-ink-soft">
              <span aria-hidden="true">⌛</span> {jur.verificationWindow}
            </p>
          </div>
          <div className="p-6 sm:p-8">
            <p className="font-ledger text-[10px] font-semibold uppercase tracking-[0.26em] text-pr-green">
              What ProofReturn promises — contractual
            </p>
            <p className="mt-4 font-ledger text-[12.5px] leading-relaxed text-ink">{jur.policyNote}</p>
            <p className="mt-4 font-ledger text-[10px] uppercase leading-[2] tracking-[0.16em] text-ink-soft">
              Printed on this plate: A {formatUSD(CIRC_GRADES[0].refund)} · B {formatUSD(CIRC_GRADES[1].refund)} · C{" "}
              {formatUSD(CIRC_GRADES[2].refund)} · D {formatUSD(CIRC_GRADES[3].refund)}
            </p>
          </div>
        </div>
        <div className="border-t border-ink/30 bg-paper-2/70 px-6 py-3 text-center sm:px-8">
          <p className="font-ledger text-[9.5px] uppercase tracking-[0.2em] text-ink-soft">
            The two are independent — statutory rights are neither replaced nor waived by the curve.
            Jurisdiction text is a fixture, not legal advice.
          </p>
        </div>
      </div>

      {/* ——— $F misdeclaration deterrent ——— */}
      <div data-reveal className="mt-12 border-[1.5px] border-pr-red/70 bg-sheet p-6 sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="engraved text-2xl font-semibold uppercase tracking-tight text-ink">
            The misdeclaration deterrent — <span className="text-pr-red">$F</span>
          </h3>
          <Stamp tone="red" rotate={-2}>
            {MISDECLARATION.disclaimer}
          </Stamp>
        </div>
        <p className="mt-4 max-w-[72ch] font-ledger text-[12px] leading-relaxed text-ink-soft">{MISDECLARATION.explanation}</p>

        <div className="mt-6 grid gap-5 md:grid-cols-3">
          <FieldSelect
            label="Grade you declare"
            value={declared}
            onChange={setDeclared}
            options={CIRC_GRADES.map((g) => ({ value: g.grade, label: `Grade ${g.grade} — ${formatUSD(g.refund)}` }))}
          />
          <FieldSelect
            label="Grade verified at intake"
            value={actual}
            onChange={setActual}
            options={CIRC_GRADES.map((g) => ({ value: g.grade, label: `Grade ${g.grade} — ${formatUSD(g.refund)}` }))}
          />
          <label className="flex flex-col gap-1.5">
            <span className="font-ledger text-[9px] font-semibold uppercase tracking-[0.22em] text-pr-red">
              $F — configurable demo value ({MISDECLARATION.unit})
            </span>
            <input
              type="number"
              min={MISDECLARATION.min}
              max={MISDECLARATION.max}
              step={MISDECLARATION.step}
              value={fee}
              onChange={(e) =>
                setFee(Math.max(MISDECLARATION.min, Math.min(MISDECLARATION.max, Number(e.target.value) || 0)))
              }
              className="w-full border border-ink bg-sheet px-3 py-2.5 font-ledger text-[12px] font-medium text-ink outline-none focus:border-pr-red"
              aria-describedby="fee-note"
            />
            <span id="fee-note" className="font-ledger text-[8.5px] uppercase tracking-[0.14em] text-ink-soft">
              Demo range $0–$50 · not a policy amount
            </span>
          </label>
        </div>

        <div className="mt-7 grid items-center gap-4 border-t border-dashed border-ink/40 pt-5 md:grid-cols-[1fr_auto]">
          <div className="font-ledger text-[11.5px] leading-[2.1] tracking-[0.06em] text-ink">
            {mismatch ? (
              <>
                Declared <b>{declared}</b> but verified <b>{actual}</b> → refund settles at the verified grade:{" "}
                <span className="font-semibold">{formatUSD(actualTier.refund)}</span>
                <br />
                minus $F <span className="text-pr-red">(demo)</span>:{" "}
                <span className="text-pr-red">− {formatUSD(fee)}</span>
                <br />
                <span className={cn("text-[13px] font-bold", net < 0 ? "text-pr-red" : "text-pr-green")}>
                  = {formatUSD(net)} net refund
                </span>
                {net < 0 && (
                  <span className="ml-2 text-[9px] uppercase tracking-[0.14em] text-pr-red">
                    raw demo arithmetic — a real policy would floor this
                  </span>
                )}
              </>
            ) : (
              <>
                Declared grade <b>{declared}</b> matches the verified grade — no deterrent applies.{" "}
                <span className="font-semibold text-pr-green">Full grade refund: {formatUSD(actualTier.refund)}</span>
              </>
            )}
          </div>
          <div className="hidden h-24 w-px bg-ink/20 md:block" aria-hidden="true" />
          <div className="max-w-[26ch] font-ledger text-[9.5px] uppercase leading-[1.9] tracking-[0.14em] text-ink-soft md:text-right">
            Honest declarations keep the curve honest. $F here is arithmetic on a demo input — nothing more.
          </div>
        </div>
      </div>

      {/* ——— Continue ——— */}
      <div data-reveal className="mt-12 flex flex-col items-center gap-3">
        <Rule draw thick={1} className="max-w-xs" />
        <p className="font-ledger text-[10px] uppercase tracking-[0.24em] text-ink-soft">
          The curve is printed on your receipt — now inspect what guarantees the grade
        </p>
        <a href="#passport" data-cursor="open" className="btn-engraved mt-2">
          Continue to the Passport — Plate III
        </a>
      </div>
    </PlateFrame>
  );
}
