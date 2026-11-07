/**
 * Typed ProofReturn /v1 HTTP Client (Section 28, Section 39, Section 40).
 * Provides end-to-end integration between frontend apps and backend REST endpoints.
 */

export interface ApiClientConfig {
  baseUrl: string;
  bearerToken?: string;
  idempotencyKey?: string;
}

export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  code?: string;
  error_code?: string;
  invalid_params?: Array<{ name: string; reason: string }>;
}

export interface ReturnDeclarationRequest {
  declared_grade: "A" | "B" | "C" | "D" | "DEF";
  accessories?: Record<string, boolean>;
  reason_code?: string;
  reason_text?: string;
  fast_lane_terms_accepted?: boolean;
  shopper_nonce?: string;
}

export interface ReturnEvidenceRequest {
  sha256?: string;
  faces_detected?: number;
  client_blur_applied?: boolean;
  image_base64?: string;
}

export interface SimulateRequestPayload {
  price_minor: number;
  declared_grade: string;
  tier: string;
  has_origin_passport: boolean;
}

export class ProofReturnApiClient {
  public config: ApiClientConfig;

  constructor(config: ApiClientConfig) {
    this.config = config;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.config.baseUrl}${path}`;
    const headers = new Headers(options.headers || {});

    if (!headers.has("Content-Type") && options.body) {
      headers.set("Content-Type", "application/json");
    }

    if (this.config.bearerToken && !headers.has("Authorization")) {
      headers.set("Authorization", `Bearer ${this.config.bearerToken}`);
    }

    if (this.config.idempotencyKey && !headers.has("Idempotency-Key")) {
      headers.set("Idempotency-Key", this.config.idempotencyKey);
    }

    const response = await fetch(url, { ...options, headers });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const error = new Error((data as ProblemDetails).detail || `HTTP ${response.status}`);
      (error as any).status = response.status;
      (error as any).problem = data;
      throw error;
    }

    return data as T;
  }

  // --- Auth Endpoints (API-04, RV-09) ---
  async requestShopperMagicLink(orderId: string, shopperId: string = "shopper_1"): Promise<{
    magic_link_url: string;
    order_id: string;
    shopper_id: string;
    access_token: string;
    expires_in_seconds: number;
  }> {
    return this.request("/v1/auth/shopper-magic-link", {
      method: "POST",
      body: JSON.stringify({ order_id: orderId, shopper_id: shopperId }),
    });
  }

  async issueStaffToken(
    merchantId: string,
    staffId: string,
    role: "MERCHANT_ADMIN" | "MERCHANT_OPERATOR" | "REVIEWER" | "PACKER" | "RECEIVER" = "MERCHANT_ADMIN",
    ttlSeconds: number = 86400
  ): Promise<{
    access_token: string;
    token_type: string;
    expires_in_seconds: number;
    merchant_id: string;
    staff_id: string;
    role: string;
  }> {
    return this.request("/v1/auth/staff-token", {
      method: "POST",
      body: JSON.stringify({
        merchant_id: merchantId,
        staff_id: staffId,
        role: role,
        ttl_seconds: ttlSeconds,
      }),
    });
  }

  // --- Return Lifecycle Endpoints (F-03, F-05, Section 26) ---
  async createReturn(orderId: string, orderItemId?: string, reasonCode: string = "CHANGED_MIND"): Promise<{
    return_id: string;
    order_id: string;
    state: string;
  }> {
    return this.request("/v1/returns", {
      method: "POST",
      body: JSON.stringify({
        order_id: orderId,
        order_item_id: orderItemId,
        reason_code: reasonCode,
      }),
    });
  }

  async getReturn(returnId: string): Promise<Record<string, any>> {
    return this.request(`/v1/returns/${returnId}`);
  }

  async submitDeclaration(returnId: string, payload: ReturnDeclarationRequest): Promise<Record<string, any>> {
    return this.request(`/v1/returns/${returnId}/declaration`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async submitEvidence(returnId: string, payload: ReturnEvidenceRequest): Promise<Record<string, any>> {
    return this.request(`/v1/returns/${returnId}/evidence`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async cancelReturn(returnId: string): Promise<{ return_id: string; state: string }> {
    return this.request(`/v1/returns/${returnId}/cancel`, {
      method: "POST",
    });
  }

  async getSignedReceipts(returnId: string): Promise<Record<string, any>> {
    return this.request(`/v1/returns/${returnId}/receipts`);
  }

  async getSignedReceipt(returnId: string): Promise<Record<string, any>> {
    return this.getSignedReceipts(returnId);
  }

  // --- Keep-Offer Endpoints (FR-78, RV-04, INV-06) ---
  async getKeepOffer(returnId: string): Promise<{
    keep_offer_id: string;
    return_id: string;
    amount_minor: number;
    status: string;
    currency: string;
    expires_at: string;
  }> {
    const raw = await this.request<any>(`/v1/returns/${returnId}/keep-offer`);
    return {
      keep_offer_id: raw.keep_offer_id,
      return_id: raw.return_id,
      amount_minor: raw.posted_price?.amount_minor ?? raw.amount_minor ?? 0,
      status: raw.status ?? "OFFERED",
      currency: raw.posted_price?.currency ?? raw.currency ?? "USD",
      expires_at: raw.expires_at ?? "",
    };
  }

  async respondKeepOffer(
    returnId: string,
    action: "ACCEPT" | "DECLINE"
  ): Promise<Record<string, any>> {
    return this.request(`/v1/returns/${returnId}/keep-offer/respond`, {
      method: "POST",
      body: JSON.stringify({ action }),
    });
  }

  // --- Carrier Ingestion Pipeline (FR-96, Section 25.1) ---
  async postCarrierEvent(returnId: string, eventType: string): Promise<{
    recorded: boolean;
    return_id: string;
    type: string;
    new_state: string;
    custody_event_id: string;
  }> {
    return this.request("/v1/carrier-events", {
      method: "POST",
      body: JSON.stringify({ return_id: returnId, type: eventType }),
    });
  }

  // --- Simulation & Analytics Pipeline (FR-52, FR-102) ---
  async simulateMechanism(payload: SimulateRequestPayload): Promise<{
    lane: string;
    timing: string;
    x_released_minor: number;
    holdback_minor: number;
    audit_probability: number;
    binding_constraint: string;
    simulated_gain_minor: number;
    feasibility_map: any[];
    roi: { annual_savings_usd: number; roi_multiple: number };
  }> {
    return this.request("/v1/simulate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getFeasibilityMap(declaredGrade: string = "B"): Promise<any[]> {
    return this.request(`/v1/simulate/feasibility-map?declared_grade=${declaredGrade}`);
  }

  async getMerchantRoi(): Promise<Record<string, any>> {
    return this.request("/v1/simulate/roi");
  }

  // --- Passport Public Verification ---
  async getPublicPassport(passportId: string): Promise<Record<string, any>> {
    return this.request(`/v1/passports/${passportId}`);
  }

  // --- Demo Diagnostics ---
  async advanceDemoClock(durationSeconds: number): Promise<Record<string, any>> {
    return this.request("/v1/demo/clock/advance", {
      method: "POST",
      body: JSON.stringify({ duration_seconds: durationSeconds }),
    });
  }
}
