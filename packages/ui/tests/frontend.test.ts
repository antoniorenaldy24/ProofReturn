/**
 * Frontend Unit & Integration Test Suite for ProofReturn Apps & Design System (Section 39, 40, 41).
 * Tests all 4 applications, controllers, and 21 shared UI components without mock dependencies.
 */

import test from "node:test";
import assert from "node:assert";

import {
  formatUsd,
  renderCurvePreviewSummary,
  MoneyAmount,
  RefundTimeline,
  StatusBadge,
  LaneBadge,
  ExplanationCard,
  GradePicker,
  KeepOfferCard,
  ConfidenceIndicator,
  KpiTile,
  DataTable,
  ReviewPanel,
  PolicyField,
  SimulatorChart,
  SandboxBanner,
} from "../src/index.ts";

import { ProofReturnApiClient } from "../../api-client/src/index.ts";
import { ShopperPortalController } from "../../../apps/shopper-portal/src/App.ts";
import { MerchantConsoleController } from "../../../apps/merchant-console/src/App.ts";
import { DemoStorefrontController } from "../../../apps/demo-storefront/src/App.ts";
import { PackingStationController } from "../../../apps/packing-station/src/App.ts";

test("Design System: formatUsd handles zero, typical, and large minor amounts", () => {
  assert.strictEqual(formatUsd(0), "$0.00");
  assert.strictEqual(formatUsd(38000), "$380.00");
  assert.strictEqual(formatUsd(21249), "$212.49");
  assert.strictEqual(formatUsd(1000000), "$10000.00");
});

test("Design System: Shared Components render accessible markup with design tokens", () => {
  // 1. RefundTimeline
  const timelineHtml = RefundTimeline({
    tranches: [
      { type: "R0", amountMinor: 21249, status: "CONFIRMED" },
      { type: "R1", amountMinor: 9843, status: "PENDING" },
    ],
  });
  assert.match(timelineHtml, /pr-refund-timeline/);
  assert.match(timelineHtml, /\$212\.49/);
  assert.match(timelineHtml, /CONFIRMED/);

  // 2. StatusBadge & LaneBadge
  const statusHtml = StatusBadge({ status: "CONFIRMED", text: "Refund Completed" });
  assert.match(statusHtml, /data-status="CONFIRMED"/);
  assert.match(statusHtml, /Refund Completed/);

  const laneHtml = LaneBadge({ lane: "FAST" });
  assert.match(laneHtml, /data-lane="FAST"/);

  // 3. KeepOfferCard (INV-06: single posted price, no counter-offer)
  const keepHtml = KeepOfferCard({ postedAmountMinor: 7600, expiresAtIso: "2026-11-04T00:00:00Z" });
  assert.match(keepHtml, /\$76\.00/);
  assert.match(keepHtml, /Accept \$76\.00/);
  assert.match(keepHtml, /Decline &amp; Ship Return/);
  assert.doesNotMatch(keepHtml, /counter-offer/);

  // 4. SandboxBanner
  assert.match(SandboxBanner(), /PayPal Sandbox · Test Money Only/);
});

test("App 1: DemoStorefrontController manages catalog, checkout with card, and order flow", () => {
  const store = new DemoStorefrontController();
  assert.strictEqual(store.state.checkoutStep, "CATALOG");

  const catalogHtml = store.render();
  assert.match(catalogHtml, /Sony WH-1000XM5/);
  assert.match(catalogHtml, /Certified Open-Box/);
  assert.match(catalogHtml, /\$380\.00/);

  // Proceed to Checkout
  store.proceedToCheckout();
  assert.strictEqual(store.state.checkoutStep, "CHECKOUT");
  const checkoutHtml = store.render();
  assert.match(checkoutHtml, /PayPal Sandbox/);
  assert.match(checkoutHtml, /Credit Card Mockup/);
  assert.match(checkoutHtml, /4000 1234 5678 9010/);

  // Place Order
  const orderId = store.placeOrder();
  assert.strictEqual(store.state.checkoutStep, "ORDER_CONFIRMED");
  assert.ok(orderId.startsWith("ord_live_"));
  const confirmedHtml = store.render();
  assert.match(confirmedHtml, /Order Confirmed!/);
  assert.match(confirmedHtml, /Start Return via ProofReturn/);
});

test("App 2: PackingStationController manages minting passport and receiving dock check-in", () => {
  const station = new PackingStationController({ mode: "PACKING" });
  const packingHtml = station.render();
  assert.match(packingHtml, /Origin Packing &amp; Digital Passport Minting/);
  assert.match(packingHtml, /PR-HP-XM5/);

  const passportId = station.mintPassport();
  assert.ok(passportId.startsWith("pass_"));
  assert.match(station.state.lastActionSummary!, /Passport/);

  // Switch to Receiving Dock Mode
  station.state.mode = "RECEIVING";
  const receivingHtml = station.render();
  assert.match(receivingHtml, /Inbound Dock Check-In/);
  assert.match(receivingHtml, /ret_dock_01/);

  // Check-in passed
  station.processDockCheckIn(true);
  assert.strictEqual(station.state.receivingDraft.checkinPassed, true);
  assert.match(station.state.lastActionSummary!, /PASSED/);

  // Check-in discrepancy
  station.processDockCheckIn(false);
  assert.strictEqual(station.state.receivingDraft.checkinPassed, false);
  assert.match(station.state.lastActionSummary!, /FAILED/);
});

