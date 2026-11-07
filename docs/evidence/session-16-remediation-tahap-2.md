# Evidence Report: Session 16 — Re-Audit Remediation Tahap 2 (Real Policy Engine, DB Persistence, Dynamic Guards, Keep-Offer Consistency, Route Templating & Auth Protection)

**Date**: 2026-11-02  
**Author**: Antigravity Assistant  
**Re-Audit Roadmap & Finding References**: J-04, J-05, J-08, J-09, AUD-01 (HIGH), AUD-04 (HIGH), AUD-06 (MEDIUM), RV-03 (HIGH), RV-04 (MEDIUM), RV-11 (MEDIUM), AUD-14 (LOW), AUD-22 (LOW), AUD-25 (LOW), AUD-29 (MEDIUM), FR-88, TM-15  

---

## 1. Executive Summary

Tahap 2 completes the overhaul of the ProofReturn API layer and core domain execution engines, eliminating all mock and in-memory remnants identified in `Laporan Audit Ulang — ProofReturn (Versi Revisi).md`:

1. **`AUD-01` (HIGH) & `J-04` — Real Policy Engine Release Calculations**:
   - Wired [`backend/api/app.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/app.py) `POST /v1/returns/{return_id}/evidence` to run `decide_release()` using real order values and calibrate configs (`_illustrative_calib`).
   - For `$380.00` order items (`ord_demo_1`) with declared grade B, the exact computed R0 tranche is `$212.49` (`21249` minor), replacing the legacy hardcoded mock value (`22157`).
   - Generated Ed25519-signed `Decision` records and persisted them directly to `DatabaseRepository`.

2. **`AUD-06` (MEDIUM) & `J-04` — Zero In-Memory Dictionaries / 100% DB Persistence**:
   - Removed all ephemeral dictionaries (`orders`, `returns`, `passports`, `declarations_store`, `appeals_store`, `resale_store`) from [`backend/api/app.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/app.py).
   - Every entity (Returns, Orders, Passports, Passport Events, Custody Events, Keep Offers, Decisions, Reviews, Appeals, Resale Listings) is strictly read from and written to `DatabaseRepository` using idempotent `session.merge()`.
   - Verified that data persists across server restarts and cross-app re-instantiations.

