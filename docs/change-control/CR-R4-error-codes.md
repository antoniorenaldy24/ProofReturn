# Change Request `CR-R4-error-codes` — API Error Code Catalog Extensions & Idempotent POST Surface (`RV3-08`, `AUD-40`, `API-06`, `API-07`, `API-11`)

- **Change Control ID**: `CR-R4-error-codes`
- **Date**: `2026-11-08`
- **Status**: `APPROVED / IMPLEMENTED`
- **SSOT Sections Referenced (without modifying `docs/SSOT.md`)**: Section 19.6 (Change Control), Section 28.1 (`API-06`, `API-07`, `API-11`), Section 28.2 (Error Code Catalog), Section 28.3 (Endpoint Contracts).
- **Authoritative Code Module**: [`backend/api/errors.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/errors.py)

---

## 1. Purpose

Per `docs/SSOT.md` Section 28.1 (`API-07`) and Section 19.6, all RFC 9457 `application/problem+json` error codes returned by the `/v1` API that extend the baseline 21 codes in SSOT §28.2 must be formally registered through Change Control and centralized in a single authoritative module (`backend/api/errors.py`).

Every `_problem(...)` call in [`backend/api/app.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/app.py) and middleware in [`backend/api/middleware.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/middleware.py) references constants from `backend/api/errors.py` (`ErrorCode.*`). Raw string literals or unregistered codes are prohibited and enforced by automated AST contract tests.

---

## 2. Extension Error Codes Not in SSOT §28.2 (`CR_R4_ERROR_CODES`)

### 2.1 Pre-Existing API Error Codes (19 Literal Codes + 2 Face-Blur Codes + 2 Middleware Codes)

| # | Error Code | HTTP Status | Origin | Meaning |
| :-: | :--- | :-: | :--- | :--- |
| 1 | `AGENT_EVIDENCE_FORBIDDEN` | `403` | Pre-existing (R3) | AI agent tokens are forbidden from obtaining or submitting physical return evidence (`INV-12`, `AZ-03`). |
| 2 | `AUTH_EXPIRED` | `401` | Pre-existing (R3) | Bearer JWT/HMAC token has passed its expiration timestamp (`exp`). |
| 3 | `CAPTURE_MISSING` | `409` | Pre-existing (R3) | Order has no recorded PayPal `capture_id` when attempting to plan a refund action (`INV-01`). |
| 4 | `CAPTURE_REQUIRED` | `409` | Pre-existing (R3) | Order or resale purchase requires a verified PayPal capture before proceeding. |
| 5 | `ENDPOINT_NOT_FOUND` | `404` | Pre-existing (R3) | Demo-only bootstrap endpoint accessed when `DEMO_MODE=false` (`RV2-01`, `RV3-05`). |
| 6 | `FORBIDDEN` | `403` | Pre-existing (R3) | Authenticated principal lacks tenant or subject ownership for the target resource. |
| 7 | `FORBIDDEN_ROLE` | `403` | Pre-existing (R3) | Authenticated staff role is not permitted to perform an administrative operation (e.g., demo reset). |
| 8 | `INVALID_ROLE` | `422` | Pre-existing (R3) | Requested staff role is not in the valid SSOT Section 29 role matrix. |
| 9 | `INVALID_WEBHOOK_SIGNATURE` | `400` | Pre-existing (R3) | PayPal webhook transmission headers are missing or cryptographic signature verification failed (`TM-06`). |
| 10 | `MALFORMED_JSON` | `400` | Pre-existing (R3) | Request payload is not valid JSON syntax. |
| 11 | `MERCHANT_NOT_FOUND` | `404` / `409` | Pre-existing (R3) / R4-T3 | Referenced merchant record does not exist (`404` on lookup; `409` fail-closed when evaluating exposure cap per `RV3-03`). |
| 12 | `NO_KEEP_OFFER` | `404` | Pre-existing (R3) | Return has no active or eligible posted keep-offer (`RV2-03`). |
| 13 | `NO_REVIEW_FOUND` | `409` | Pre-existing (R3) | Appeal filed on a return that has no prior human review decision to appeal. |
| 14 | `ORDER_NOT_FOUND` | `404` | Pre-existing (R3) | Referenced `order_id` does not exist or belongs to another merchant tenant. |
| 15 | `RESOURCE_NOT_FOUND` | `404` | Pre-existing (R3) | Target domain entity (return, order, passport, listing, appeal, policy) not found or out of caller scope (`TZ-04`). |
| 16 | `RETURN_NOT_FOUND` | `404` | Pre-existing (R3) | Referenced `return_id` does not exist or is outside the caller's tenant scope. |
| 17 | `ROLE_FORBIDDEN` | `403` | Pre-existing (R3) | Principal type or staff role is not authorized for this endpoint under the Section 29 Role Matrix. |
| 18 | `SAME_REVIEWER_CONFLICT` | `409` | Pre-existing (R3) | Appeal reviewer is identical to the original review decider (violates reviewer independence `FR-37`, `AUD-29`). |
| 19 | `TERMS_NOT_ACCEPTED` | `400` | Pre-existing (R3) | Shopper did not explicitly accept fast-lane terms on return declaration (`FR-14`, `INV-06`). |
| 20 | `UNBLURRED_FACE_REJECTED` | `422` | Pre-existing (R3, `blur_check.reason`) | Evidence media contains detected faces without client-side blur applied before upload (`FR-16`, `TM-12`). |
| 21 | `BLUR_BUDGET_EXCEEDED_50MS` | `422` | Pre-existing (R3, `blur_check.reason`) | On-device face blur latency exceeded the 50 ms per-frame performance budget (`FR-16`). |
| 22 | `RATE_LIMIT_EXCEEDED` | `429` | Pre-existing (R3, Middleware) | Per-IP/principal sliding-window request rate limit exceeded (`RateLimiterMiddleware`). |
| 23 | `PAYLOAD_TOO_LARGE` | `413` | Pre-existing (R3, Middleware) | Request `Content-Length` exceeds maximum allowed body size (`RequestBodyLimitMiddleware`, `AUD-30`). |

### 2.2 Error Codes Added in Remediation Round 4 (Tasks T1–T8)

| # | Error Code | HTTP Status | Task Origin | Meaning |
| :-: | :--- | :-: | :--- | :--- |
| 24 | `ORDER_FROZEN` | `409` | `R4-T1` (`RV3-11`, `FR-75`) | Order refund planning/execution is frozen due to an open PayPal dispute (`frozen_by_dispute`) or capture reversal (`capture_reversed`). |
| 25 | `CAPTURE_FAILED` | `409` | `R4-T2` (`RV3-01`, `RV3-02`) | PayPal capture failed or returned no provider capture ID; resale listing ownership transfer is aborted. |
| 26 | `JURISDICTION_CAP_VIOLATION` | `422` / `409` | `R4-T4` (`RV3-06`, `INV-11`, `FR-10`) | Policy refund curve or misdeclaration fee violates SSOT jurisdiction caps (`422` on policy creation; `409` when order uses an inactive/violating policy or engine refuses curve). |
| 27 | `INVALID_WEBHOOK_PAYLOAD` | `400` | `R4-T5` (`RV3-04`) | PayPal webhook payload is missing a non-empty string event `"id"`. |
| 28 | `IDEMPOTENCY_KEY_REQUIRED` | `400` | `R4-T8` (`RV3-08`, `API-06`) | Missing required `Idempotency-Key` header on a POST endpoint that plans, executes, or changes a refund, capture, ownership transfer, or policy. |

---

## 3. Mandatory `Idempotency-Key` POST Endpoints (`API-06`, `RV3-08`)

Every POST endpoint that can plan, execute, or change a **refund**, a **capture**, an **ownership transfer**, or a **policy** requires a non-empty `Idempotency-Key` request header:
- Missing or empty `Idempotency-Key` $\rightarrow$ `400 IDEMPOTENCY_KEY_REQUIRED`
- Same `Idempotency-Key` + identical JSON request body $\rightarrow$ replays the cached `200`/`201` response without re-executing side effects
- Same `Idempotency-Key` + different JSON request body $\rightarrow$ `409 IDEMPOTENCY_CONFLICT`
- Keys are scoped per tenant and principal (`POST:{route_pattern}:{principal.merchant_id}:{principal.sub}:{idempotency_key}`)

| # | Endpoint | Category | Request Schema (`backend/api/schemas.py`) | Side Effect Protected |
| :-: | :--- | :--- | :--- | :--- |
| 1 | `POST /v1/returns` | Refund lifecycle | `CreateReturnRequest` | Creates `Return` entity and CSPRNG audit commitment |
| 2 | `POST /v1/returns/{return_id}/evidence` | Refund (`R0`) | `EvidenceSubmissionRequest` | Runs `decide_release` and plans `R0` `RefundAction` |
| 3 | `POST /v1/returns/{return_id}/keep-offer/respond` | Refund (`KEEP`) | `KeepOfferRespondRequest` | Accepts/declines keep-offer; plans `KEEP` `RefundAction` |
| 4 | `POST /v1/review/{return_id}/decision` | Refund (`SETTLEMENT`) | `ReviewDecisionRequest` | Runs `settle_return` and plans `SETTLEMENT` `RefundAction` |
| 5 | `POST /v1/audits/{return_id}` | Refund (`SETTLEMENT`) | `AuditResultRequest` | Records physical audit and computes settlement refund |
| 6 | `POST /v1/review/appeals/{appeal_id}/decision` | Refund (`APPEAL_COMPENSATION`) | `DecideAppealRequest` | Decides appeal; plans compensating `RefundAction` |
| 7 | `POST /v1/orders/{order_id}/passport` | Ownership transfer | `OrderPassportRequest` | Mints and binds origin `Passport` (`ORIGIN_MINTED`) to order |
| 8 | `POST /v1/passports` | Ownership transfer | `MintPassportRequest` | Mints `Passport` (`ORIGIN_MINTED`) |
| 9 | `POST /v1/resale/listings` | Ownership transfer | `CreateResaleListingRequest` | Creates `ResaleListing` for passport resale |
| 10 | `POST /v1/resale/listings/{listing_id}/order` | Capture & Ownership transfer | `PurchaseResaleListingRequest` | Captures PayPal order and transfers passport (`RESALE_SOLD`) |
| 11 | `POST /v1/policies` | Policy | `CreatePolicyRequest` | Validates jurisdiction caps and persists merchant `Policy` |
