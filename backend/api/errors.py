"""Centralized RFC 9457 Error Code Catalog for ProofReturn /v1 API (Section 28.2, RV3-08, API-07).

Contains:
1. `SSOT_ERROR_CODES`: Canonical error codes defined in `docs/SSOT.md` Section 28.2.
2. `CR_R4_ERROR_CODES`: Change-controlled extension error codes documented in
   `docs/change-control/CR-R4-error-codes.md` (19 pre-existing codes + privacy/middleware codes +
   codes added in Remediation Round 4 Tasks T1-T8).
3. `ALL_ERROR_CODES`: Complete registry of permitted error codes.
4. `ErrorCode`: Namespace of string constants used by all `_problem(...)` calls.
"""

from __future__ import annotations

from typing import Any


class ErrorCode:
    """Typed string constants for all RFC 9457 error codes used across the API."""

    # --- SSOT Section 28.2 Canonical Codes (21) ---
    AUTH_REQUIRED = "AUTH_REQUIRED"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN_ACTION = "FORBIDDEN_ACTION"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    VERSION_CONFLICT = "VERSION_CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    RETURN_WINDOW_CLOSED = "RETURN_WINDOW_CLOSED"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    CHALLENGE_EXPIRED = "CHALLENGE_EXPIRED"
    KEEP_OFFER_ACTION_INVALID = "KEEP_OFFER_ACTION_INVALID"
    KEEP_OFFER_EXPIRED = "KEEP_OFFER_EXPIRED"
    REFILE_STANDARD_ONLY = "REFILE_STANDARD_ONLY"
    REFUND_LIMIT_EXCEEDED = "REFUND_LIMIT_EXCEEDED"
    RATE_LIMITED = "RATE_LIMITED"
    UPSTREAM_PAYMENT_ERROR = "UPSTREAM_PAYMENT_ERROR"
    SERVICE_DEGRADED = "SERVICE_DEGRADED"
    RETAKE_LIMIT_REACHED = "RETAKE_LIMIT_REACHED"
    APPEAL_WINDOW_CLOSED = "APPEAL_WINDOW_CLOSED"
    NOT_CANCELLABLE = "NOT_CANCELLABLE"
    KEEP_OFFER_NOT_ELIGIBLE = "KEEP_OFFER_NOT_ELIGIBLE"

    # --- Change-Controlled Extension Codes (CR-R4-error-codes.md) ---
    # Pre-existing 19 literal codes in app.py
    AGENT_EVIDENCE_FORBIDDEN = "AGENT_EVIDENCE_FORBIDDEN"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    CAPTURE_MISSING = "CAPTURE_MISSING"
    CAPTURE_REQUIRED = "CAPTURE_REQUIRED"
    ENDPOINT_NOT_FOUND = "ENDPOINT_NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    FORBIDDEN_ROLE = "FORBIDDEN_ROLE"
    INVALID_ROLE = "INVALID_ROLE"
    INVALID_WEBHOOK_SIGNATURE = "INVALID_WEBHOOK_SIGNATURE"
    MALFORMED_JSON = "MALFORMED_JSON"
    MERCHANT_NOT_FOUND = "MERCHANT_NOT_FOUND"
    NO_KEEP_OFFER = "NO_KEEP_OFFER"
    NO_REVIEW_FOUND = "NO_REVIEW_FOUND"
    ORDER_NOT_FOUND = "ORDER_NOT_FOUND"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RETURN_NOT_FOUND = "RETURN_NOT_FOUND"
    ROLE_FORBIDDEN = "ROLE_FORBIDDEN"
    SAME_REVIEWER_CONFLICT = "SAME_REVIEWER_CONFLICT"
    TERMS_NOT_ACCEPTED = "TERMS_NOT_ACCEPTED"

    # Dynamic privacy face-blur verification codes (FR-16)
    UNBLURRED_FACE_REJECTED = "UNBLURRED_FACE_REJECTED"
    BLUR_BUDGET_EXCEEDED_50MS = "BLUR_BUDGET_EXCEEDED_50MS"

    # Middleware error codes (AUD-30, rate limiting)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"

    # Remediation Round 4 additions (T1-T8)
    ORDER_FROZEN = "ORDER_FROZEN"
    CAPTURE_FAILED = "CAPTURE_FAILED"
    JURISDICTION_CAP_VIOLATION = "JURISDICTION_CAP_VIOLATION"
    INVALID_WEBHOOK_PAYLOAD = "INVALID_WEBHOOK_PAYLOAD"
    IDEMPOTENCY_KEY_REQUIRED = "IDEMPOTENCY_KEY_REQUIRED"


