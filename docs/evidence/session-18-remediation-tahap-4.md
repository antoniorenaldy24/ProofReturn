# Evidence Report: Session 18 — Re-Audit Remediation Tahap 4 (Identity Minting, Rate Limiting & Body Protection, Resilient Fallbacks, Conformal Confidence Margin & Contract Testing)

**Date**: 2026-11-02  
**Author**: Antigravity Assistant  
**Re-Audit Roadmap & Finding References**: RV-05, RV-06, RV-07, RV-09, AUD-03, AUD-14, AUD-15, AUD-26, AUD-30, AUD-34, ST-11, CT-02, CT-08, J-08, J-09, J-10, FR-53, INV-18, NFR-04, API-04  

---

## 1. Executive Summary

Tahap 4 delivers complete remediation for all remaining items in Section J.2 ("Should Fix Before Production") of `Laporan Audit Ulang — ProofReturn (Versi Revisi).md`, closing architectural, security, testing, and operational gaps:

1. **`RV-09` (MEDIUM) & `API-04` — Staff & Shopper Identity Minting Endpoints**:
   - Implemented `POST /v1/auth/staff-token` in [`backend/api/app.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/app.py) allowing verified merchant staff (`MERCHANT_ADMIN`, `MERCHANT_OPERATOR`, `REVIEWER`, `PACKER`, `RECEIVER`) to mint scoped JWTs.
   - Implemented `POST /v1/auth/shopper-magic-link` in [`backend/api/app.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/app.py) generating order-scoped magic-link tokens and returning deep URLs (`/returns?token=...&order_id=...`).
   - Defined strict request schemas `IssueStaffTokenRequest` and `IssueShopperMagicLinkRequest` in [`backend/api/schemas.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/schemas.py).

2. **`AUD-30` (LOW) — Rate Limiting & Request Body Size Limit Middleware**:
   - Implemented `RateLimiterMiddleware` in [`backend/api/middleware.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/middleware.py) providing token-bucket and sliding window rate limiting per IP and per Bearer token.
   - Exceeding quotas returns RFC 9457 HTTP 429 `RATE_LIMIT_EXCEEDED` with `Retry-After`, `X-RateLimit-Limit`, and `X-RateLimit-Remaining` headers.
   - Implemented `RequestBodyLimitMiddleware` in [`backend/api/middleware.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/middleware.py) rejecting request payloads exceeding 10MB with RFC 9457 HTTP 413 `PAYLOAD_TOO_LARGE`.

3. **`AUD-14` (MEDIUM) — Injected Settings & Non-Demo Default**:
   - Hardened `create_app` in [`backend/api/app.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/app.py) to default `is_demo = False` (clean empty repository, no synthetic demo orders seeded) unless explicitly requested via `demo_mode=True`, `DEMO_MODE=true`, or `settings.demo_mode=True`.

4. **`AUD-15` (MEDIUM) & `INV-18` — Section 31.3 Degraded Fallback Integration**:
   - Connected `apply_fallback_degradation` from `backend/policy_engine/release.py` into `POST /v1/returns/{return_id}/evidence` in [`backend/api/app.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/app.py).
   - Upstream degradation signals (e.g. `X-Fallback-Degradation: FB-04` or detector outages) automatically route release decisions to degraded mode, enforcing invariant `INV-18` (released funds $X$ never increase and timing is never advanced under degraded conditions).

5. **`RV-07` (LOW) — Conformal Prediction Gate AG-01 Statistical Confidence Margin**:
   - Updated `verify_gate_ag01` in [`backend/ai/calibration/conformal.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/ai/calibration/conformal.py) to incorporate finite-sample normal approximation / Clopper-Pearson statistical confidence intervals ($z \cdot \sqrt{\frac{\alpha(1-\alpha)}{n}}$ with $z=1.96$), ensuring test split evaluations do not reject valid calibrators due to empirical binomial sample variance.

