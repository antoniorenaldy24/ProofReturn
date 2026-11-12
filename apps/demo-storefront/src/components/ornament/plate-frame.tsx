import { Rule, Rosette } from "@/components/ornament/ornaments";
import { cn } from "@/lib/utils";

/**
 * PlateFrame — every section of the storefront is an engraved plate:
 * numbered like a print run, ruled like a certificate.
 */
export function PlateFrame({
  id,
  numeral,
  title,
  kicker,
  children,
  className,
}: {
  id: string;
  numeral: string;
  title: string;
  kicker: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-heading`}
      className={cn("relative mx-auto w-full max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6 sm:py-28", className)}
    >
      <div data-reveal className="flex flex-col items-center text-center">
        <div className="flex items-center gap-4 sm:gap-6">
          <span className="hidden h-px w-16 bg-ink/50 sm:block sm:w-24" aria-hidden="true" />
          <span className="relative flex h-14 w-14 items-center justify-center sm:h-16 sm:w-16">
            <Rosette size={56} count={4} className="absolute inset-0 m-auto opacity-70" />
            <span className="engraved text-sm font-semibold text-ink sm:text-base">{numeral}</span>
          </span>
          <span className="hidden h-px w-16 bg-ink/50 sm:block sm:w-24" aria-hidden="true" />
        </div>
        <p className="mt-4 font-ledger text-[10px] font-semibold uppercase tracking-[0.34em] text-ink-soft">
          {kicker}
        </p>
        <h2
          id={`${id}-heading`}
          className="engraved mt-3 text-4xl font-semibold uppercase leading-none tracking-tight text-ink sm:text-5xl lg:text-6xl"
        >
          {title}
        </h2>
      </div>

      <div className="mt-10 sm:mt-14">{children}</div>
    </section>
  );
}
