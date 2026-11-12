export function Overlay() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-40">
      <div className="scanlines absolute inset-0" />
      <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-carbon/80 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-carbon/80 to-transparent" />
    </div>
  );
}
