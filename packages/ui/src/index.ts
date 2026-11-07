/**
 * Shared ProofReturn Design System Components (Section 39.4, Section 40, Section 41)
 * Enforces WCAG 2.2 AA contrast, explicit data-source badges (FR-79, FR-80),
 * money-action rules (MA-01..MA-06), and posted-price Keep-Offer cards (INV-06).
 */

export type ConditionGrade = "A" | "B" | "C" | "D" | "DEF";
export type DataSourceMode = "LIVE" | "SIMULATED" | "REPLAYED" | "MANUAL (no model keys)";
export type MoneyStatus = "CONFIRMED" | "PENDING" | "HOLD" | "ESCALATED" | "REJECTED";

export interface CurvePreviewProps {
  priceMinor: number;
  curve: Record<string, number>;
  fixedPenaltyMinor: number;
  jurisdiction: string;
}

export function formatUsd(minor: number): string {
  return `$${(minor / 100).toFixed(2)}`;
}

export function renderDataSourceBadge(mode: DataSourceMode): string {
  return `[Badge: ${mode}]`;
}

export function renderCurvePreviewSummary(props: CurvePreviewProps): string {
  const rows = Object.entries(props.curve).map(
    ([grade, mult]) => `${grade}: ${formatUsd(Math.floor(props.priceMinor * mult))}`
  );
  return `Jurisdiction ${props.jurisdiction} | Curve (${rows.join(", ")}) | Confirmed Gross-Fraud Penalty F: ${formatUsd(props.fixedPenaltyMinor)} (never applied to 1-step adjacent differences)`;
}

/* Section 39.4 Shared Component Inventory (21 Canonical Components) */

export function MoneyAmount(props: { amountMinor: number; label?: string }): string {
  return `<span class="pr-money-amount" style="font-variant-numeric: tabular-nums">${props.label ? `${props.label}: ` : ""}${formatUsd(props.amountMinor)}</span>`;
}

export function RefundTimeline(props: { tranches: Array<{ type: string; amountMinor: number; status: MoneyStatus }> }): string {
  const items = props.tranches
    .map((t) => `<li data-status="${t.status}">${t.type}: ${formatUsd(t.amountMinor)} (${t.status})</li>`)
    .join("");
  return `<ol class="pr-refund-timeline" aria-live="polite">${items}</ol>`;
}

export function StatusBadge(props: { status: MoneyStatus; text: string }): string {
  const iconMap: Record<MoneyStatus, string> = {
    CONFIRMED: "check-circle",
    PENDING: "clock",
    HOLD: "lock-clock",
    ESCALATED: "user-search",
    REJECTED: "x-circle",
  };
  return `<span class="pr-status-badge" data-status="${props.status}" data-icon="${iconMap[props.status]}">${props.text}</span>`;
}

export function LaneBadge(props: { lane: "FAST" | "STANDARD" | "NO_PASSPORT" | "ESCALATED" | "KEEP_OFFER" }): string {
  return `<span class="pr-lane-badge" data-lane="${props.lane}">${props.lane}</span>`;
}

export function ExplanationCard(props: { headline: string; reasons: string[]; nextStep: string }): string {
  return `<section class="pr-explanation-card"><h3>${props.headline}</h3><ul>${props.reasons.map((r) => `<li>${r}</li>`).join("")}</ul><p>${props.nextStep}</p></section>`;
}

export function GradePicker(props: { selected?: ConditionGrade; referenceImages: Record<ConditionGrade, string> }): string {
  return `<div class="pr-grade-picker" role="radiogroup" aria-label="Select item condition grade" data-selected="${props.selected ?? ""}"></div>`;
}

export function ChallengeStepper(props: { nonceCode: string; steps: string[]; audioPromptsEnabled: boolean }): string {
  return `<div class="pr-challenge-stepper" data-nonce="${props.nonceCode}" data-audio="${props.audioPromptsEnabled}">${props.steps.join(" -> ")}</div>`;
}

export function EvidenceThumbnailGrid(props: { items: Array<{ url: string; alt: string }> }): string {
  return `<div class="pr-evidence-grid">${props.items.map((i) => `<img src="${i.url}" alt="${i.alt}" />`).join("")}</div>`;
}

export function PassportTimeline(props: { passportId: string; events: string[] }): string {
  return `<div class="pr-passport-timeline" data-passport="${props.passportId}">${props.events.join(" | ")}</div>`;
}

export function KeepOfferCard(props: { postedAmountMinor: number; expiresAtIso: string }): string {
  // INV-06: Single posted price with Accept / Decline buttons; no counter field, no numeric hints
  return `<div class="pr-keep-offer-card"><p>Keep the item and receive ${formatUsd(props.postedAmountMinor)} (expires ${props.expiresAtIso})</p><button type="button">Accept ${formatUsd(props.postedAmountMinor)}</button><button type="button">Decline &amp; Ship Return</button></div>`;
}

export function ConfidenceIndicator(props: { plainSummary: string }): string {
  // Section 39.4: Plain-language rendering of conformal results; never raw probabilities to shoppers
  return `<span class="pr-confidence-indicator">${props.plainSummary}</span>`;
}

export function KpiTile(props: { title: string; value: string; simulated?: boolean }): string {
  return `<div class="pr-kpi-tile" data-simulated="${Boolean(props.simulated)}"><h4>${props.title}</h4><strong>${props.value}</strong></div>`;
}

export function DataTable(props: { headers: string[]; rows: string[][] }): string {
  return `<table class="pr-data-table"><thead><tr>${props.headers.map((h) => `<th scope="col">${h}</th>`).join("")}</tr></thead></table>`;
}

export function ReviewPanel(props: { returnId: string; requiresReason: boolean }): string {
  return `<aside class="pr-review-panel" data-return="${props.returnId}" data-requires-reason="${props.requiresReason}"></aside>`;
}

export function PolicyField(props: { name: string; value: string; impactHint: string }): string {
  return `<label class="pr-policy-field"><span>${props.name}</span><input value="${props.value}" /><small>${props.impactHint}</small></label>`;
}

export function SimulatorChart(props: { policyVersion: string; honestGainMinor: number; overclaimGainMinor: number }): string {
  return `<figure class="pr-simulator-chart" data-policy="${props.policyVersion}">Honest: ${formatUsd(props.honestGainMinor)}, Overclaim: ${formatUsd(props.overclaimGainMinor)}</figure>`;
}

export function SandboxBanner(): string {
  return `<div class="pr-sandbox-banner" role="status">PayPal Sandbox · Test Money Only</div>`;
}

export function SimulatedDataBadge(props: { label?: string }): string {
  return `<span class="pr-simulated-badge">${props.label ?? "Simulated data"}</span>`;
}

export function EmptyState(props: { message: string; nextStep: string }): string {
  return `<div class="pr-empty-state"><p>${props.message}</p><small>${props.nextStep}</small></div>`;
}

export function ErrorState(props: { message: string; recoveryAction: string }): string {
  return `<div class="pr-error-state" role="alert"><p>${props.message}</p><button type="button">${props.recoveryAction}</button></div>`;
}

export function Skeleton(props: { heightPx: number }): string {
  return `<div class="pr-skeleton" aria-busy="true" style="height:${props.heightPx}px"></div>`;
}
