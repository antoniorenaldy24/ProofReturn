# Evidence Report: Session 17 — Re-Audit Remediation Tahap 3 (Real PayPal Payments, Webhook Signature Verification, DB Deduplication & ST-01 Staged Refunds)

**Date**: 2026-11-02  
**Author**: Antigravity Assistant  
**Re-Audit Roadmap & Finding References**: J-06, ST-01, AUD-02 (HIGH), AUD-24 (HIGH), RV-14 (LOW), INV-01, INV-02, INV-03, INV-07, NFR-04, FR-75, AUD-12, AUD-42  

---

## 1. Executive Summary

Tahap 3 delivers the complete remediation of the payment execution engine and webhook lifecycle, resolving all payment stubbing and webhook security vulnerabilities from `Laporan Audit Ulang — ProofReturn (Versi Revisi).md`:

1. **`AUD-02` (HIGH), `INV-01`, `INV-03`, `INV-07` & `J-06` — Real PayPal Sandbox Capture & Refund Execution**:
   - Replaced static stub implementations in [`backend/payments/client.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/payments/client.py).
   - Implemented `capture_order_live` executing real `POST /v2/checkout/orders/{id}/capture` with OAuth2 Bearer authorization and optional `PayPal-Request-Id`.
   - Implemented `refund_capture_live` executing real `POST /v2/payments/captures/{id}/refund` with OAuth2 Bearer authorization, mandatory `PayPal-Request-Id` (`INV-03`), decimal amount formatting (`value_str = f"{amount_minor / 100:.2f}"`), and correlation fields (`invoice_id`, `custom_id`, `note_to_payer`).
   - Wired `capture_order` and `refund_capture` to automatically invoke live Sandbox endpoints whenever live credentials are provided, while gracefully providing structured responses during offline test suites without crashing.

2. **`AUD-24` (HIGH) & `NFR-04` — Fail-Closed Webhook Signature Verification**:
   - Eliminated the vulnerability where webhooks lacking the `X-PayPal-Signature-Valid` header were accepted by default.
   - Updated `POST /v1/webhooks/paypal` in [`backend/api/app.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/app.py) to be strictly fail-closed:
     - Unsigned or unauthenticated requests with missing headers are rejected with HTTP 400 `INVALID_WEBHOOK_SIGNATURE`.
     - Untrusted or malicious certificate URLs are rejected with HTTP 400.
     - Live PayPal webhook transmissions are verified via `verify_webhook_signature_live()` calling PayPal's `/v1/notifications/verify-webhook-signature`.

3. **`RV-14` (LOW) & `AUD-12` — Database-Backed Webhook Event Deduplication**:
   - Replaced process-memory-only cache (`_seen_event_ids: BoundedTTLCache`) in [`backend/payments/webhooks.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/payments/webhooks.py) with persistent `DatabaseRepository` queries against the canonical `webhook_events` table.
   - When duplicate events are redelivered after a server restart or process crash, `WebhookProcessor` identifies the existing `event_id` from the database and idempotently returns `duplicate: True` with HTTP 200.
   - Webhook processing atomically freezes orders upon `CUSTOMER.DISPUTE.CREATED` and zeroes refundable balances upon `PAYMENT.CAPTURE.REVERSED`.

4. **`ST-01` & `INV-01` — Staged Multi-Tranche Refunds & Over-Refund Rejection**:
   - Tested and verified sequential staged refunds on an order capture ($380.00 / 38000 minor):
     - R0 partial refund: $212.49 (21249 minor)
     - CHECKIN partial refund: $107.51 (10751 minor)
     - HOLDBACK settlement refund: $60.00 (6000 minor)
   - Verified that a 4th refund attempt for even 1 minor cent ($0.01) is immediately rejected under reentrant lock with `OverRefundError("INV-01 violation")` before calling PayPal.
   - Wired `POST /v1/returns/{id}/evidence` and `POST /v1/review/{id}/decision` in [`backend/api/app.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/app.py) to plan and persist real `RefundAction` records into `DatabaseRepository`.

---

## 2. Verification & Test Evidence

### 2.1 Dedicated Tahap 3 Remediation Suite
Command:
```powershell
uv run pytest backend/tests/remediation/test_remediation_tahap3_payments_and_webhooks.py -v
```
Output:
```
backend/tests/remediation/test_remediation_tahap3_payments_and_webhooks.py::test_aud02_real_paypal_capture_and_refund_formatting PASSED [ 16%]
backend/tests/remediation/test_remediation_tahap3_payments_and_webhooks.py::test_aud24_webhook_signature_verification_fail_closed PASSED [ 33%]
backend/tests/remediation/test_remediation_tahap3_payments_and_webhooks.py::test_rv14_webhook_event_deduplication_persisted_in_database PASSED [ 50%]
backend/tests/remediation/test_remediation_tahap3_payments_and_webhooks.py::test_j06_st01_staged_partial_refunds_and_over_refund_rejection PASSED [ 66%]
backend/tests/remediation/test_remediation_tahap3_payments_and_webhooks.py::test_j06_evidence_and_review_persists_refund_actions_in_database PASSED [ 83%]
backend/tests/remediation/test_remediation_tahap3_payments_and_webhooks.py::test_webhook_dispute_freezes_order_and_blocks_further_refunds PASSED [100%]
================= 6 passed, 1 deselected, 1 warning in 3.25s ==================
```

### 2.2 Full Project Test Suite
Command:
```powershell
uv run pytest
```
Output:
```
================ 117 passed, 3 deselected, 1 warning in 10.08s ================
```
*Pass rate: **100% PASS** (117 passed, 3 live-model/sandbox deselected via flags).*

### 2.3 Secret Scanner & Reference Integrity
Commands:
```powershell
uv run python scripts/scan_secrets.py
uv run python scripts/check_refs.py
```
Output:
```
[OK] Secret scan passed: 0 credentials or leaked keys detected across 218 files.
check-refs PASSED (XR-01..XR-10 verified).
```
