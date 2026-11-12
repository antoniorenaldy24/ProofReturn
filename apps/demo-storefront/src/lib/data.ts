/**
 * ProofReturn — Demo Storefront fixtures.
 *
 * EVERYTHING in this file is local, illustrative front-end mock data.
 * Nothing here is a real product, policy, legal statement, or payment.
 */

export const DEMO_DISCLAIMER =
  "Front-end demonstration. All records, amounts, and verifications shown are local fixtures — simulated, not authoritative.";

/* ————————————————————————————————————————————————
   THE OBJECT — product fixture
———————————————————————————————————————————————— */

export type Callout = {
  id: string;
  marker: string; // ①..⑦ style index label
  x: number; // SVG coordinate (viewBox 0 0 560 600)
  y: number;
  zone: string;
  result: "PASS" | "PASS · NOTE";
  note: string;
  inspector: string;
  date: string;
};

export const PRODUCT = {
  name: "Auralis N°1",
  tagline: "Adaptive Noise-Cancelling Headphones",
  msrp: 380,
  minorUnits: 38000,
  currency: "USD",
  currencySymbol: "$",
  sku: "PR-HP-XM5",
  modelCode: "AUR-NC1-OBLK",
  origin: "Certified Open-Box — customer return, unopened seal line verified",
  condition: {
    grade: "A" as const,
    label: "Grade A — Like-new",
    note: "Seal line verified at intake; no functional or cosmetic defects found across 7 inspection points.",
  },
  specs: [
    { label: "Drivers", value: "40 mm beryllium-coated dynamic" },
    { label: "Noise cancellation", value: "Hybrid adaptive, −38 dB effective" },
    { label: "Battery", value: "32 h ANC on · 5 min → 3 h fast charge" },
    { label: "Codecs", value: "LDAC · aptX Adaptive · AAC · SBC" },
    { label: "Weight", value: "250.0 g (as measured at intake)" },
    { label: "In the box", value: "Case · USB-C cable · 3.5 mm cable · documents" },
  ],
  provenanceBadge: {
    title: "Condition Passport",
    ref: "pass_demo_1",
    line: "Inspected, sealed and serialized. Readable in Plate III.",
  },
};

/* Inspection points mapped onto the engraved portrait (SVG coords) */
export const CALLOUTS: Callout[] = [
  {
    id: "c1",
    marker: "1",
    x: 280,
    y: 138,
    zone: "Headband cushion",
    result: "PASS",
    note: "Vegan leather unmarked; memory foam rebound within spec.",
    inspector: "INSP-0042",
    date: "2026-10-27",
  },
  {
    id: "c2",
    marker: "2",
    x: 130,
    y: 358,
    zone: "Yoke & hinge — left",
    result: "PASS",
    note: "Detent action smooth across full travel; no play at rest.",
    inspector: "INSP-0042",
    date: "2026-10-27",
  },
  {
    id: "c3",
    marker: "3",
    x: 130,
    y: 452,
    zone: "Driver plate — left",
    result: "PASS",
    note: "Sweep test 20 Hz–20 kHz: response within ±1.5 dB of reference.",
    inspector: "INSP-0042",
    date: "2026-10-27",
  },
  {
    id: "c4",
    marker: "4",
    x: 430,
    y: 452,
    zone: "Driver plate — right",
    result: "PASS",
    note: "Matched pair: inter-driver deviation ≤ 0.8 dB at 1 kHz.",
    inspector: "INSP-0042",
    date: "2026-10-27",
  },
  {
    id: "c5",
    marker: "5",
    x: 468,
    y: 384,
    zone: "Beam microphone array",
    result: "PASS · NOTE",
    note: "Voice pickup nominal. Micro-scratch on bezel, visible at raking light only.",
    inspector: "INSP-0042",
    date: "2026-10-27",
  },
  {
    id: "c6",
    marker: "6",
    x: 96,
    y: 494,
    zone: "Memory-foam cushion — left",
    result: "PASS",
    note: "No compression set; cover textile unbroken at seam.",
    inspector: "INSP-0042",
    date: "2026-10-27",
  },
  {
    id: "c7",
    marker: "7",
    x: 430,
    y: 330,
    zone: "Control housing — right",
    result: "PASS",
    note: "All 4 controls exercised; tactile feedback uniform.",
    inspector: "INSP-0042",
    date: "2026-10-27",
  },
];

