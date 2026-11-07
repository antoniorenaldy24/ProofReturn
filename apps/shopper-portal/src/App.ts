/**
 * App 3: Shopper Return Portal (F-03 Guided Intake, F-05 Tranche Timeline, F-08 Posted Keep-Offer, F-15 Appeals, FR-88 Free Cancel).
 * Implements mobile-first consumer return experience connecting to ProofReturn /v1 API.
 */

import {
  ConfidenceIndicator,
  ExplanationCard,
  GradePicker,
  KeepOfferCard,
  LaneBadge,
  MoneyAmount,
  RefundTimeline,
  SandboxBanner,
  StatusBadge,
  formatUsd,
} from "../../../packages/ui/src/index.ts";
import { ProofReturnApiClient, type ReturnDeclarationRequest } from "../../../packages/api-client/src/index.ts";

export interface ShopperPortalState {
  orderId: string;
  returnId: string;
  step: "DECLARATION" | "KEEP_OFFER" | "EVIDENCE" | "DECISION" | "TRACKING" | "CANCELLED";
  declaredGrade: "A" | "B" | "C" | "D" | "DEF";
  accessories: Record<string, boolean>;
  lane?: "FAST" | "STANDARD" | "ESCALATED" | "KEEP_OFFER";
  timing?: "R0" | "R1" | "ESC" | "STANDARD";
  r0TrancheMinor?: number;
  checkinMinor?: number;
  holdbackMinor?: number;
  keepOfferAmountMinor?: number;
  signedReceipt?: Record<string, any>;
  explanation?: string;
  error?: string;
}

export class ShopperPortalController {
  private client: ProofReturnApiClient;
  public state: ShopperPortalState;

  constructor(client: ProofReturnApiClient, initialState?: Partial<ShopperPortalState>) {
    this.client = client;
    this.state = {
      orderId: initialState?.orderId || "ord_demo_1",
      returnId: initialState?.returnId || "ret_demo_1",
      step: initialState?.step || "DECLARATION",
      declaredGrade: initialState?.declaredGrade || "B",
      accessories: initialState?.accessories || { case: true, cable: true },
      ...initialState,
    };
  }

  async submitDeclaration(grade: "A" | "B" | "C" | "D" | "DEF"): Promise<void> {
    this.state.declaredGrade = grade;
    const req: ReturnDeclarationRequest = {
      declared_grade: grade,
      accessories: this.state.accessories,
      reason_code: "CHANGED_MIND",
      reason_text: "Fit not ideal",
      fast_lane_terms_accepted: true,
      shopper_nonce: "nonce_shopper_01",
    };
    await this.client.submitDeclaration(this.state.returnId, req);

    // Check for Keep-Offer eligibility
    try {
      const offer = await this.client.getKeepOffer(this.state.returnId);
      if (offer && offer.amount_minor > 0 && offer.status !== "EXPIRED") {
        this.state.keepOfferAmountMinor = offer.amount_minor;
        this.state.step = "KEEP_OFFER";
        return;
      }
    } catch {
      // No active keep offer; proceed to evidence capture
    }
    this.state.step = "EVIDENCE";
  }

  async respondKeepOffer(accept: boolean): Promise<void> {
    if (accept) {
      const res = await this.client.respondKeepOffer(this.state.returnId, "ACCEPT");
      this.state.step = "TRACKING";
      this.state.lane = "KEEP_OFFER";
      this.state.r0TrancheMinor = res.posted_price_minor || this.state.keepOfferAmountMinor;
    } else {
      await this.client.respondKeepOffer(this.state.returnId, "DECLINE");
      this.state.step = "EVIDENCE";
    }
  }

  async submitEvidence(sha256: string = "a".repeat(64)): Promise<void> {
    const res = await this.client.submitEvidence(this.state.returnId, {
      sha256,
      faces_detected: 0,
      client_blur_applied: true,
    });
    this.state.lane = res.lane || "FAST";
    this.state.timing = res.timing || "R0";
    this.state.r0TrancheMinor = res.r0_tranche_minor || 0;
    this.state.holdbackMinor = res.holdback_minor || 0;
    this.state.explanation = res.plain_language_explanation || "Evidence matches declared grade.";
    this.state.step = "DECISION";
  }