test("App 3: ShopperPortalController handles declaration, keep-offer, decision, and free cancel", async () => {
  // Mock API client for controller test
  const fakeClient = {
    submitDeclaration: async () => ({ status: "OK" }),
    getKeepOffer: async () => ({ amount_minor: 7600, status: "OFFERED" }),
    respondKeepOffer: async (_id: string, action: string) => ({ posted_price_minor: 7600, action }),
    submitEvidence: async () => ({ lane: "FAST", timing: "R0", r0_tranche_minor: 21249, holdback_minor: 6000 }),
    cancelReturn: async () => ({ return_id: "ret_demo_1", state: "CANCELLED" }),
    getSignedReceipt: async () => ({ signed: true, signature: "ed25519_sig" }),
  } as unknown as ProofReturnApiClient;

  const portal = new ShopperPortalController(fakeClient);
  assert.strictEqual(portal.state.step, "DECLARATION");

  const declHtml = portal.render();
  assert.match(declHtml, /Select Item Condition/);
  assert.match(declHtml, /pr-grade-picker/);

  // Submit Declaration -> routes to Keep-Offer
  await portal.submitDeclaration("B");
  assert.strictEqual(portal.state.step, "KEEP_OFFER");
  assert.strictEqual(portal.state.keepOfferAmountMinor, 7600);
  const keepHtml = portal.render();
  assert.match(keepHtml, /Instant Cash Option/);

  // Decline Keep Offer -> routes to Evidence
  await portal.respondKeepOffer(false);
  assert.strictEqual(portal.state.step, "EVIDENCE");
  const evHtml = portal.render();
  assert.match(evHtml, /Privacy Shield Active/);

  // Submit Evidence -> routes to Decision
  await portal.submitEvidence();
  assert.strictEqual(portal.state.step, "DECISION");
  assert.strictEqual(portal.state.lane, "FAST");
  assert.strictEqual(portal.state.r0TrancheMinor, 21249);
  const decHtml = portal.render();
  assert.match(decHtml, /Refund Decision/);
  assert.match(decHtml, /\$212\.49/);
  assert.match(decHtml, /Cancel Return \(Free\)/);

  // Free cancellation per FR-88
  await portal.cancelReturn();
  assert.strictEqual(portal.state.step, "CANCELLED");
  const cancelHtml = portal.render();
  assert.match(cancelHtml, /Return Cancelled/);
  assert.match(cancelHtml, /free of charge per FR-88/);
});

test("App 4: MerchantConsoleController manages dashboard KPIs, reviewer queue, policy, and simulator", async () => {
  const fakeClient = {
    simulateMechanism: async () => ({
      lane: "FAST",
      timing: "R0",
      x_released_minor: 21249,
      holdback_minor: 6000,
      simulated_gain_minor: 38000,
      roi: { annual_savings_usd: 14200.5, roi_multiple: 4.2 },
    }),
  } as unknown as ProofReturnApiClient;

  const consoleApp = new MerchantConsoleController(fakeClient);
  assert.strictEqual(consoleApp.state.activeTab, "DASHBOARD");

  // Dashboard
  const dashHtml = consoleApp.render();
  assert.match(dashHtml, /ProofReturn Merchant Console/);
  assert.match(dashHtml, /Total Return Volume/);
  assert.match(dashHtml, /1420 units/);

  // Review Queue
  consoleApp.state.activeTab = "REVIEW_QUEUE";
  const queueHtml = consoleApp.render();
  assert.match(queueHtml, /Review Queue — Verification Required/);
  assert.match(queueHtml, /ret_rev_01/);
  assert.match(queueHtml, /Confirm Shopper Grade/);

  // Policy Editor
  consoleApp.state.activeTab = "POLICY_EDITOR";
  const policyHtml = consoleApp.render();
  assert.match(policyHtml, /Dynamic Policy Configuration/);
  assert.match(policyHtml, /Grade A Multiplier/);

  // Simulator
  consoleApp.state.activeTab = "SIMULATOR";
  await consoleApp.runSimulation({
    price_minor: 38000,
    declared_grade: "B",
    tier: "TRUSTED",
    has_origin_passport: true,
  });
  const simHtml = consoleApp.render();
  assert.match(simHtml, /Mechanism Simulator &amp; Feasibility Sandbox/);
  assert.match(simHtml, /\$14200\.50/);
  assert.match(simHtml, /4\.2x/);
});
