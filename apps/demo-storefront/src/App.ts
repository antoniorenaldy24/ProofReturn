/**
 * App 1: Demo Storefront (F-02 Pre-Purchase Refund Curve, F-09 Certified Open-Box Resale).
 * Premium retail storefront providing transparent return conditions and checkout.
 */

import { formatUsd, renderCurvePreviewSummary, SandboxBanner } from "../../../packages/ui/src/index.ts";

export interface StorefrontProductView {
  sku: string;
  name: string;
  priceMinor: number;
  certifiedOpenBox?: boolean;
  passportId?: string;
}

export interface StorefrontState {
  cart: Array<{ product: StorefrontProductView; quantity: number }>;
  checkoutStep: "CATALOG" | "CHECKOUT" | "ORDER_CONFIRMED";
  lastOrderId?: string;
  paymentMethod: "PAYPAL_SANDBOX" | "CREDIT_CARD";
}

export class DemoStorefrontController {
  public state: StorefrontState;

  constructor(initialState?: Partial<StorefrontState>) {
    this.state = {
      cart: [
        {
          product: {
            sku: "PR-HP-XM5",
            name: "Sony WH-1000XM5 Wireless Headphones",
            priceMinor: 38000,
            certifiedOpenBox: true,
            passportId: "pass_demo_1",
          },
          quantity: 1,
        },
      ],
      checkoutStep: initialState?.checkoutStep || "CATALOG",
      paymentMethod: "PAYPAL_SANDBOX",
      ...initialState,
    };
  }

  proceedToCheckout(): void {
    this.state.checkoutStep = "CHECKOUT";
  }

  placeOrder(): string {
    this.state.lastOrderId = `ord_live_${Date.now()}`;
    this.state.checkoutStep = "ORDER_CONFIRMED";
    return this.state.lastOrderId;
  }

  render(): string {
    const banner = SandboxBanner();
    let body = "";

    switch (this.state.checkoutStep) {
      case "CATALOG":
        body = `
          <div class="pr-storefront-catalog">
            <article class="pr-product-card">
              <h2>Sony WH-1000XM5 Wireless Headphones</h2>
              <p class="pr-product-price">${formatUsd(38000)}</p>
              <div class="pr-passport-badge">🛡️ Certified Open-Box — Digital Passport #pass_demo_1 Verified</div>
              <div class="pr-curve-preview">
                ${renderCurvePreviewSummary({
                  priceMinor: 38000,
                  curve: { A: 1.0, B: 0.95, C: 0.8, D: 0.5 },
                  fixedPenaltyMinor: 1500,
                  jurisdiction: "US",
                })}
              </div>
              <button type="button" class="pr-btn-primary" onclick="proceedToCheckout()">
                Add to Cart &amp; Checkout ➔
              </button>
            </article>
          </div>
        `;
        break;

      case "CHECKOUT":
        body = `
          <div class="pr-storefront-checkout">
            <h2>Order Checkout</h2>
            <div class="pr-order-summary">
              <p>Item: Sony WH-1000XM5</p>
              <p>Total: <strong>${formatUsd(38000)}</strong></p>
              <span class="pr-badge-fastlane">⚡ Protected by ProofReturn Instant Refund Guarantee</span>
            </div>
            <div class="pr-payment-selector">
              <label>
                <input type="radio" name="payment" value="PAYPAL_SANDBOX" checked />
                PayPal Sandbox (Test Money)
              </label>
              <label>
                <input type="radio" name="payment" value="CREDIT_CARD" />
                Credit Card Mockup
              </label>
            </div>
            <div class="pr-credit-card-mockup">
              <div class="pr-card-chip">💳</div>
              <div class="pr-card-number">4000 1234 5678 9010</div>
              <div class="pr-card-meta"><span>EXP: 12/28</span><span>CVC: ***</span></div>
            </div>
            <button type="button" class="pr-btn-primary" onclick="placeOrder()">
              Authorize &amp; Place Order (${formatUsd(38000)}) ➔
            </button>
          </div>
        `;
        break;

      case "ORDER_CONFIRMED":
        body = `
          <div class="pr-storefront-confirmed">
            <h2>🎉 Order Confirmed!</h2>
            <p>Order Reference: <strong>${this.state.lastOrderId}</strong></p>
            <div class="pr-return-callout">
              <p>Need to return? Experience instant refund processing with zero hassle.</p>
              <button type="button" class="pr-btn-secondary" onclick="startReturn()">
                Start Return via ProofReturn ➔
              </button>
            </div>
          </div>
        `;
        break;
    }

    return `
      <div class="pr-demo-storefront">
        ${banner}
        <header class="pr-storefront-header">
          <h1>ProofReturn Audio &amp; Electronics</h1>
        </header>
        <main class="pr-storefront-main">
          ${body}
        </main>
      </div>
    `;
  }
}
