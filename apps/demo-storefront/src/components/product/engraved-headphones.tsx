"use client";

import { useId } from "react";
import { motion } from "framer-motion";
import { CALLOUTS, type Callout } from "@/lib/data";

/**
 * The portrait — a procedural intaglio engraving of the object,
 * hatched like banknote portraiture, dimensioned like an assay plate.
 * When `interactive`, its seven inspection points become readable records.
 */
export function EngravedHeadphones({
  interactive = false,
  activeId,
  onSelect,
  className,
}: {
  interactive?: boolean;
  activeId?: string | null;
  onSelect?: (id: string | null) => void;
  className?: string;
}) {
  const uid = useId().replace(/[:]/g, "");
  const hA = `eh-hatchA-${uid}`;
  const hB = `eh-hatchB-${uid}`;

  const drivers = (cx: number) =>
    [
      [46, 62],
      [37, 52],
      [29, 42],
      [21, 31],
      [13, 20],
      [6, 9],
    ].map(([rx, ry], i) => (
      <ellipse
        key={i}
        cx={cx}
        cy={430}
        rx={rx}
        ry={ry}
        fill="none"
        stroke="var(--ink)"
        strokeWidth={i === 0 ? 1.1 : 0.6}
        opacity={i === 0 ? 1 : 0.75}
      />
    ));

  const cushionRing = (cx: number) => {
    const x0 = cx - 60;
    const x1 = cx + 60;
    const rect = `M ${x0 + 46} 350 H ${x1 - 46} Q ${x1} 350 ${x1} 396 V 464 Q ${x1} 510 ${x1 - 46} 510 H ${x0 + 46} Q ${x0} 510 ${x0} 464 V 396 Q ${x0} 350 ${x0 + 46} 350 Z`;
    const ell = `M ${cx} 368 A 46 62 0 1 0 ${cx} 492 A 46 62 0 1 0 ${cx} 368 Z`;
    return (
      <path d={`${rect} ${ell}`} fill={`url(#${hB})`} fillRule="evenodd" stroke="var(--ink)" strokeWidth={1.2} />
    );
  };

  return (
    <svg
      viewBox="0 0 560 610"
      className={className}
      role="img"
      aria-label="Engraved technical portrait of the Auralis N°1 noise-cancelling headphones with seven inspection points"
    >
      <defs>
        <pattern id={hA} width="3.2" height="3.2" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="3.2" stroke="#221d12" strokeWidth="0.55" opacity="0.75" />
        </pattern>
        <pattern id={hB} width="2.2" height="2.2" patternTransform="rotate(-45)" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="2.2" stroke="#221d12" strokeWidth="0.5" opacity="0.85" />
        </pattern>
      </defs>

      {/* ——— Ground shadow ——— */}
      <ellipse cx="280" cy="568" rx="215" ry="15" fill={`url(#${hA})`} opacity="0.5" />
      <ellipse cx="280" cy="568" rx="215" ry="15" fill="none" stroke="var(--ink)" strokeWidth="0.8" opacity="0.6" />
      <ellipse cx="280" cy="568" rx="150" ry="9" fill="none" stroke="var(--ink)" strokeWidth="0.5" opacity="0.35" />

      {/* ——— Headband ——— */}
      <path
        d="M 130 302 C 130 126, 430 126, 430 302 L 402 302 C 402 152, 158 152, 158 302 Z"
        fill={`url(#${hA})`}
      />
      <path d="M 130 302 C 130 126, 430 126, 430 302" fill="none" stroke="var(--ink)" strokeWidth="1.4" />
      <path d="M 158 302 C 158 152, 402 152, 402 302" fill="none" stroke="var(--ink)" strokeWidth="1.2" />

      {/* ——— Headband cushion (hatched stroke band) ——— */}
      <path
        d="M 178 244 C 188 194, 224 170, 280 170 C 336 170, 372 194, 382 244"
        fill="none"
        stroke="var(--ink)"
        strokeWidth="22"
      />
      <path
        d="M 178 244 C 188 194, 224 170, 280 170 C 336 170, 372 194, 382 244"
        fill="none"
        stroke={`url(#${hB})`}
        strokeWidth="19"
      />
      <path
        d="M 178 244 C 188 194, 224 170, 280 170 C 336 170, 372 194, 382 244"
        fill="none"
        stroke="var(--sheet)"
        strokeWidth="1"
        strokeDasharray="2 6"
        opacity="0.9"
      />

      {/* ——— Yokes ——— */}
      {[130, 430].map((x) => (
        <g key={x}>
          <rect x={x - 9} y="302" width="18" height="48" rx="5" fill="var(--sheet)" stroke="var(--ink)" strokeWidth="1.1" />
          <circle cx={x} cy="356" r="9" fill="var(--sheet)" stroke="var(--ink)" strokeWidth="1.2" />
          <circle cx={x} cy="356" r="3" fill="var(--ink)" />
        </g>
      ))}

      {/* ——— Ear cups ——— */}
      {cushionRing(130)}
      {cushionRing(430)}
      {drivers(130)}
      {drivers(430)}
      <circle cx="130" cy="430" r="3" fill="var(--ink)" />
      <circle cx="430" cy="430" r="3" fill="var(--ink)" />

      {/* Control pills — right cup top edge */}
      {[396, 418, 440].map((x) => (
        <rect key={x} x={x} y="354" width="16" height="6" rx="3" fill="var(--sheet)" stroke="var(--ink)" strokeWidth="0.8" />
      ))}

      {/* Beam mic array — right cup outer edge */}
      {[400, 412, 424].map((y) => (
        <circle key={y} cx="479" cy={y} r="2.6" fill="none" stroke="var(--ink)" strokeWidth="0.8" />
      ))}
      {/* Port — right cup */}
      <circle cx="474" cy="462" r="3.4" fill="none" stroke="var(--ink)" strokeWidth="0.9" />
      <circle cx="474" cy="462" r="1.2" fill="var(--ink)" />

      {/* L / R */}
      <text x="130" y="533" textAnchor="middle" fontFamily="var(--font-plex-mono)" fontWeight={600} fontSize="12" fill="var(--ink)">
        L
      </text>
      <text x="430" y="533" textAnchor="middle" fontFamily="var(--font-plex-mono)" fontWeight={600} fontSize="12" fill="var(--ink)">
        R
      </text>

      {/* ——— Dimension lines (assay plate) ——— */}
      <g stroke="var(--ink)" strokeWidth="0.8" opacity="0.85">
        <line x1="70" y1="512" x2="70" y2="588" strokeDasharray="2 3" strokeWidth="0.5" />
        <line x1="490" y1="512" x2="490" y2="588" strokeDasharray="2 3" strokeWidth="0.5" />
        <line x1="70" y1="588" x2="490" y2="588" />
        <line x1="70" y1="582" x2="70" y2="594" />
        <line x1="490" y1="582" x2="490" y2="594" />
        <line x1="52" y1="350" x2="68" y2="350" strokeDasharray="2 3" strokeWidth="0.5" />
        <line x1="52" y1="510" x2="68" y2="510" strokeDasharray="2 3" strokeWidth="0.5" />
        <line x1="60" y1="350" x2="60" y2="510" />
        <line x1="54" y1="350" x2="66" y2="350" />
        <line x1="54" y1="510" x2="66" y2="510" />
        <line x1="474" y1="562" x2="516" y2="548" strokeDasharray="2 3" strokeWidth="0.5" />
      </g>
      <g
        fontFamily="var(--font-plex-mono)"
        fontSize="9"
        fill="var(--ink)"
        letterSpacing="1.4"
        stroke="var(--sheet)"
        strokeWidth="3"
        paintOrder="stroke"
      >
        <text x="280" y="604" textAnchor="middle">
          420 MM — ARCH SPAN
        </text>
        <text x="42" y="430" textAnchor="middle" transform="rotate(-90 42 430)" fontSize="8.5">
          160 MM — HOUSING
        </text>
        <text x="522" y="544" textAnchor="end">
          INTAKE 258.3 G
        </text>
      </g>
      {interactive && (
        <text
          x="552"
          y="24"
          textAnchor="end"
          fontFamily="var(--font-plex-mono)"
          fontSize="8"
          letterSpacing="1.8"
          fill="var(--ink-soft)"
        >
          PLATE 01 — AURALIS N°1
        </text>
      )}

      {/* ——— Inspection markers ——— */}
      {interactive &&
        CALLOUTS.map((c: Callout) => {
          const active = c.id === activeId;
          return (
            <g
              key={c.id}
              transform={`translate(${c.x} ${c.y})`}
              role="button"
              tabIndex={0}
              aria-pressed={active}
              aria-label={`Inspection point ${c.marker}: ${c.zone}. ${c.result}.`}
              onClick={() => onSelect?.(active ? null : c.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect?.(active ? null : c.id);
                }
              }}
              style={{ cursor: "pointer" }}
            >
              {active && (
                <motion.circle
                  r="14"
                  fill="none"
                  stroke="var(--pr-green)"
                  strokeWidth="1"
                  initial={{ opacity: 0.7, scale: 0.8 }}
                  animate={{ opacity: [0.7, 0], scale: [0.8, 1.5] }}
                  transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut" }}
                  style={{ transformOrigin: "center" }}
                />
              )}
              <circle
                r="11"
                fill={active ? "var(--pr-green)" : "var(--sheet)"}
                stroke={active ? "var(--pr-green)" : "var(--ink)"}
                strokeWidth="1.3"
              />
              <text
                y="3.5"
                textAnchor="middle"
                fontFamily="var(--font-plex-mono)"
                fontWeight={600}
                fontSize="10"
                fill={active ? "var(--sheet)" : "var(--ink)"}
              >
                {c.marker}
              </text>
            </g>
          );
        })}
    </svg>
  );
}