/* ————————————————————————————————————————————————
   THE CURVE — CIRC (Condition-Indexed Refund Curve) fixtures
———————————————————————————————————————————————— */

export type GradeTier = {
  grade: "A" | "B" | "C" | "D";
  rate: number; // 0..1
  refund: number; // computed exactly from rate × msrp
  condition: string;
  wear: string;
};

const GRADE_INPUTS: Array<Omit<GradeTier, "refund">> = [
  {
    grade: "A",
    rate: 1,
    condition: "Like-new — full function, no visible wear",
    wear: "Practically indistinguishable from new.",
  },
  {
    grade: "B",
    rate: 0.95,
    condition: "Light wear — fully functional",
    wear: "Faint surface marks visible under raking light.",
  },
  {
    grade: "C",
    rate: 0.8,
    condition: "Visible wear — fully functional",
    wear: "Clear cosmetic marks; nothing that affects use.",
  },
  {
    grade: "D",
    rate: 0.5,
    condition: "Significant wear or minor defects",
    wear: "Heavier wear, or a minor defect such as a scuffed hinge.",
  },
];

/** Exact refund = round-half-up to cents of rate × MSRP. */
export const CIRC_GRADES: GradeTier[] = GRADE_INPUTS.map((g) => ({
  ...g,
  refund: Math.round(PRODUCT.msrp * g.rate * 100) / 100,
}));

/* Jurisdiction fixtures — explicitly NOT legal advice. */
export type JurisdictionFixture = {
  code: "US-CA" | "EU";
  label: string;
  short: string;
  verificationWindow: string;
  statutoryNote: string;
  policyNote: string;
  disclaimer: string;
};

export const JURISDICTIONS: JurisdictionFixture[] = [
  {
    code: "US-CA",
    label: "United States — California",
    short: "US-CA",
    verificationWindow: "Fixture: 30-day grade verification window",
    statutoryNote:
      "Illustrative fixture: California consumers may hold statutory remedies for defective goods — for example under implied-warranty law — that exist independently of any seller policy. Whatever those rights are in your case, they are not waived, replaced, or narrowed by the curve printed above.",
    policyNote:
      "ProofReturn's CIRC is a contractual promise stacked on top of your rights: return the object, we grade it, the printed amount is what returns to you.",
    disclaimer: "Fixture — not legal advice",
  },
  {
    code: "EU",
    label: "European Union",
    short: "EU",
    verificationWindow: "Fixture: 14-day grade verification window",
    statutoryNote:
      "Illustrative fixture: EU distance purchases may carry a statutory right of withdrawal (commonly framed as 14 days). Such statutory rights — where they apply to you — remain fully intact and separate from this storefront's promises.",
    policyNote:
      "The CIRC is additive: a Grade-A return pays back 100% of the note's face value, contractual or statutory, whichever path you take.",
    disclaimer: "Fixture — not legal advice",
  },
];

/* $F — the misdeclaration deterrent. NO formula was supplied for $F,
   so this is a clearly-labeled configurable demonstration value. */
export const MISDECLARATION = {
  key: "$F",
  demoDefault: 15,
  min: 0,
  max: 50,
  step: 0.5,
  unit: "USD",
  explanation:
    "$F stands for a misdeclaration handling fee — the deterrent applied when a returned object's verified condition is worse than the grade the customer declared. ProofReturn has not published a formula for $F, so the value below is a configurable demonstration input, not an established policy amount.",
  disclaimer: "DEMO INPUT — $F IS NOT AN ESTABLISHED POLICY VALUE",
};

/* ————————————————————————————————————————————————
   THE PASSPORT — Condition Passport fixture
———————————————————————————————————————————————— */

