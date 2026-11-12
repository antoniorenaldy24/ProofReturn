import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

/* Shared HUD primitives for the LIVING LAB chrome. */

export function LED({
  color = "ok",
  pulse = false,
  className,
}: {
  color?: "ok" | "sig" | "warn" | "bad" | "faint" | "teal" | "indigo";
  pulse?: boolean;
  className?: string;
}) {
  const colors: Record<string, string> = {
    ok: "bg-ok text-ok",
    sig: "bg-sig text-sig",
    warn: "bg-warn text-warn",
    bad: "bg-bad text-bad",
    faint: "bg-faint text-faint",
    teal: "bg-teal text-teal",
    indigo: "bg-indigo text-indigo",
  };
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block h-[7px] w-[7px] rounded-full shrink-0",
        colors[color],
        pulse && "led-pulse",
        className,
      )}
    />
  );
}

export function Bracket({
  children,
  className,
  color = "line",
}: {
  children: React.ReactNode;
  className?: string;
  color?: "line" | "sig";
}) {
  const c = color === "sig" ? "border-sig/60" : "border-line";
  const tick = color === "sig" ? "bg-sig/70" : "bg-faint/60";
  return (
    <div className={cn("relative", className)}>
      <span aria-hidden className={cn("absolute -top-px -left-px h-2.5 w-2.5 border-t border-l", c)}>
        <span className={cn("absolute top-0 left-0 h-[3px] w-[3px]", tick)} />
      </span>
      <span aria-hidden className={cn("absolute -top-px -right-px h-2.5 w-2.5 border-t border-r", c)} />
      <span aria-hidden className={cn("absolute -bottom-px -left-px h-2.5 w-2.5 border-b border-l", c)} />
      <span aria-hidden className={cn("absolute -bottom-px -right-px h-2.5 w-2.5 border-b border-r", c)} />
      {children}
    </div>
  );
}

export function Chip({
  children,
  tone = "line",
  className,
}: {
  children: React.ReactNode;
  tone?: "line" | "sig" | "ok" | "warn" | "bad" | "teal" | "indigo";
  className?: string;
}) {
  const tones: Record<string, string> = {
    line: "border-line bg-panel text-dim",
    sig: "border-sig/30 bg-sig/[0.07] text-sig",
    ok: "border-ok/30 bg-ok/[0.07] text-ok",
    warn: "border-warn/30 bg-warn/[0.08] text-warn",
    bad: "border-bad/30 bg-bad/[0.07] text-bad",
    teal: "border-teal/30 bg-teal/[0.07] text-teal",
    indigo: "border-indigo/30 bg-indigo/[0.07] text-indigo",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-tech text-[10px] font-medium uppercase tracking-[0.14em] whitespace-nowrap",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Panel({
  children,
  className,
  label,
  right,
  tone = "panel",
  accent,
  lift,
}: {
  children: React.ReactNode;
  className?: string;
  label?: string;
  right?: React.ReactNode;
  tone?: "panel" | "inset";
  /** LED hue for the panel header */
  accent?: "ok" | "sig" | "warn" | "faint" | "teal" | "indigo";
  /** hover lift + colored shadow (pass the accent hue) */
  lift?: string;
}) {
  return (
    <section
      style={lift ? ({ "--lift": lift } as React.CSSProperties) : undefined}
      className={cn(
        "relative",
        tone === "panel" ? "panel" : "panel-inset",
        lift && "lift",
        className,
      )}
    >
      {label ? (
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-2.5">
          <div className="flex items-center gap-2 min-w-0">
            <LED color={accent ?? "faint"} />
            <h3 className="truncate font-tech text-[10px] font-semibold uppercase tracking-[0.2em] text-dim">
              {label}
            </h3>
          </div>
          {right}
        </header>
      ) : null}
      {children}
    </section>
  );
}

/**
 * Rise — scroll-triggered entrance wrapper. Content springs up softly;
 * `delay` staggers siblings so sections cascade in.
 */
export function Rise({
  children,
  delay = 0,
  y = 22,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  y?: number;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ type: "spring", stiffness: 110, damping: 20, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function SectionHead({
  index,
  code,
  title,
  right,
  hue = "var(--sig)",
  action,
  className,
}: {
  index: string;
  code: string;
  title: React.ReactNode;
  right?: React.ReactNode;
  /** accent hue (CSS color) for index + underline */
  hue?: string;
  /** plain-language "what you do here" line */
  action?: string;
  className?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 26 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ type: "spring", stiffness: 100, damping: 20 }}
      className={cn("flex flex-wrap items-end justify-between gap-x-8 gap-y-4", className)}
    >
      <div className="min-w-0">
        <div
          className="flex items-center gap-3 font-tech text-[11px] font-medium uppercase tracking-[0.28em]"
          style={{ color: hue }}
        >
          <span
            aria-hidden
            className="h-[3px] w-7 rounded-full"
            style={{ background: hue, animation: "dot-breathe 2.4s ease-in-out infinite", ["--dot" as string]: hue }}
          />
          <span>
            {index} <span className="opacity-40">{"//"}</span> {code}
          </span>
        </div>
        <h2 className="mt-3 font-display text-4xl font-semibold leading-[1.02] tracking-tight text-ink sm:text-5xl lg:text-6xl">
          {title}
        </h2>
        {action ? (
          <p className="mt-3 max-w-xl font-display text-[14px] leading-relaxed text-dim">
            <span className="font-semibold" style={{ color: hue }}>
              Try it:
            </span>{" "}
            {action}
          </p>
        ) : null}
      </div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </motion.div>
  );
}
