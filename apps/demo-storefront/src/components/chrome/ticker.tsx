import { cn } from "@/lib/utils";

/** journey palette cycling through the marquee dots */
const DOTS = ["var(--sig)", "var(--indigo)", "var(--teal)", "var(--ok)"];

export function Ticker({ items, className }: { items: string[]; className?: string }) {
  const row = (ariaHidden: boolean) => (
    <div aria-hidden={ariaHidden} className="flex shrink-0 items-center">
      {items.map((item, i) => (
        <span key={i} className="flex items-center">
          <span className="px-6 font-tech text-[10px] font-medium uppercase tracking-[0.22em] text-dim whitespace-nowrap">
            {item}
          </span>
          <span
            className="h-1.5 w-1.5 shrink-0 rounded-full"
            style={{ background: DOTS[i % DOTS.length], opacity: 0.75 }}
          />
        </span>
      ))}
    </div>
  );
  return (
    <div
      className={cn(
        "group relative flex overflow-hidden border-y border-line bg-panel/70 py-2.5",
        className,
      )}
    >
      <div className="marquee-track">
        {row(false)}
        {row(true)}
      </div>
      <span aria-hidden className="pointer-events-none absolute inset-y-0 left-0 w-24 bg-gradient-to-r from-paper to-transparent" />
      <span aria-hidden className="pointer-events-none absolute inset-y-0 right-0 w-24 bg-gradient-to-l from-paper to-transparent" />
    </div>
  );
}
