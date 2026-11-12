"use client";

import { AnimatePresence, motion } from "framer-motion";
import { formatUSD } from "@/lib/data";
import { cn } from "@/lib/utils";

/**
 * RollingNumber — odometer-style counter for USD values.
 * Every character slot animates independently; the mono font
 * keeps column widths stable while digits roll.
 */
export function RollingNumber({
  value,
  className,
  style,
  small = false,
}: {
  value: number;
  className?: string;
  style?: React.CSSProperties;
  small?: boolean;
}) {
  const text = formatUSD(value);
  return (
    <span
      style={style}
      className={cn(
        "inline-flex font-tech tabular-nums",
        small ? "text-[13px]" : "text-4xl sm:text-5xl",
        className,
      )}
      aria-label={text}
      role="text"
    >
      {text.split("").map((ch, i) => (
        <span
          key={i}
          className="inline-block w-[1ch] overflow-hidden"
          aria-hidden="true"
        >
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.span
              key={`${i}-${ch}`}
              initial={{ y: small ? 10 : 16, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: small ? -10 : -16, opacity: 0 }}
              transition={{ type: "spring", stiffness: 500, damping: 34 }}
              className="inline-block"
            >
              {ch}
            </motion.span>
          </AnimatePresence>
        </span>
      ))}
    </span>
  );
}
