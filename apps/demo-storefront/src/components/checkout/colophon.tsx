import { MicrotextStrip, Rule, Rosette } from "@/components/ornament/ornaments";

/**
 * The colophon — where a print run signs its work and confesses its fictions.
 */
export function Colophon() {
  return (
    <footer className="mt-auto border-t border-ink/60 bg-paper-2/60">
      <div className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <div className="flex flex-col items-center text-center">
          <Rosette size={72} count={5} className="opacity-70" />
          <p className="engraved mt-4 text-2xl font-semibold uppercase tracking-[0.12em] text-ink">
            ProofReturn
          </p>
          <p className="mt-1 font-ledger text-[9px] uppercase tracking-[0.3em] text-ink-soft">
            The Intaglio Storefront · demonstration edition
          </p>
        </div>

        <Rule className="my-8" />

        <div className="grid gap-8 text-center sm:grid-cols-3 sm:text-left">
          <div>
            <p className="font-ledger text-[9px] font-semibold uppercase tracking-[0.26em] text-ink">
              The concept
            </p>
            <p className="mt-3 font-ledger text-[10px] leading-[1.9] text-ink-soft">
              Trust used to be printed — guilloché, serials, seals. ProofReturn sells trust, so its
              storefront is set like money: every fine print pulled into the light of the plate.
            </p>
          </div>
          <div>
            <p className="font-ledger text-[9px] font-semibold uppercase tracking-[0.26em] text-ink">
              Disclosures
            </p>
            <p className="mt-3 font-ledger text-[10px] leading-[1.9] text-ink-soft">
              Front-end exploration only. Products, passports, and policies are local fixtures;
              jurisdiction notes are illustrative and are not legal advice. Checkout is a simulated
              Sandbox flow — no payment occurs and no data leaves the browser.
            </p>
          </div>
          <div>
            <p className="font-ledger text-[9px] font-semibold uppercase tracking-[0.26em] text-ink">
              The press
            </p>
            <p className="mt-3 font-ledger text-[10px] leading-[1.9] text-ink-soft">
              Next.js 16 · React 19 · TypeScript · Tailwind CSS 4 · Framer Motion · GSAP
              ScrollTrigger · Canvas guilloché · Fraunces &amp; IBM Plex Mono. All engraving is
              procedural — no images were harmed.
            </p>
          </div>
        </div>

        <div className="mt-10">
          <MicrotextStrip
            text="PROOFRETURN · DEMO STOREFRONT · SIMULATED · SPECIMEN · MMXXVI · THE CURVE IS THE CONTRACT"
            repeat={40}
          />
        </div>
        <p className="mt-4 text-center font-ledger text-[8px] uppercase tracking-[0.34em] text-ink-soft/80">
          Plate series of one — printed nowhere, rendered everywhere
        </p>
      </div>
    </footer>
  );
}