export const PASSPORT = {
  ref: "pass_demo_1",
  displayRef: "PP-2026-0038-A",
  issued: "2026-10-28",
  product: `${PRODUCT.name} — ${PRODUCT.tagline}`,
  sku: PRODUCT.sku,
  serialHash:
    "3ea4d6ef259b32c668ef1b702ecfa54737db2d326fa2c1f93f619de9dbd4e5f3",
  hashAlgo: "SHA-256 · Ed25519 hash chain",
  originWeight: 250.0,
  measuredWeight: 250.0,
  weightTolerance: 0.5,
  seal: {
    status: "INTACT" as const,
    method: "Serialized tamper-evident label",
    label: "SEAL 04-7A · verifiable under lamp",
  },
  condition: {
    grade: "A",
    summary:
      "Origin condition Grade A. Seven inspection points recorded; one cosmetic note (mic bezel, visible at raking light only). No functional defects.",
  },
  inspections: [
    {
      zone: "Identity — serial & weight",
      result: "PASS",
      detail: "Case serial matches passport; intake weight 258.1 g within ±0.5 g of origin.",
      inspector: "INSP-0042",
      date: "2026-10-27",
    },
    {
      zone: "Packaging seal",
      result: "PASS",
      detail: "Tamper-evident label intact; serialization legible; no re-adhesion traces.",
      inspector: "INSP-0042",
      date: "2026-10-27",
    },
    {
      zone: "Left driver — sweep test",
      result: "PASS",
      detail: "20 Hz–20 kHz within ±1.5 dB of reference curve.",
      inspector: "INSP-0042",
      date: "2026-10-27",
    },
    {
      zone: "Right driver — sweep test",
      result: "PASS",
      detail: "Inter-driver deviation ≤ 0.8 dB at 1 kHz.",
      inspector: "INSP-0042",
      date: "2026-10-27",
    },
    {
      zone: "Beam microphone array",
      result: "PASS · NOTE",
      detail: "Voice pickup nominal; micro-scratch on bezel (raking light only).",
      inspector: "INSP-0042",
      date: "2026-10-27",
    },
    {
      zone: "Hinges, controls & cushions",
      result: "PASS",
      detail: "Yoke detents smooth; 4 controls exercised; cushion rebound within spec.",
      inspector: "INSP-0042",
      date: "2026-10-27",
    },
  ],
  custody: [
    { event: "Intake — origin verified", date: "2026-10-26", actor: "PR-INTAKE-DESK" },
    { event: "Inspection completed — Grade A", date: "2026-10-27", actor: "INSP-0042" },
    { event: "Condition Passport issued", date: "2026-10-28", actor: "PR-PASSPORT-REGISTRY (demo)" },
  ],
  verification: {
    checks: [
      "Digest recomputed over inspection payload",
      "Seal serialization cross-referenced",
      "Custody chain continuity confirmed",
      "Weight delta within tolerance",
    ],
  },
};

/* ————————————————————————————————————————————————
   THE COUNTING HOUSE — checkout fixtures
———————————————————————————————————————————————— */

export const CHECKOUT = {
  fastLaneRules: [
    { key: "passport", label: "Condition Passport seal verified" },
    { key: "grade", label: "Object is Grade A origin" },
    { key: "value", label: "Ledger value ≥ $250" },
  ] as const,
  shipping: "Insured & complimentary — demonstration fixture",
  tax: 0,
  warranty: {
    label: "Seal Warranty Extension",
    price: 12,
    note: "Demo line item — adds priority re-grade to the passport on file.",
  },
  paypal: {
    label: "Checkout with PayPal — Sandbox",
    steps: [
      { line: "POST /v2/checkout/orders — creating sandbox session", detail: "intent: CAPTURE · simulated" },
      { line: "Sandbox buyer session opened", detail: "sb-buyer@demo.example — fixture identity" },
      { line: "POST /v2/checkout/orders/{id}/capture — authorizing", detail: "amount: computed at runtime · demo" },
      { line: "Capture response: COMPLETED", detail: "no funds moved — sandbox only" },
      { line: "Sealing order record to ledger", detail: "passport attached: PP-2026-0038-A" },
    ],
    disclaimer:
      "Sandbox simulation. No PayPal session is opened and no payment occurs; this flow demonstrates the intended experience only.",
  },
};

/* ————————————————————————————————————————————————
   RETURN LAB chrome — ticker, hotspots, nav
———————————————————————————————————————————————— */

