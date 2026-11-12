"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useLedger } from "@/lib/store";
import { cn } from "@/lib/utils";

/**
 * Stamp toasts — every important action lands as a small rubber stamp
 * pressed at the edge of the sheet.
 */
export function StampToasts() {
  const toasts = useLedger((s) => s.toasts);
  const dismiss = useLedger((s) => s.dismissToast);

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-4 right-4 z-[95] flex flex-col items-end gap-2"
    >
      <AnimatePresence>
        {toasts.map((t) => (
          <motion.button
            key={t.id}
            type="button"
            onClick={() => dismiss(t.id)}
            initial={{ opacity: 0, y: 14, rotate: 4, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, rotate: -1, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.97 }}
            transition={{ type: "spring", stiffness: 420, damping: 26 }}
            className={cn(
              "pointer-events-auto block border-[1.5px] bg-sheet/95 px-4 py-2.5 text-left shadow-[3px_3px_0_rgba(34,29,18,0.25)] backdrop-blur-[2px]",
              t.kind === "green"
                ? "border-pr-green text-pr-green"
                : t.kind === "red"
                  ? "border-pr-red text-pr-red"
                  : "border-ink text-ink",
            )}
            data-cursor="read"
          >
            <span className="block font-ledger text-[10px] font-semibold uppercase tracking-[0.22em]">
              {t.title}
            </span>
            {t.line ? (
              <span className="mt-0.5 block font-ledger text-[9px] uppercase tracking-[0.14em] opacity-70">
                {t.line}
              </span>
            ) : null}
          </motion.button>
        ))}
      </AnimatePresence>
    </div>
  );
}
