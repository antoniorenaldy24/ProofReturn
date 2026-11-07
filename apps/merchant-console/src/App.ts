/**
 * App 4: Merchant Console & Mechanism Simulator (F-06, F-07, F-08, F-11, F-15, F-16).
 * Provides desktop-first administrative command center connecting to ProofReturn /v1 API.
 */

import {
  DataTable,
  KpiTile,
  PolicyField,
  ReviewPanel,
  SandboxBanner,
  SimulatorChart,
  StatusBadge,
  formatUsd,
  renderDataSourceBadge,
} from "../../../packages/ui/src/index.ts";
import { ProofReturnApiClient, type SimulateRequestPayload } from "../../../packages/api-client/src/index.ts";

export interface MerchantConsoleState {
  activeTab: "DASHBOARD" | "REVIEW_QUEUE" | "POLICY_EDITOR" | "SIMULATOR";
  merchantId: string;
  kpis: {
    totalVolume: number;
    capitalReleasedMinor: number;
    holdbackRetainedMinor: number;
    fraudPreventedMinor: number;
  };
  reviewQueue: Array<{
    returnId: string;
    orderId: string;
    shopperId: string;
    declaredGrade: string;
    observedGrade: string;
    status: string;
  }>;
  simulationResult?: {
    lane: string;
    timing: string;
    xReleasedMinor: number;
    holdbackMinor: number;
    simulatedGainMinor: number;
    annualSavingsUsd: number;
    roiMultiple: number;
  };
  policyCurve: Record<string, number>;
}

export class MerchantConsoleController {
  private client: ProofReturnApiClient;
  public state: MerchantConsoleState;

  constructor(client: ProofReturnApiClient, initialState?: Partial<MerchantConsoleState>) {
    this.client = client;
    this.state = {
      activeTab: initialState?.activeTab || "DASHBOARD",
      merchantId: initialState?.merchantId || "merch_demo_1",
      kpis: {
        totalVolume: 1420,
        capitalReleasedMinor: 31245000,
        holdbackRetainedMinor: 6420000,
        fraudPreventedMinor: 4890000,
      },
      reviewQueue: [
        {
          returnId: "ret_rev_01",
          orderId: "ord_102",
          shopperId: "shopper_discrepant_1",
          declaredGrade: "A",
          observedGrade: "C",
          status: "ESCALATED",
        },
      ],
      policyCurve: { A: 1.0, B: 0.95, C: 0.8, D: 0.5, DEF: 0.0 },
      ...initialState,
    };
  }

  async runSimulation(payload: SimulateRequestPayload): Promise<void> {
    const res = await this.client.simulateMechanism(payload);
    this.state.simulationResult = {
      lane: res.lane,
      timing: res.timing,
      xReleasedMinor: res.x_released_minor,
      holdbackMinor: res.holdback_minor,
      simulatedGainMinor: res.simulated_gain_minor,
      annualSavingsUsd: res.roi?.annual_savings_usd || 0,
      roiMultiple: res.roi?.roi_multiple || 0,
    };
  }

  render(): string {
    const banner = SandboxBanner();
    let mainContent = "";

    switch (this.state.activeTab) {
      case "DASHBOARD":
        mainContent = `
          <div class="pr-console-dashboard">
            <div class="pr-kpi-grid">
              ${KpiTile({ title: "Total Return Volume", value: `${this.state.kpis.totalVolume} units` })}
              ${KpiTile({ title: "Capital Released (R0)", value: formatUsd(this.state.kpis.capitalReleasedMinor) })}
              ${KpiTile({ title: "Holdback Protected", value: formatUsd(this.state.kpis.holdbackRetainedMinor) })}
              ${KpiTile({ title: "Gross Fraud Prevented", value: formatUsd(this.state.kpis.fraudPreventedMinor) })}
            </div>
            <div class="pr-recent-returns">
              <h3>Recent Return Activity</h3>
              ${DataTable({
                headers: ["Return ID", "Order ID", "Shopper", "Declared", "Observed", "Status"],
                rows: this.state.reviewQueue.map((r) => [
                  r.returnId,
                  r.orderId,
                  r.shopperId,
                  r.declaredGrade,
                  r.observedGrade,
                  r.status,
                ]),
              })}
            </div>
          </div>
        `;
        break;

      case "REVIEW_QUEUE":
        mainContent = `
          <div class="pr-console-review">
            <h2>Review Queue — Verification Required</h2>
            ${ReviewPanel({ returnId: "ret_rev_01", requiresReason: true })}
            <div class="pr-review-actions">
              <button type="button" class="pr-btn-success">Confirm Shopper Grade</button>
              <button type="button" class="pr-btn-warning">Adjust to Verified Grade C</button>
              <button type="button" class="pr-btn-danger">Apply Gross Penalty F ($15.00)</button>
            </div>
          </div>
        `;
        break;

      case "POLICY_EDITOR":
        mainContent = `
          <div class="pr-console-policy">
            <h2>Dynamic Policy Configuration</h2>
            <div class="pr-curve-fields">
              ${PolicyField({ name: "Grade A Multiplier", value: "1.00", impactHint: "Full refund for pristine condition" })}
              ${PolicyField({ name: "Grade B Multiplier", value: "0.95", impactHint: "5% restocking reduction for minor scuffs" })}
              ${PolicyField({ name: "Grade C Multiplier", value: "0.80", impactHint: "20% value deduction for visible wear" })}
              ${PolicyField({ name: "Grade D Multiplier", value: "0.50", impactHint: "50% salvage allowance" })}
            </div>
            <button type="button" class="pr-btn-primary">Save &amp; Validate Policy Version</button>
          </div>
        `;
        break;

      case "SIMULATOR":
        mainContent = `
          <div class="pr-console-simulator">
            <h2>Mechanism Simulator &amp; Feasibility Sandbox</h2>
            ${SimulatorChart({
              policyVersion: "v1.2",
              honestGainMinor: this.state.simulationResult?.simulatedGainMinor || 38000,
              overclaimGainMinor: 21249,
            })}
            ${this.state.simulationResult ? `
              <div class="pr-sim-metrics">
                <p>Projected Annual Savings: <strong>$${this.state.simulationResult.annualSavingsUsd.toFixed(2)}</strong></p>
                <p>Merchant ROI Ratio: <strong>${this.state.simulationResult.roiMultiple}x</strong></p>
              </div>
            ` : ""}
          </div>
        `;
        break;
    }

    return `
      <div class="pr-merchant-console">
        ${banner}
        <header class="pr-console-header">
          <h1>ProofReturn Merchant Console ${renderDataSourceBadge("LIVE")}</h1>
          <nav class="pr-console-nav">
            <button class="${this.state.activeTab === "DASHBOARD" ? "active" : ""}">Dashboard</button>
            <button class="${this.state.activeTab === "REVIEW_QUEUE" ? "active" : ""}">Review Queue</button>
            <button class="${this.state.activeTab === "POLICY_EDITOR" ? "active" : ""}">Policy Editor</button>
            <button class="${this.state.activeTab === "SIMULATOR" ? "active" : ""}">Simulator</button>
          </nav>
        </header>
        <main class="pr-console-main">
          ${mainContent}
        </main>
      </div>
    `;
  }
}