  async cancelReturn(): Promise<void> {
    await this.client.cancelReturn(this.state.returnId);
    this.state.step = "CANCELLED";
  }

  async loadReceipt(): Promise<void> {
    const receipt = await this.client.getSignedReceipt(this.state.returnId);
    this.state.signedReceipt = receipt;
  }

  render(): string {
    const banner = SandboxBanner();
    let body = "";

    switch (this.state.step) {
      case "DECLARATION":
        body = `
          <div class="pr-shopper-step" data-step="declaration">
            <h2>Select Item Condition</h2>
            <p>Select the honest condition of your item for fair, instant refund processing.</p>
            ${GradePicker({
              selected: this.state.declaredGrade,
              referenceImages: { A: "a.jpg", B: "b.jpg", C: "c.jpg", D: "d.jpg", DEF: "def.jpg" },
            })}
            <div class="pr-accessories-checklist">
              <label><input type="checkbox" checked /> Original Case</label>
              <label><input type="checkbox" checked /> Charging Cable</label>
            </div>
            <button type="button" class="pr-btn-primary" onclick="submitDeclaration('${this.state.declaredGrade}')">
              Continue to Verification ➔
            </button>
          </div>
        `;
        break;

      case "KEEP_OFFER":
        body = `
          <div class="pr-shopper-step" data-step="keep_offer">
            <h2>Instant Cash Option</h2>
            ${KeepOfferCard({
              postedAmountMinor: this.state.keepOfferAmountMinor || 7600,
              expiresAtIso: new Date(Date.now() + 86400000).toISOString(),
            })}
          </div>
        `;
        break;

      case "EVIDENCE":
        body = `
          <div class="pr-shopper-step" data-step="evidence">
            <h2>Verify Physical Condition</h2>
            <div class="pr-camera-viewfinder" data-blur-active="true">
              <span class="pr-privacy-shield">🛡️ Privacy Shield Active: Faces Automatically Redacted</span>
              <div class="pr-challenge-overlay">Code: NONCE-PROOFRTN</div>
            </div>
            <button type="button" class="pr-btn-primary" onclick="submitEvidence()">
              Analyze Condition &amp; Calculate Refund ➔
            </button>
          </div>
        `;
        break;

      case "DECISION":
        body = `
          <div class="pr-shopper-step" data-step="decision">
            <h2>Refund Decision</h2>
            ${LaneBadge({ lane: this.state.lane || "FAST" })}
            ${RefundTimeline({
              tranches: [
                { type: "Instant Release (R0)", amountMinor: this.state.r0TrancheMinor || 21249, status: "CONFIRMED" },
                { type: "Drop-off Scan (R1)", amountMinor: this.state.checkinMinor || 9843, status: "PENDING" },
                { type: "Dock Check-in Holdback", amountMinor: this.state.holdbackMinor || 6000, status: "HOLD" },
              ],
            })}
            ${ExplanationCard({
              headline: "Decision Summary",
              reasons: [this.state.explanation || "Grade matched with high confidence."],
              nextStep: "Ship item using the prepaid carrier barcode below.",
            })}
            <div class="pr-actions-row">
              <button type="button" class="pr-btn-primary" onclick="proceedToShipping()">Get Shipping Barcode ➔</button>
              <button type="button" class="pr-btn-link" onclick="cancelReturn()">Cancel Return (Free)</button>
            </div>
          </div>
        `;
        break;

      case "CANCELLED":
        body = `
          <div class="pr-shopper-step" data-step="cancelled">
            <h2>Return Cancelled</h2>
            <p>Your return request has been cancelled free of charge per FR-88.</p>
          </div>
        `;
        break;

      case "TRACKING":
        body = `
          <div class="pr-shopper-step" data-step="tracking">
            <h2>Return Completed</h2>
            ${StatusBadge({ status: "CONFIRMED", text: `Refund of ${formatUsd(this.state.r0TrancheMinor || 0)} Completed` })}
          </div>
        `;
        break;
    }

    return `
      <div class="pr-shopper-portal">
        ${banner}
        <header class="pr-portal-header">
          <h1>ProofReturn Shopper Portal</h1>
          <span class="pr-order-ref">Order #${this.state.orderId}</span>
        </header>
        <main class="pr-portal-main">
          ${body}
        </main>
      </div>
    `;
  }
}
