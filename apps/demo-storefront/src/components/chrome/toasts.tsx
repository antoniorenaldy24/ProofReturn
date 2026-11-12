"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useLedger } from "@/lib/store";
import { LED } from "./hud";

const BORDERS: Record<string, string> = {
  green: "border-l-[3px] !border-l-ok",
  red: "border-l-[3px] !border-l-bad",
  ink: "border-l-[3px] !border-l-sig",
};

export function Toasts() {
  const toasts = useLedger((s) => s.toasts);
  const dismiss = useLedger((s) => s.dismissToast);

  return (
    <div className="pointer-events-none fixed bottom-4 left-4 z-[90] flex w-[min(92vw,360px)] flex-col gap-2">
      <AnimatePresence initial={false}>
        {toasts.map((t) => (
          <motion.button
            key={t.id}
            type="button"
            onClick={() => dismiss(t.id)}
            initial={{ opacity: 0, x: -24, scale: 0.95, height: 0, marginBottom: 0 }}
            animate={{ opacity: 1, x: 0, scale: 1, height: "auto", marginBottom: 8 }}
            exit={{ opacity: 0, x: -24, scale: 0.95, height: 0, marginBottom: 0 }}
            transition={{ type: "spring", stiffness: 340, damping: 28 }}
            className={`pointer-events-auto flex cursor-pointer items-start gap-3 rounded-2xl border border-line bg-panel/95 px-3.5 py-3 text-left shadow-[0_12px_36px_-12px_rgba(21,23,26,0.22)] backdrop-blur-sm ${BORDERS[t.kind] ?? ""}`}
            aria-label={`${t.title} — tap to dismiss`}
          >
            <LED
              color={t.kind === "green" ? "ok" : t.kind === "red" ? "bad" : "sig"}
              pulse={t.kind !== "red"}
              className="mt-1"
            />
            <span className="min-w-0">
              <span className="block font-tech text-[11px] font-semibold uppercase tracking-[0.16em] text-ink">
                {t.title}
              </span>
              {t.line ? (
                <span className="mt-0.5 block font-display text-[12px] leading-relaxed text-dim">
                  {t.line}
                </span>
              ) : null}
            </span>
          </motion.button>
        ))}
      </AnimatePresence>
    </div>
  );
}
