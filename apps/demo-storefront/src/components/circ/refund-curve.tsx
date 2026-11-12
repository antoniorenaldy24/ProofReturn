"use client";

import { CIRC_GRADES, formatUSD } from "@/lib/data";
import { cn } from "@/lib/utils";

/**
 * The engraved curve — the refund tiers cut as an assay chart.
 * Not a bar chart: a line engraved on the plate, hatched beneath the
 * active tier, every point a readable record.
 */
export function RefundCurve({
  gradeIndex,
  onChange,
  className,
}: {
  gradeIndex: number;
  onChange: (i: number) => void;
  className?: string;
}) {
  const W = 720;
  const H = 300;
  const X0 = 86;
  const X1 = 690;
  const Y_BASE = 244;
  const Y_TOP = 44;

  const yOf = (v: number) => Y_BASE - (v / 400) * (Y_BASE - Y_TOP);
  const xOf = (i: number) => X0 + (i / (CIRC_GRADES.length - 1)) * (X1 - X0);

  const points = CIRC_GRADES.map((g, i) => ({ x: xOf(i), y: yOf(g.refund), g, i }));
  const line = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
  const active = points[gradeIndex];
  const areaPath = `M ${xOf(0)} ${Y_BASE} L ${points.slice(0, gradeIndex + 1).map((p) => `${p.x} ${p.y}`).join(" L ")} L ${active.x} ${Y_BASE} Z`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={className} role="group" aria-label="Refund curve by condition grade">
      <defs>
        <pattern id="rc-hatch" width="5" height="5" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="5" stroke="#1e4a36" strokeWidth="0.9" opacity="0.4" />
        </pattern>
      </defs>

      {/* grid */}
      {[0, 100, 200, 300, 400].map((v) => (
        <g key={v}>
          <line x1={X0 - 40} y1={yOf(v)} x2={X1 + 8} y2={yOf(v)} stroke="var(--ink)" strokeWidth="0.4" opacity="0.35" strokeDasharray={v === 0 ? "" : "2 5"} />
          <text x={X0 - 48} y={yOf(v) + 3} textAnchor="end" fontFamily="var(--font-plex-mono)" fontSize="9" fill="var(--ink-soft)">
            {v ? `$${v}` : "$0"}
          </text>
        </g>
      ))}
      <text x={X0 - 48} y={Y_TOP - 14} textAnchor="end" fontFamily="var(--font-plex-mono)" fontSize="8" letterSpacing="1.5" fill="var(--ink-soft)">
        USD
      </text>

      {/* hatched retained-value area up to the active tier */}
      <path d={areaPath} fill="url(#rc-hatch)" />
      <path d={areaPath} fill="none" stroke="var(--pr-green)" strokeWidth="0.8" opacity="0.7" />

      {/* the curve */}
      <path d={line} fill="none" stroke="var(--ink)" strokeWidth="1.6" />

      {/* baseline */}
      <line x1={X0 - 40} y1={Y_BASE} x2={X1 + 8} y2={Y_BASE} stroke="var(--ink)" strokeWidth="1.2" />

      {/* active vertical hairline */}
      <line x1={active.x} y1={active.y} x2={active.x} y2={Y_BASE} stroke="var(--pr-green)" strokeWidth="0.8" strokeDasharray="3 4" />

      {/* points */}
      {points.map((p) => {
        const isActive = p.i === gradeIndex;
        return (
          <g
            key={p.g.grade}
            transform={`translate(${p.x} ${p.y})`}
            role="button"
            tabIndex={0}
            aria-label={`Grade ${p.g.grade}: ${formatUSD(p.g.refund)} — ${Math.round(p.g.rate * 100)}% refund`}
            onClick={() => onChange(p.i)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onChange(p.i);
              }
            }}
            style={{ cursor: "pointer" }}
          >
            <circle r={isActive ? 16 : 22} fill="transparent" />
            <circle r={isActive ? 8 : 5.5} fill="var(--sheet)" stroke={isActive ? "var(--pr-green)" : "var(--ink)"} strokeWidth={isActive ? 2 : 1.2} />
            {isActive && <circle r="2.4" fill="var(--pr-green)" />}
            <text
              y={-16}
              textAnchor="middle"
              fontFamily="var(--font-plex-mono)"
              fontWeight={isActive ? 600 : 400}
              fontSize="10.5"
              fill={isActive ? "var(--pr-green)" : "var(--ink)"}
              stroke="var(--sheet)"
              strokeWidth="3"
              paintOrder="stroke"
            >
              {formatUSD(p.g.refund)}
            </text>
            <text
              y={Y_BASE - p.y + 20}
              textAnchor="middle"
              fontFamily="var(--font-plex-mono)"
              fontSize="9.5"
              letterSpacing="1.6"
              fill={isActive ? "var(--pr-green)" : "var(--ink-soft)"}
              fontWeight={isActive ? 600 : 400}
            >
              GRADE {p.g.grade}
            </text>
          </g>
        );
      })}

      <text x={X1} y={Y_BASE + 34} textAnchor="end" fontFamily="var(--font-plex-mono)" fontSize="8" letterSpacing="1.8" fill="var(--ink-soft)" opacity="0.8">
        VERIFIED CONDITION AT RETURN →
      </text>
      <text x={X0 - 40} y={Y_BASE + 34} fontFamily="var(--font-plex-mono)" fontSize="8" letterSpacing="1.8" fill="var(--ink-soft)" opacity="0.8">
        ← REFUND PAID
      </text>
    </svg>
  );
}
