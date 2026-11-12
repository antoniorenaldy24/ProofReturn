import { DEMO_DISCLAIMER, SECTIONS } from "@/lib/data";
import { LED } from "./chrome/hud";

const DISCLAIMERS = [
  "CIRC refund ladder is a demonstration fixture — a contractual policy sketch, not legal advice.",
  "$F misdeclaration value is a configurable demo input; no published formula exists.",
  "Jurisdiction notes (US-CA / EU) are illustrative. Statutory consumer rights exist independently of any store policy.",
  "PayPal flow is a sandbox simulation. No session opens, no funds move, no order exists.",
];

export function Footer() {
  return (
    <footer className="relative mt-auto overflow-hidden border-t border-line bg-panel/40 pb-[env(safe-area-inset-bottom)]">
      {/* soft closing wash — the journey settles back to paper */}
      <div
        aria-hidden
        className="wash left-1/2 top-[-30%] h-[420px] w-[720px] -translate-x-1/2"
        style={{ ["--blob" as string]: "var(--ok)", ["--blob-o" as string]: 0.05 }}
      />
      <div className="relative mx-auto grid max-w-[1500px] gap-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.2fr_0.8fr_1.6fr]">
        <div>
          <div className="flex items-center gap-3">
            <span className="relative grid h-7 w-7 place-items-center rounded-lg border border-sig/60">
              <span className="h-2.5 w-2.5 rounded-[3px] bg-sig" />
            </span>
            <span className="font-display text-[15px] font-semibold tracking-tight">ProofReturn</span>
          </div>
          <p className="mt-4 max-w-xs font-display text-[12.5px] leading-relaxed text-dim">
            {DEMO_DISCLAIMER}
          </p>
        </div>
        <nav aria-label="Footer">
          <h3 className="font-tech text-[10px] font-semibold uppercase tracking-[0.22em] text-faint">
            The journey
          </h3>
          <ul className="mt-4 space-y-2.5">
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  className="group flex items-center gap-2.5 font-display text-[12.5px] text-dim transition-colors hover:text-ink"
                >
                  <span
                    aria-hidden
                    className="grid h-5 w-5 place-items-center rounded-full font-tech text-[8px] font-bold text-white transition-transform group-hover:scale-110"
                    style={{ background: s.hue }}
                  >
                    {s.index}
                  </span>
                  {s.human}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div>
          <h3 className="flex items-center gap-2 font-tech text-[10px] font-semibold uppercase tracking-[0.22em] text-faint">
            <LED color="warn" pulse /> Simulation notices
          </h3>
          <ul className="mt-4 space-y-2">
            {DISCLAIMERS.map((d, i) => (
              <li key={i} className="flex gap-2.5 font-display text-[12px] leading-relaxed text-dim">
                <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-warn/70" aria-hidden />
                {d}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <div className="relative border-t border-line">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
          <span className="font-tech text-[10px] uppercase tracking-[0.2em] text-faint">
            Return Lab · Built for demonstration — no backend, no payments, no records
          </span>
          <span className="font-tech text-[10px] uppercase tracking-[0.2em] text-faint">
            Unit PR-0038 · Fixture set 2026-10
          </span>
        </div>
      </div>
    </footer>
  );
}
