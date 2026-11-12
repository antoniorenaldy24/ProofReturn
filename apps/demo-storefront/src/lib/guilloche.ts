/**
 * Guilloché engine — the anti-forgery mathematics of security print.
 *
 * Every rosette on this storefront is a hypotrochoid / modulated rose
 * computed at runtime, the same family of curves engraved on banknotes
 * and stock certificates. The decoration IS the math.
 */

export type RosetteOpts = {
  /** base radius */
  R: number;
  /** modulation amplitude, 0..0.5 */
  a: number;
  /** petal frequency */
  n: number;
  /** phase offset, radians */
  phase?: number;
  /** samples around the loop */
  steps?: number;
};

/** Polar point generator for one modulated rose ring. */
export function rosePoints(
  cx: number,
  cy: number,
  o: RosetteOpts,
): Array<[number, number]> {
  const steps = o.steps ?? 240;
  const pts: Array<[number, number]> = [];
  for (let i = 0; i <= steps; i++) {
    const t = (i / steps) * Math.PI * 2;
    const r = o.R * (1 + o.a * Math.sin(o.n * t + (o.phase ?? 0)));
    pts.push([cx + r * Math.cos(t), cy + r * Math.sin(t)]);
  }
  return pts;
}

/** Classic hypotrochoid ring — the true "spirograph" guilloché. */
export function hypotrochoidPoints(
  cx: number,
  cy: number,
  R: number,
  r: number,
  d: number,
  turns = 24,
  steps = 720,
): Array<[number, number]> {
  const pts: Array<[number, number]> = [];
  const end = Math.PI * 2 * turns;
  for (let i = 0; i <= steps; i++) {
    const t = (i / steps) * end;
    pts.push([
      cx + (R - r) * Math.cos(t) + d * Math.cos(((R - r) / r) * t),
      cy + (R - r) * Math.sin(t) - d * Math.sin(((R - r) / r) * t),
    ]);
  }
  return pts;
}

/** Points → SVG path string. */
export function toPath(pts: Array<[number, number]>): string {
  return pts.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(2)} ${p[1].toFixed(2)}`).join(" ") + " Z";
}

/** A full layered rosette as an array of SVG path strings. */
export function rosetteLayerPaths(
  cx: number,
  cy: number,
  R: number,
  count = 5,
  phase = 0,
): string[] {
  const paths: string[] = [];
  for (let k = 0; k < count; k++) {
    const f = k / Math.max(1, count - 1); // 0..1
    paths.push(
      toPath(
        rosePoints(cx, cy, {
          R: R * (0.32 + 0.68 * f),
          a: 0.06 + 0.1 * f,
          n: 12 + (k % 3) * 4,
          phase: phase + k * 0.35,
        }),
      ),
    );
  }
  return paths;
}

/** A running wave band — used for engraved borders under headings. */
export function waveBandPath(
  width: number,
  height: number,
  opts: { cycles?: number; amp?: number; phase?: number; steps?: number } = {},
): string {
  const { cycles = 6, amp = 0.5, phase = 0, steps = 240 } = opts;
  const mid = height / 2;
  const pts: Array<[number, number]> = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const x = t * width;
    const y =
      mid +
      (height / 2 - 1) * amp * Math.sin(t * Math.PI * 2 * cycles + phase) * Math.sin(t * Math.PI);
    pts.push([x, y]);
  }
  return pts.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(2)} ${p[1].toFixed(2)}`).join(" ");
}

/** Circle path for SVG textPath seals. Starts at top so text reads upright. */
export function circleTextPath(cx: number, cy: number, r: number): string {
  return `M ${cx} ${cy - r} A ${r} ${r} 0 1 1 ${cx - 0.01} ${cy - r}`;
}