6. **`RV-06` (MEDIUM) & `RV-05` (MEDIUM) — CI Marker Preservation & Secret Scanner Hardening**:
   - Updated [`.github/workflows/ci.yml`](file:///c:/Users/renal/Downloads/ProofReturn/.github/workflows/ci.yml) to execute `uv run pytest -v -m "not live_model and not sandbox"`, eliminating the buggy `-m "not live"` argument that previously overrode marker exclusions.
   - Hardened [`scripts/scan_secrets.py`](file:///c:/Users/renal/Downloads/ProofReturn/scripts/scan_secrets.py) to eliminate blind exception suppression, actively inspect `.env.example`, verify git-ignored status of all `.env*` variants, and report diagnostic warnings.

7. **`AUD-26` (LOW) & `FR-53` — Non-Literal Key Derivation in Journeys**:
   - Replaced hardcoded literal secret keys `b"merch_secret_key_32_bytes_minimum"` in [`backend/domain/journeys.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/domain/journeys.py) with salts derived securely from `get_settings().serial_hash_salt`.

8. **`AUD-34`, `AUD-03`, `ST-11` & `CT-02` — Contract Testing & Multi-Threaded Concurrency**:
   - Verified exact contract parity between REST API evidence response and direct Policy Engine calculation (`decide_release`).
   - Verified concurrent refund requests with the identical `request_id` (`ST-11`, `CT-08`) execute idempotently across 8 worker threads with zero duplicate charges.
   - Verified concurrent multi-threaded race conditions attempting to over-refund an order (`CT-02`, `INV-01`) are safely rejected under reentrant locks with `OverRefundError("INV-01 violation")`.

---

## 2. Verification & Test Evidence

### 2.1 Dedicated Tahap 4 Remediation Suite
Command:
```powershell
uv run pytest backend/tests/remediation/test_remediation_tahap4_contracts_and_hardening.py -v
```
Output:
```
backend/tests/remediation/test_remediation_tahap4_contracts_and_hardening.py::test_rv09_staff_token_minting_and_authorization PASSED [  7%]
backend/tests/remediation/test_remediation_tahap4_contracts_and_hardening.py::test_rv09_shopper_magic_link_issuance_and_access PASSED [ 15%]
backend/tests/remediation/test_remediation_tahap4_contracts_and_hardening.py::test_aud30_rate_limiter_middleware_429 PASSED [ 23%]
backend/tests/remediation/test_remediation_tahap4_contracts_and_hardening.py::test_aud30_request_body_size_limit_413 PASSED [ 30%]
backend/tests/remediation/test_remediation_tahap4_contracts_and_hardening.py::test_aud14_create_app_defaults_non_demo PASSED [ 38%]
backend/tests/remediation/test_remediation_tahap4_contracts_and_hardening.py::test_aud15_apply_fallback_degradation_via_api PASSED [ 46%]
backend/tests/remediation/test_remediation_tahap4_contracts_and_hardening.py::test_rv07_conformal_gate_ag01_statistical_margin PASSED [ 53%]
backend/tests/remediation/test_remediation_tahap4_contracts_and_hardening.py::test_rv06_ci_workflow_preserves_live_markers PASSED [ 61%]
backend/tests/remediation/test_remediation_tahap4_contracts_and_hardening.py::test_rv05_secret_scanner_detects_untracked_and_example_hygiene PASSED [ 69%]
backend/tests/remediation/test_remediation_tahap4_contracts_and_hardening.py::test_aud26_journeys_serial_salt_without_literal_key PASSED [ 76%]
backend/tests/remediation/test_remediation_tahap4_contracts_and_hardening.py::test_aud34_contract_api_evidence_matches_policy_engine PASSED [ 84%]
backend/tests/remediation/test_remediation_tahap4_contracts_and_hardening.py::test_st11_concurrent_refund_idempotency_with_same_request_id PASSED [ 92%]
backend/tests/remediation/test_remediation_tahap4_contracts_and_hardening.py::test_ct02_concurrent_over_refund_race_condition_rejected PASSED [100%]
======================== 13 passed, 1 warning in 2.49s ========================
```

### 2.2 Full Project Test Suite
Command:
```powershell
uv run pytest
```
Output:
```
================ 130 passed, 3 deselected, 1 warning in 13.00s ================
```
*Pass rate: **100% PASS** (130 passed, 0 failed, 3 live-model/sandbox deselected via flags).*

### 2.3 Secret Scanner & Reference Integrity
Commands:
```powershell
uv run python scripts/scan_secrets.py
uv run python scripts/check_refs.py
```
Output:
```
Scanned 220 files across repository.
[OK] Secret scan passed: 0 credentials or leaked keys detected.
check-refs PASSED (XR-01..XR-10 verified).
```

### 2.4 RTM Traceability Matrix
- **VERIFIED**: **30** requirements (elevated `FR-53` with non-mock test proofs).
- **IMPLEMENTED**: **45** requirements.
- **SPECIFIED**: **62** requirements.
- Total: **137** requirements (100% synchronized in `docs/rtm.csv`).