SSOT_ERROR_CODES: dict[str, dict[str, Any]] = {
    ErrorCode.AUTH_REQUIRED: {
        "http_status": 401,
        "meaning": "Missing or invalid authentication token",
    },
    ErrorCode.NOT_FOUND: {
        "http_status": 404,
        "meaning": "Resource not found or not in caller's scope",
    },
    ErrorCode.FORBIDDEN_ACTION: {
        "http_status": 403,
        "meaning": "In scope but action not allowed for role or agent scope",
    },
    ErrorCode.VALIDATION_FAILED: {
        "http_status": 422,
        "meaning": "Schema or business validation failed",
    },
    ErrorCode.INVALID_STATE_TRANSITION: {
        "http_status": 409,
        "meaning": "Action not allowed in current return lifecycle state (Section 26.3)",
    },
    ErrorCode.VERSION_CONFLICT: {
        "http_status": 409,
        "meaning": "If-Match optimistic concurrency version mismatch",
    },
    ErrorCode.IDEMPOTENCY_CONFLICT: {
        "http_status": 409,
        "meaning": "Idempotency-Key reused with a different request payload",
    },
    ErrorCode.RETURN_WINDOW_CLOSED: {
        "http_status": 422,
        "meaning": "Return requested or declared outside the merchant return window",
    },
    ErrorCode.EVIDENCE_INCOMPLETE: {
        "http_status": 422,
        "meaning": "Required return evidence artifacts are missing",
    },
    ErrorCode.CHALLENGE_EXPIRED: {
        "http_status": 422,
        "meaning": "Live evidence challenge script expired (default 10 min)",
    },
    ErrorCode.KEEP_OFFER_ACTION_INVALID: {
        "http_status": 422,
        "meaning": "Only accept or decline are valid actions for a posted keep-offer",
    },
    ErrorCode.KEEP_OFFER_EXPIRED: {
        "http_status": 422,
        "meaning": "Posted keep-offer has expired",
    },
    ErrorCode.REFILE_STANDARD_ONLY: {
        "http_status": 200,
        "meaning": "Re-filed return accepted on the standard lane (no pre-check-in release)",
    },
    ErrorCode.REFUND_LIMIT_EXCEEDED: {
        "http_status": 409,
        "meaning": "Requested refund would exceed remaining refundable capture balance (violates INV-01)",
    },
    ErrorCode.RATE_LIMITED: {
        "http_status": 429,
        "meaning": "Too many requests (Retry-After header set)",
    },
    ErrorCode.UPSTREAM_PAYMENT_ERROR: {
        "http_status": 502,
        "meaning": "Upstream PayPal error surfaced (with paypal_debug_id for staff roles only)",
    },
    ErrorCode.SERVICE_DEGRADED: {
        "http_status": 503,
        "meaning": "Downstream dependency unavailable; protective safe default applied",
    },
    ErrorCode.RETAKE_LIMIT_REACHED: {
        "http_status": 422,
        "meaning": "Evidence capture retake attempts exhausted; alternative path offered (FR-66)",
    },
    ErrorCode.APPEAL_WINDOW_CLOSED: {
        "http_status": 422,
        "meaning": "Shopper appeal filed after the appeal window closed",
    },
    ErrorCode.NOT_CANCELLABLE: {
        "http_status": 409,
        "meaning": "A refund tranche was already submitted; return cannot be cancelled",
    },
    ErrorCode.KEEP_OFFER_NOT_ELIGIBLE: {
        "http_status": 422,
        "meaning": "Keep-offer eligibility or frequency rules not met (FR-78)",
    },
}