export const TICKER_A = [
  "UNIT PR-0038 — AURALIS N°1",
  "SEAL 04-7A · INTACT",
  "GRADE A · ORIGIN VERIFIED",
  "INTAKE WEIGHT 258.1 G ± 0.5 G",
  "SERIAL HASH 7F3C…B8E1C",
  "CIRC PRINTED ON THE INSTRUMENT",
  "DEMO — NO REAL PAYMENTS",
];

export const TICKER_B = [
  "FAST-LANE SETTLEMENT ≤ 48 H",
  "7/7 INSPECTION POINTS PASS",
  "MISDECLARATION DETERMINANT $F — DEMO INPUT",
  "JURISDICTION FIXTURES: US-CA · EU",
  "STATUTORY RIGHTS EXIST SEPARATELY",
  "SANDBOX CAPTURE: COMPLETED (SIMULATED)",
  "PROOFRETURN — RADICAL PRE-PURCHASE TRANSPARENCY",
];

/** 3D anchor points on the specimen rig — offsets RELATIVE to their parent group
 *  (c1 on headband group, c3/c5 on left cup, c4/c7 on right cup). */
export const HERO_HOTSPOTS: Array<{
  id: string;
  pos: [number, number, number];
}> = [
  { id: "c1", pos: [0, 1.32, 0.12] },
  { id: "c3", pos: [-0.3, 0, 0.05] },
  { id: "c4", pos: [0.3, 0, 0.05] },
  { id: "c5", pos: [-0.12, -0.78, 0.12] },
  { id: "c7", pos: [0.32, 0.22, 0.12] },
];

export const NAV_LINKS = [
  { index: "01", label: "SPECIMEN", href: "#specimen" },
  { index: "02", label: "CIRC", href: "#circ" },
  { index: "03", label: "PASSPORT", href: "#passport" },
  { index: "04", label: "CHECKOUT", href: "#checkout" },
] as const;

/* ————————————————————————————————————————————————
   JOURNEY — human-first wayfinding over the lab chrome
———————————————————————————————————————————————— */

export type SectionMeta = {
  id: string;
  index: string;
  /** human label shown in the journey strip */
  human: string;
  /** lab code kept as secondary flavor */
  code: string;
  /** one plain-language sentence: what you can DO here */
  action: string;
  /** CSS hue variable for this step */
  hue: string;
};

export const SECTIONS: SectionMeta[] = [
  {
    id: "specimen",
    index: "01",
    human: "Meet the object",
    code: "Specimen",
    action: "Rotate the headphones, tap the numbered points, add it to your order.",
    hue: "var(--sig)",
  },
  {
    id: "circ",
    index: "02",
    human: "See your refund future",
    code: "CIRC",
    action: "Drag the lever — the exact dollars you'd get back in every condition.",
    hue: "var(--indigo)",
  },
  {
    id: "passport",
    index: "03",
    human: "Verify the passport",
    code: "Passport",
    action: "Flip the card, run the rig — unlock Fast-Lane settlement.",
    hue: "var(--teal)",
  },
  {
    id: "checkout",
    index: "04",
    human: "Check out (safely)",
    code: "Checkout",
    action: "Watch the ledger total itself, then run a sandbox PayPal flow.",
    hue: "var(--ok)",
  },
];

/** Grade ramp A→D — emerald, amber, orange, red. */
export const GRADE_COLORS = ["#0e9f6e", "#c7860a", "#ee6c2b", "#e03131"] as const;
export const gradeColor = (grade: "A" | "B" | "C" | "D") =>
  GRADE_COLORS["ABCD".indexOf(grade)];

/* ————————————————————————————————————————————————
   Helpers
———————————————————————————————————————————————— */

export function formatUSD(value: number): string {
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function spellDollars(value: number): string {
  const ones = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen",
  ];
  const tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];
  const n = Math.round(value);
  const hundred = Math.floor(n / 100);
  const rest = n % 100;
  let words = "";
  if (hundred > 0) words += ones[hundred] + " hundred";
  if (rest > 0) {
    if (hundred > 0) words += " ";
    if (rest < 20) words += ones[rest];
    else words += tens[Math.floor(rest / 10)] + (rest % 10 ? "-" + ones[rest % 10] : "");
  }
  return words + " dollars";
}
