import { circleTextPath, rosetteLayerPaths } from "@/lib/guilloche";
import { cn } from "@/lib/utils";

/* ————————————————————————————————————————————————
   Engraved rule — thin · thick · thin, the certificate border
———————————————————————————————————————————————— */

export function Rule({
  className,
  draw = false,
  thick = 2,
}: {
  className?: string;
  draw?: boolean;
  thick?: number;
}) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "relative w-full border-t border-ink/70",
        draw && "rule-draw origin-left",
        className,
      )}
      style={{ borderTopWidth: thick }}
    >
      <div className="absolute inset-x-0 -top-[5px] border-t border-ink/60" style={{ borderTopWidth: 1 }} />
      <div className="absolute inset-x-0 top-[5px] border-t border-ink/60" style={{ borderTopWidth: 1 }} />
    </div>
  );
}

/* ————————————————————————————————————————————————
   Rosette — layered guilloché medallion
———————————————————————————————————————————————— */

export function Rosette({
  size = 96,
  count = 5,
  phase = 0,
  className,
  strokeWidth = 0.5,
  color = "var(--ink)",
}: {
  size?: number;
  count?: number;
  phase?: number;
  className?: string;
  strokeWidth?: number;
  color?: string;
}) {
  const c = size / 2;
  const paths = rosetteLayerPaths(c, c, size / 2 - 2, count, phase);
  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      width={size}
      height={size}
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <g fill="none" stroke={color} strokeWidth={strokeWidth} opacity={0.85}>
        {paths.map((d, i) => (
          <path key={i} d={d} />
        ))}
      </g>
    </svg>
  );
}

/* ————————————————————————————————————————————————
   Seal — circular engraved text around a medallion
———————————————————————————————————————————————— */

export function Seal({
  size = 118,
  text = "PROOFRETURN · CERTIFIED OPEN BOX · DEMONSTRATION ·",
  center,
  sub,
  color = "var(--pr-green)",
  className,
}: {
  size?: number;
  text?: string;
  center: string;
  sub?: string;
  color?: string;
  className?: string;
}) {
  const c = size / 2;
  const r = c - 11;
  return (
    <div className={cn("relative", className)} style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} aria-hidden="true" focusable="false">
        <defs>
          <path id={`seal-arc-${size}`} d={circleTextPath(c, c, r)} fill="none" />
        </defs>
        <circle cx={c} cy={c} r={c - 1} fill="none" stroke={color} strokeWidth={1} />
        <circle cx={c} cy={c} r={c - 3.5} fill="none" stroke={color} strokeWidth={0.5} />
        <circle cx={c} cy={c} r={r - 9} fill="none" stroke={color} strokeWidth={0.5} />
        <g opacity={0.5}>
          {rosetteLayerPaths(c, c, r - 11, 3, 0).map((d, i) => (
            <path key={i} d={d} fill="none" stroke={color} strokeWidth={0.35} />
          ))}
        </g>
        <text
          fill={color}
          fontSize={Math.max(6.2, size / 15)}
          fontFamily="var(--font-plex-mono)"
          fontWeight={600}
          letterSpacing="1.6"
        >
          <textPath href={`#seal-arc-${size}`} startOffset="25%" textAnchor="middle">
            {text}
          </textPath>
        </text>
        <text
          x={c}
          y={c + size / 9}
          textAnchor="middle"
          fill={color}
          fontSize={size / 5.4}
          fontFamily="var(--font-fraunces)"
          fontWeight={700}
        >
          {center}
        </text>
        {sub ? (
          <text
            x={c}
            y={c + size / 4.6}
            textAnchor="middle"
            fill={color}
            fontSize={size / 16}
            fontFamily="var(--font-plex-mono)"
            letterSpacing="1"
          >
            {sub}
          </text>
        ) : null}
      </svg>
    </div>
  );
}

/* ————————————————————————————————————————————————
   Microtext strip — real anti-forgery print technique
———————————————————————————————————————————————— */

export function MicrotextStrip({
  text,
  className,
  repeat = 60,
}: {
  text: string;
  className?: string;
  repeat?: number;
}) {
  return (
    <div className={cn("microtext", className)} aria-hidden="true">
      {Array.from({ length: repeat }, (_, i) => (
        <span key={i}>{`${text} `}</span>
      ))}
    </div>
  );
}

/* ————————————————————————————————————————————————
   Rubber stamp
———————————————————————————————————————————————— */

export function Stamp({
  children,
  tone = "ink",
  size = "sm",
  flat = false,
  rotate = -2,
  className,
}: {
  children: React.ReactNode;
  tone?: "ink" | "green" | "red" | "bronze";
  size?: "sm" | "lg";
  flat?: boolean;
  rotate?: number;
  className?: string;
}) {
  const toneClass =
    tone === "green"
      ? "text-pr-green"
      : tone === "red"
        ? "text-pr-red"
        : tone === "bronze"
          ? "text-pr-bronze"
          : "text-ink";
  return (
    <span
      className={cn("stamp", toneClass, size === "lg" && "stamp-lg", flat && "stamp-flat", className)}
      style={{ transform: `rotate(${rotate}deg)` }}
    >
      {children}
    </span>
  );
}

/* ————————————————————————————————————————————————
   Corner ornament for plate frames
———————————————————————————————————————————————— */

export function CornerMark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 26 26" aria-hidden="true" focusable="false">
      <g stroke="var(--ink)" strokeWidth="0.8" fill="none">
        <path d="M 1 1 H 8 M 1 1 V 8" />
        <circle cx="4" cy="4" r="1.6" fill="var(--ink)" stroke="none" />
      </g>
    </svg>
  );
}