CR_R4_ERROR_CODES: dict[str, dict[str, Any]] = {
    # Pre-existing 19 literal codes from R3 baseline
    ErrorCode.AGENT_EVIDENCE_FORBIDDEN: {
        "http_status": 403,
        "origin": "Pre-existing (R3)",
        "meaning": "AI agent tokens are forbidden from obtaining or submitting physical return evidence (INV-12, AZ-03)",
    },
    ErrorCode.AUTH_EXPIRED: {
        "http_status": 401,
        "origin": "Pre-existing (R3)",
        "meaning": "Bearer JWT/HMAC token has passed its expiration timestamp (exp)",
    },
    ErrorCode.CAPTURE_MISSING: {
        "http_status": 409,
        "origin": "Pre-existing (R3)",
        "meaning": "Order has no recorded PayPal capture_id when attempting to plan a refund action (INV-01)",
    },
    ErrorCode.CAPTURE_REQUIRED: {
        "http_status": 409,
        "origin": "Pre-existing (R3)",
        "meaning": "Order or resale purchase requires a verified PayPal capture before proceeding",
    },
    ErrorCode.ENDPOINT_NOT_FOUND: {
        "http_status": 404,
        "origin": "Pre-existing (R3)",
        "meaning": "Demo-only bootstrap endpoint accessed when DEMO_MODE=false (RV2-01, RV3-05)",
    },
    ErrorCode.FORBIDDEN: {
        "http_status": 403,
        "origin": "Pre-existing (R3)",
        "meaning": "Authenticated principal lacks tenant or subject ownership for the target resource",
    },
    ErrorCode.FORBIDDEN_ROLE: {
        "http_status": 403,
        "origin": "Pre-existing (R3)",
        "meaning": "Authenticated staff role is not permitted to perform an administrative operation (e.g. demo reset)",
    },
    ErrorCode.INVALID_ROLE: {
        "http_status": 422,
        "origin": "Pre-existing (R3)",
        "meaning": "Requested staff role is not in the valid SSOT role matrix",
    },
    ErrorCode.INVALID_WEBHOOK_SIGNATURE: {
        "http_status": 400,
        "origin": "Pre-existing (R3)",
        "meaning": "PayPal webhook transmission headers are missing or cryptographic signature verification failed (TM-06)",
    },
    ErrorCode.MALFORMED_JSON: {
        "http_status": 400,
        "origin": "Pre-existing (R3)",
        "meaning": "Request payload is not valid JSON syntax",
    },
    ErrorCode.MERCHANT_NOT_FOUND: {
        "http_status": 409,
        "http_statuses": [404, 409],
        "origin": "Pre-existing (R3) / R4-T3",
        "meaning": "Referenced merchant record does not exist (404 on lookup; 409 fail-closed when evaluating exposure cap per RV3-03)",
    },
    ErrorCode.NO_KEEP_OFFER: {
        "http_status": 404,
        "origin": "Pre-existing (R3)",
        "meaning": "Return has no active or eligible posted keep-offer (RV2-03)",
    },
    ErrorCode.NO_REVIEW_FOUND: {
        "http_status": 409,
        "origin": "Pre-existing (R3)",
        "meaning": "Appeal filed on a return that has no prior human review decision to appeal",
    },
    ErrorCode.ORDER_NOT_FOUND: {
        "http_status": 404,
        "origin": "Pre-existing (R3)",
        "meaning": "Referenced order_id does not exist or belongs to another merchant tenant",
    },
    ErrorCode.RESOURCE_NOT_FOUND: {
        "http_status": 404,
        "origin": "Pre-existing (R3)",
        "meaning": "Target domain entity (return, order, passport, listing, appeal, policy) not found or out of caller scope (TZ-04)",
    },
    ErrorCode.RETURN_NOT_FOUND: {
        "http_status": 404,
        "origin": "Pre-existing (R3)",
        "meaning": "Referenced return_id does not exist or is outside the caller's tenant scope",
    },
    ErrorCode.ROLE_FORBIDDEN: {
        "http_status": 403,
        "origin": "Pre-existing (R3)",
        "meaning": "Principal type or staff role is not authorized for this endpoint under the Section 29 Role Matrix",
    },
    ErrorCode.SAME_REVIEWER_CONFLICT: {
        "http_status": 409,
        "origin": "Pre-existing (R3)",
        "meaning": "Appeal reviewer is identical to the original review decider (violates reviewer independence FR-37, AUD-29)",
    },
    ErrorCode.TERMS_NOT_ACCEPTED: {
        "http_status": 400,
        "origin": "Pre-existing (R3)",
        "meaning": "Shopper did not explicitly accept fast-lane terms on return declaration (FR-14, INV-06)",
    },
    # Privacy face-blur verification codes (FR-16)
    ErrorCode.UNBLURRED_FACE_REJECTED: {
        "http_status": 422,
        "origin": "Pre-existing (R3, dynamic blur_check.reason)",
        "meaning": "Evidence media contains detected faces without client-side blur applied before upload (FR-16, TM-12)",
    },
    ErrorCode.BLUR_BUDGET_EXCEEDED_50MS: {
        "http_status": 422,
        "origin": "Pre-existing (R3, dynamic blur_check.reason)",
        "meaning": "On-device face blur latency exceeded the 50 ms per-frame performance budget (FR-16)",
    },
    # Middleware codes
    ErrorCode.RATE_LIMIT_EXCEEDED: {
        "http_status": 429,
        "origin": "Pre-existing (R3, RateLimiterMiddleware)",
        "meaning": "Per-IP/principal sliding-window request rate limit exceeded",
    },
    ErrorCode.PAYLOAD_TOO_LARGE: {
        "http_status": 413,
        "origin": "Pre-existing (R3, RequestBodyLimitMiddleware)",
        "meaning": "Request Content-Length exceeds maximum allowed body size (AUD-30)",
    },
    # Remediation Round 4 additions (T1-T8)
    ErrorCode.ORDER_FROZEN: {
        "http_status": 409,
        "origin": "Added in R4-T1",
        "meaning": "Order refund planning/execution is frozen due to an open PayPal dispute (frozen_by_dispute) or capture reversal (capture_reversed) (RV3-11, FR-75)",
    },
    ErrorCode.CAPTURE_FAILED: {
        "http_status": 409,
        "origin": "Added in R4-T2",
        "meaning": "PayPal capture failed or returned no provider capture ID; resale listing ownership transfer aborted (RV3-01, RV3-02)",
    },
    ErrorCode.JURISDICTION_CAP_VIOLATION: {
        "http_status": 422,
        "http_statuses": [409, 422],
        "origin": "Added in R4-T4",
        "meaning": "Policy refund curve or misdeclaration fee violates SSOT jurisdiction caps (422 on policy creation; 409 when order uses an inactive/violating policy per RV3-06, INV-11, FR-10)",
    },
    ErrorCode.INVALID_WEBHOOK_PAYLOAD: {
        "http_status": 400,
        "origin": "Added in R4-T5",
        "meaning": "PayPal webhook payload is missing a non-empty string event id (RV3-04)",
    },
    ErrorCode.IDEMPOTENCY_KEY_REQUIRED: {
        "http_status": 400,
        "origin": "Added in R4-T8",
        "meaning": "Missing required Idempotency-Key header on a POST endpoint that plans, executes, or changes a refund, capture, ownership transfer, or policy (RV3-08, API-06)",
    },
}

ALL_ERROR_CODES: dict[str, dict[str, Any]] = {
    **SSOT_ERROR_CODES,
    **CR_R4_ERROR_CODES,
}

# Expose all error codes as module-level constants as well
for _code_key in ALL_ERROR_CODES:
    globals()[_code_key] = _code_key

__all__ = [
    "ALL_ERROR_CODES",
    "CR_R4_ERROR_CODES",
    "ErrorCode",
    "SSOT_ERROR_CODES",
    *ALL_ERROR_CODES.keys(),
]
