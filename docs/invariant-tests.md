# Invariant Test Suite Mapping

This document maps all system invariants defined in SSOT §29 (`INV-01` through `INV-18`), plus functional invariants `FR-65` (challenge nonce verification) and `FR-75` (dispute/chargeback freeze), and database isolation guarantees (`AUD-34`, `AUD-38`, `RV3-09`) to their dedicated negative automated tests executed through the API.

Each test verifies that when an invariant violation is attempted:
1. The API immediately rejects the request with an RFC 9457 error problem (HTTP 4xx).
2. No state is persisted to the database or mutated.
3. No external call (e.g., PayPal refund) is dispatched.

---

## Invariant Mapping Matrix

| Invariant | SSOT Ref | Test ID / Function Name | Test File | Negative Test Action & Assertion |
| :--- | :--- | :--- | :--- | :--- |
| **INV-01** | §29.1 | `test_inv01_over_refund_attempt_rejected_and_unpersisted` | `backend/tests/invariants/test_inv01_to_inv04_money_and_state.py` | Attempt settlement/refund exceeding capture capacity. Rejection: HTTP 409 `REFUND_LIMIT_EXCEEDED`; order balance untouched, no `RefundAction` persisted. |
| **INV-02** | §29.1 | `test_inv02_cross_merchant_refund_rejected_with_404` | `backend/tests/invariants/test_inv01_to_inv04_money_and_state.py` | Cross-merchant staff attempt to access or settle another merchant's return/order. Rejection: HTTP 404 `RESOURCE_NOT_FOUND` (BOLA isolation TZ-04); victim resources unmutated. |
| **INV-03** | §29.1 | `test_inv03_outbox_retry_reuses_identical_request_id` | `backend/tests/invariants/test_inv01_to_inv04_money_and_state.py` | Outbox executor retries mutating refund. Assertion: Retried calls reuse identical `PayPal-Request-Id` (`request_id`); never fabricates provider IDs. |
| **INV-04** | §29.1 | `test_inv04_illegal_state_transition_rejected_and_unpersisted` | `backend/tests/invariants/test_inv01_to_inv04_money_and_state.py` | Attempt illegal state transition (cancelling a settled return). Rejection: HTTP 409 `INVALID_STATE_TRANSITION`; return state remains `SETTLED`, no refund actions created. |
| **INV-05** | §29.1 | `test_inv05_model_output_cannot_directly_trigger_paypal` | `backend/tests/invariants/test_inv05_to_inv08_engine_and_custody.py` | Attempt direct payment invocation bypassing Policy Engine. Rejection: HTTP 404/405; review decision enforces `via_policy_engine: true`. |
| **INV-06** | §29.1 | `test_inv06_explanation_required_and_bounds_never_disclosed` | `backend/tests/invariants/test_inv05_to_inv08_engine_and_custody.py` | Money decisions require non-empty explanation. Negative assertion: Mechanism bounds (`k_max`, `p_max`, exposure limits) are never leaked in API responses. |
| **INV-07** | §29.1 | `test_inv07_non_custodial_no_wallet_no_payouts_client` | `backend/tests/invariants/test_inv05_to_inv08_engine_and_custody.py` | Non-custodial guarantee. Rejection: Wallet, escrow, and payout endpoints return 404/405; PayPal client has no Payouts client. |
| **INV-08** | §29.1 | `test_inv08_records_only_custody_no_insurance_or_risk_pooling` | `backend/tests/invariants/test_inv05_to_inv08_engine_and_custody.py` | No insurance or risk-pooling. Custody ledger enforces `records_only=True`; claim/indemnity endpoints return 404/405. |
| **INV-09** | §29.1 | `test_inv09_tampered_passport_chain_fails_validation` | `backend/tests/invariants/test_inv09_to_inv13_security_and_fairness.py` | Tampered event payload/signature in database. Verification via `GET /v1/passports/{id}/verify` returns `chain_valid=False`. |
| **INV-10** | §29.1 | `test_inv10_gross_finding_without_conformal_exclusion_charges_zero_fee` | `backend/tests/invariants/test_inv09_to_inv13_security_and_fairness.py` | Gross downgrade without conformal exclusion at $\alpha_{\text{accuse}}$. Server ignores caller override: `f_charged_minor == 0`, `status_affected == False`. |
| **INV-11** | §29.1 | `test_inv11_jurisdiction_cap_violation_rejected_at_policy_creation` | `backend/tests/invariants/test_inv09_to_inv13_security_and_fairness.py` | Policy violating jurisdiction caps (EU $F > 0$ or excessive holdback curve). Rejection: HTTP 422 `JURISDICTION_CAP_VIOLATION`; policy not persisted. |
| **INV-12** | §29.1 | `test_inv12_agent_cannot_complete_physical_challenge_or_act_before_assessed` | `backend/tests/invariants/test_inv09_to_inv13_security_and_fairness.py` | Agent token attempts challenge request (403), evidence submission (403), or keep-offer acceptance before ASSESSED (409). |
| **INV-13** | §29.1 | `test_inv13_unblurred_face_evidence_rejected` | `backend/tests/invariants/test_inv09_to_inv13_security_and_fairness.py` | Evidence submitted with unblurred detected faces (`client_blur_applied=False`). Rejection: HTTP 422 `UNBLURRED_FACE_REJECTED` / `VALIDATION_FAILED`; evidence not stored. |
| **INV-14** | §29.1 | `test_inv14_pre_checkin_release_never_exceeds_merchant_exposure_cap` | `backend/tests/invariants/test_inv14_to_inv18_caps_and_degraded.py` | Pre-checkin release when merchant instant exposure cap is exhausted. Rejection: HTTP 409 `INVALID_STATE_TRANSITION` (`exposure_cap_ok=False`). |
| **INV-15** | §29.1 | `test_inv15_adjacent_grade_difference_never_penalized` | `backend/tests/invariants/test_inv14_to_inv18_caps_and_degraded.py` | Adjacent mismatch (declared B, verified C). Verification: `f_charged_minor == 0`, `status_affected == False`, no penalty fee charged. |
| **INV-16** | §29.1 | `test_inv16_mismatched_audit_seed_reveal_rejected` | `backend/tests/invariants/test_inv14_to_inv18_caps_and_degraded.py` | Reveal audit seed with mismatched value against pre-committed hash $c$. Rejection: `ValueError` raised, audit verification fails. |
| **INV-17** | §29.1 | `test_inv17_refiled_returns_never_receive_pre_checkin_money` | `backend/tests/invariants/test_inv14_to_inv18_caps_and_degraded.py` | Re-filed return (`refiled=True`) attempts pre-checkin release. Rejection: `InvalidStateTransitionError` raised; forced to STANDARD lane ($R_0 = 0$). |
| **INV-18** | §29.1 | `test_inv18_degraded_modes_never_increase_release_or_advance_timing` | `backend/tests/invariants/test_inv14_to_inv18_caps_and_degraded.py` | Evidence evaluated in degraded/fallback mode (no live model keys). Assertion: Forces STANDARD lane and timing R3; never advances release timing. |
| **FR-65** | §26.2 | `test_fr65_missing_or_mismatched_nonce_routes_to_standard_lane` | `backend/tests/invariants/test_fr65_and_fr75_nonce_and_freeze.py` | Evidence submitted with missing/empty challenge nonce OCR. Assertion: `challenge_valid=False`, routed to STANDARD lane with `CHALLENGE_NOT_VERIFIED`, $R_0 = 0$. |
| **FR-75** | §26.3 | `test_fr75_dispute_freeze_blocks_refund_planning_with_409` | `backend/tests/invariants/test_fr65_and_fr75_nonce_and_freeze.py` | Order frozen by dispute (`CUSTOMER.DISPUTE.CREATED`). Planning: HTTP 409 `ORDER_FROZEN`; Outbox: action marked `BLOCKED_BY_DISPUTE`, PayPal call refused. |
| **ISOLATION** | AUD-34 | `test_data_proofreturn_db_hash_unmodified_before_and_after` | `backend/tests/invariants/test_db_isolation.py` | Tests verify that `data/proofreturn.db` SHA-256 hash before and after test suite run is completely identical. |

---

## Test Execution Commands

### 1. Pure Unit Subset (No SQLAlchemy / DB fixture required)
```bash
uv run pytest backend/tests/state_machine backend/tests/policy_engine backend/tests/golden -p no:cacheprovider
```

### 2. Full Invariants Suite
```bash
uv run pytest backend/tests/invariants -v
```

### 3. Complete Backend Test Suite
```bash
uv run pytest -m "not sandbox and not live_model"
```