3. **`AUD-04` (HIGH), `J-08` & `RFC 9457` — Pydantic Request Models & Strict Error Contracts**:
   - Created [`backend/api/schemas.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/schemas.py) defining validated Pydantic models for all API requests.
   - Removed all permissive defaults: `fast_lane_terms_accepted` and `client_blur_faces_applied` must be explicitly verified.
   - Registered RFC 9457 exception handlers for `RequestValidationError`, `pydantic.ValidationError` (returning HTTP 422 `VALIDATION_FAILED` with `application/problem+json`), and `json.JSONDecodeError` (HTTP 400 `MALFORMED_JSON`).

4. **`RV-03` (HIGH) & `J-04` — Dynamic State Machine Guards**:
   - Eliminated literal `True` guards across all transitions.
   - Dynamic `within_window` check evaluates `(now - order.created_at).days <= policy.return_window_days`. Return requests exceeding the window fail with 409 `INVALID_STATE_TRANSITION`.
   - Dynamic `exposure_cap_ok` check evaluates merchant instant exposure limits in the DB.
   - Agent tokens are strictly prohibited from declining keep offers to bypass physical evidence inspection (`INV-12`, `RV-03`).

5. **`RV-04` (MEDIUM) & `J-04` — Consistent Posted Keep-Offer Pricing**:
   - Wired `_get_or_compute_keep_offer()` using `compute_posted_keep_offer()`.
   - Both `GET /v1/returns/{id}/keep-offer` and `POST /v1/returns/{id}/keep-offer/respond` read and write the exact same `amount_minor` from the canonical `keep_offers` table.
   - Eliminated the previous divergence (18000 on GET vs 5320 on POST). Internal reservation bounds (`k_max_minor`) remain strictly confidential (`INV-06`, `MV-18`).

6. **`RV-11` (MEDIUM), `TM-15` & `J-09` — Protected Observability Endpoints & Templated Metric Paths**:
   - Updated [`backend/api/middleware.py`](file:///c:/Users/renal/Downloads/ProofReturn/backend/api/middleware.py) to use `_get_metric_route_path(request)` so Prometheus metric labels use templated route paths (`/v1/returns/{return_id}/declaration`) rather than dynamic IDs, preventing metric cardinality explosion and data leakage.
   - Protected `GET /v1/metrics` and `GET /v1/ops/alerts` behind loopback IP checks (`127.0.0.1`, `::1`, `localhost`) or staff Bearer token authorization. Unauthenticated external requests receive HTTP 401, while shopper tokens receive HTTP 403.

7. **`AUD-29` (MEDIUM), `AUD-22` (LOW), `AUD-25` (LOW) & `FR-88` — Authorization Hardening & Return Cancellation**:
   - Implemented `POST /v1/returns/{id}/cancel` executing `CANCEL_RETURN` via the state machine (`FR-88`).
   - Enforced reviewer independence on appeals: original reviewers are strictly prohibited from deciding appeals filed against their decisions, returning HTTP 409 `SAME_REVIEWER_CONFLICT` (`AUD-29`).
   - Enforced authentication on `POST /v1/resale/listings/{id}/order`, returning HTTP 401 for unauthenticated requests (`AUD-22`).
   - Hardened `POST /v1/privacy/deletion-requests` to execute crypto-shredding key erasure (`AUD-25`).

---

## 2. Verification & Test Evidence

### 2.1 Dedicated Tahap 2 Remediation Suite
Command:
```powershell
uv run pytest backend/tests/remediation/test_remediation_tahap2_api_and_engine.py -v
```
Output:
```
backend/tests/remediation/test_remediation_tahap2_api_and_engine.py::test_aud01_real_policy_engine_calculation_on_evidence PASSED [  9%]
backend/tests/remediation/test_remediation_tahap2_api_and_engine.py::test_aud04_pydantic_validation_and_rfc9457_error_contracts PASSED [ 18%]
backend/tests/remediation/test_remediation_tahap2_api_and_engine.py::test_aud06_zero_in_memory_state_persistence PASSED [ 27%]
backend/tests/remediation/test_remediation_tahap2_api_and_engine.py::test_rv03_dynamic_state_machine_guards PASSED [ 36%]
backend/tests/remediation/test_remediation_tahap2_api_and_engine.py::test_rv04_keep_offer_price_consistency PASSED [ 45%]
backend/tests/remediation/test_remediation_tahap2_api_and_engine.py::test_rv11_metrics_and_alerts_protection_and_route_templating PASSED [ 54%]
backend/tests/remediation/test_remediation_tahap2_api_and_engine.py::test_aud29_reviewer_independence_on_appeals PASSED [ 63%]
backend/tests/remediation/test_remediation_tahap2_api_and_engine.py::test_fr88_return_cancellation_endpoint PASSED [ 72%]
backend/tests/remediation/test_remediation_tahap2_api_and_engine.py::test_aud14_signed_receipts_and_csprng_seed PASSED [ 81%]
backend/tests/remediation/test_remediation_tahap2_api_and_engine.py::test_aud22_resale_order_authentication PASSED [ 90%]
backend/tests/remediation/test_remediation_tahap2_api_and_engine.py::test_aud25_privacy_deletion_lifecycle PASSED [100%]
======================== 11 passed, 1 warning in 2.78s ========================
```

### 2.2 Full Project Test Suite
Command:
```powershell
uv run pytest
```
Output:
```
================ 111 passed, 2 deselected, 1 warning in 8.06s =================
```

### 2.3 Secret Scanner & Reference Integrity
Commands:
```powershell
uv run python scripts/scan_secrets.py
uv run python scripts/check_refs.py
```
Output:
```
[OK] Secret scan passed: 0 credentials or leaked keys detected.
check-refs PASSED (XR-01..XR-10 verified).
```
