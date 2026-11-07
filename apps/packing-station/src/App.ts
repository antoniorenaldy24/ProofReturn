/**
 * App 2: Packing & Receiving Station (F-01 Origin Passport Minting & F-06 Dock Check-In).
 * Warehouse tablet dock application optimized for fast scanning and touch with gloves.
 */

import { formatUsd, SandboxBanner } from "../../../packages/ui/src/index.ts";

export interface PackingStationDraft {
  orderId: string;
  sku: string;
  passportTier: "FULL" | "LITE" | "NONE";
  nonceOrigin: string;
  weightGrams: number;
  functionalSelfTestPassed: boolean;
}

export interface ReceivingDockDraft {
  returnId: string;
  sealIntact: boolean;
  expectedWeightGrams: number;
  actualWeightGrams: number;
  observedGrade: "A" | "B" | "C" | "D" | "DEF";
  checkinPassed: boolean;
}

export interface StationState {
  mode: "PACKING" | "RECEIVING";
  packingDraft: PackingStationDraft;
  receivingDraft: ReceivingDockDraft;
  lastActionSummary?: string;
}

export class PackingStationController {
  public state: StationState;

  constructor(initialState?: Partial<StationState>) {
    this.state = {
      mode: initialState?.mode || "PACKING",
      packingDraft: {
        orderId: "ord_pack_01",
        sku: "PR-HP-XM5",
        passportTier: "FULL",
        nonceOrigin: "NONCE-ORIGIN-77",
        weightGrams: 250,
        functionalSelfTestPassed: true,
      },
      receivingDraft: {
        returnId: "ret_dock_01",
        sealIntact: true,
        expectedWeightGrams: 250,
        actualWeightGrams: 249,
        observedGrade: "B",
        checkinPassed: true,
      },
      ...initialState,
    };
  }

  mintPassport(): string {
    const passportId = `pass_${Date.now()}`;
    this.state.lastActionSummary = `Passport ${passportId} minted for SKU ${this.state.packingDraft.sku} (${this.state.packingDraft.passportTier})`;
    return passportId;
  }

  processDockCheckIn(passed: boolean): void {
    this.state.receivingDraft.checkinPassed = passed;
    this.state.lastActionSummary = passed
      ? `Dock Check-in PASSED for ${this.state.receivingDraft.returnId}; seal intact, weight verified.`
      : `Dock Check-in FAILED for ${this.state.receivingDraft.returnId}; discrepancy routed to Review Queue.`;
  }

  render(): string {
    const banner = SandboxBanner();
    let body = "";

    if (this.state.mode === "PACKING") {
      body = `
        <div class="pr-station-view" data-station="packing">
          <h2>Origin Packing &amp; Digital Passport Minting (F-01)</h2>
          <div class="pr-station-grid">
            <div class="pr-input-group">
              <label>Order Reference: <input value="${this.state.packingDraft.orderId}" readonly /></label>
              <label>SKU: <input value="${this.state.packingDraft.sku}" readonly /></label>
              <label>Passport Tier: <input value="${this.state.packingDraft.passportTier}" readonly /></label>
            </div>
            <div class="pr-input-group">
              <label>Holographic Seal Nonce: <input value="${this.state.packingDraft.nonceOrigin}" readonly /></label>
              <label>Scale Weight: <strong>${this.state.packingDraft.weightGrams}g</strong> (Calibrated)</label>
              <label><input type="checkbox" checked /> Functional Self-Test Passed</label>
            </div>
          </div>
          <button type="button" class="pr-btn-touch-primary" onclick="mintPassport()">
            Mint Passport &amp; Attach Tamper Seal ➔
          </button>
        </div>
      `;
    } else {
      body = `
        <div class="pr-station-view" data-station="receiving">
          <h2>Inbound Dock Check-In &amp; Inspection (F-06)</h2>
          <div class="pr-station-grid">
            <div class="pr-input-group">
              <label>Return ID: <input value="${this.state.receivingDraft.returnId}" readonly /></label>
              <label>Tamper Seal Intact: <strong>${this.state.receivingDraft.sealIntact ? "YES (VERIFIED)" : "TAMPERED"}</strong></label>
              <label>Weight Check: ${this.state.receivingDraft.actualWeightGrams}g / expected ${this.state.receivingDraft.expectedWeightGrams}g (OK)</label>
            </div>
            <div class="pr-input-group">
              <label>Observed Grade: <strong>Grade ${this.state.receivingDraft.observedGrade}</strong></label>
            </div>
          </div>
          <div class="pr-dock-actions">
            <button type="button" class="pr-btn-touch-success" onclick="processDockCheckIn(true)">
              Check-in Passed ➔ Release Holdback
            </button>
            <button type="button" class="pr-btn-touch-danger" onclick="processDockCheckIn(false)">
              Discrepancy ➔ Flag to Reviewer
            </button>
          </div>
        </div>
      `;
    }

    return `
      <div class="pr-packing-station-app">
        ${banner}
        <header class="pr-station-header">
          <h1>ProofReturn Operations Dock Station</h1>
          <nav>
            <button class="${this.state.mode === "PACKING" ? "active" : ""}">Packing</button>
            <button class="${this.state.mode === "RECEIVING" ? "active" : ""}">Receiving</button>
          </nav>
        </header>
        <main class="pr-station-main">
          ${body}
          ${this.state.lastActionSummary ? `<div class="pr-station-alert">${this.state.lastActionSummary}</div>` : ""}
        </main>
      </div>
    `;
  }
}
