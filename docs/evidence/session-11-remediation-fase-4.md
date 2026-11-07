# Evidence Report: Session 11 — Remediation Fase 4 (AI Pipeline Hardening & Conformal Calibration)

**Date**: 2026-11-02  
**Author**: Antigravity Assistant  
**Auditor Finding References**: AUD-08, AUD-09, AUD-10, AUD-13, AUD-17, AUD-18, J-08, J-09  
**SSOT Invariants & Requirements**: Section 7.5, Section 8.4 (Rule 5), Section 8.7, Section 31.1, Section 31.2 (Gate AG-01), FR-08, FR-09, FR-32, FR-73, FR-74, FR-91, INV-01, INV-06, INV-10, INV-15  

---

## 1. Executive Summary

Fase R4 addresses and remediates key functional, algorithmic, and calibration issues uncovered during the independent technical audit (`Laporan Audit Teknis Independen — ProofReturn.md`):
1. **AUD-08 & Rule 5 / FR-73**: Gross condition discrepancies ($|\text{verified} - \text{declared}| \ge 2$) without reviewer confirmation no longer settle immediately at merchant-claimed grades. Remaining tranches are strictly frozen and the return is routed to `ESCALATED`.
2. **AUD-09 & INV-10 / FR-32**: Unsafe settlement defaults (`excluded_at_alpha_accuse=True`, `has_merchant_evidence=True`) are hardened to protective `False`. Reviewer confirmation alone without conformal exclusion at $\alpha_{\text{accuse}}$ or hard identity failure cannot charge misdeclaration fee $F$ or restrict shopper trust tier.
3. **AUD-10 & FR-08 / FR-09 / INV-06**: Refund curve values displayed in REST API (`/v1/orders/{order_id}/policy`), Agent Gateway MCP (`get_return_policy`), and demo storefront are reconciled with canonical SSOT and `config/policy_defaults.json` (Grade C: 0.80, Grade D: 0.50).
4. **AUD-13 & Section 8.7 / FR-91**: Single-step promotion constraint enforced in `evaluate_tier_promotion`. Shopper accounts in `NEW` tier can only promote to `ESTABLISHED`, strictly preventing multi-tier leapfrogging to `TRUSTED`.
5. **AUD-17 & FR-74 / INV-06**: Dead ternary expression removed from `backend/policy_engine/release.py:331`. Decisions for returns without origin passport explicitly return `lane="NO_PASSPORT"` with R1 timing.
6. **AUD-18 & INV-01**: `RefundLedger.plan_refund_action` rejects re-planning attempts for the same decision and tranche with differing amounts via `IdempotencyConflictError`.
7. **ADR-017 & Section 7.5 / AG-01 / DS-03**: Implemented `MondrianConformalCalibrator` with finite-sample order statistic quantiles at $\alpha_{\text{route}} = 0.10$ and $\alpha_{\text{accuse}} = 0.02$, downward/upward exclusion tests, and passing Gate AG-01 on test split ($\ge 98\%$ coverage at $\alpha_{\text{accuse}}$, $\ge 90\%$ coverage at $\alpha_{\text{route}}$).

---

## 2. Code Modifications & Architecture

### 2.1 Conformal Calibration Engine (`backend/ai/calibration/conformal.py`)
- Implemented `MondrianConformalCalibrator`:
  - `compute_conformal_quantile(scores, alpha)`: Computes $\lceil (n+1)(1-\alpha) \rceil$-th order statistic.
  - `fit_category(category, sessions)`: Fits per-category nonconformity quantiles on calibration split DS-03.
  - `evaluate(category, declared_grade, cum_probs)`: Evaluates downward plausible set $S_\alpha(x)$ and exclusion at $\alpha_{\text{route}} = 0.10$ and $\alpha_{\text{accuse}} = 0.02$; tests upward under-declaration for automatic top-ups (FR-28).
  - `verify_gate_ag01(category, test_sessions)`: Evaluates empirical one-sided coverage against Section 31.2 Gate AG-01.

### 2.2 Deterministic Settlement Guard (`backend/policy_engine/settlement.py`)
- Hardened `SettlementInput` defaults:
  - `human_confirmed_gross: bool = False`
  - `excluded_at_alpha_accuse: bool = False`
  - `has_merchant_evidence: bool = False`
- Added `status: str` and `is_escalated: bool` to `SettlementResult`.
- Enforced Rule 5: When gross gap or hard failure occurs without human confirmation, return status `ESCALATED`, freeze tranches at $X$ (`additional_refund_minor = 0`), and defer settlement until manual review.
- Enforced INV-10: Reviewer confirmation without conformal exclusion at $\alpha_{\text{accuse}}$ or hard failure settles at verified grade without fee $F$ and without status penalty.

### 2.3 Single-Step Trust Promotion (`backend/domain/trust.py`)
- Enforced single-step state transitions:
  - `NEW` $\to$ `ESTABLISHED` (or `NEW`)
  - `ESTABLISHED` $\to$ `TRUSTED` (or `ESTABLISHED`)
  - `RESTRICTED` $\to$ `NEW` (or `RESTRICTED`)
  - `TRUSTED` $\to$ `TRUSTED`

### 2.4 Refund Curve Reconciled Across Surfaces
- `backend/api/app.py`: Updated `/v1/orders/{order_id}/policy` and `/v1/policies` to return `{ "A": 1.0, "B": 0.95, "C": 0.80, "D": 0.50 }`.
- `backend/agent_gateway/mcp_server.py`: Updated `get_return_policy` to return `{ "A": 1.0, "B": 0.95, "C": 0.80, "D": 0.50 }`.
- `apps/demo-storefront/src/App.tsx`: Updated storefront preview card to `{ A: 1.0, B: 0.95, C: 0.80, D: 0.50 }`.

### 2.5 Idempotency Conflict Enforcement (`backend/payments/ledger.py`)
- Added `IdempotencyConflictError(ValueError)`.
- If an action already exists in `_actions_by_request_id` and the requested `amount_minor` differs, raises `IdempotencyConflictError`.

### 2.6 NO_PASSPORT Lane Preservation (`backend/policy_engine/release.py`)
- Line 331: Fixed dead ternary expression to `lane=lane_name`.

---

## 3. Test Verification Results

Suite execution command:
```bash
uv run pytest -v
```

Output:
```
============================= test session starts =============================
platform win32 -- Python 3.12.13, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\renal\Downloads\ProofReturn
configfile: pyproject.toml
testpaths: backend/tests
plugins: anyio-4.15.1, hypothesis-6.170.13
collected 86 items / 2 deselected / 84 selected

backend/tests/ai/test_ai_pipeline_and_jobs.py .....                      [  5%]
backend/tests/ai/test_gemini_provider.py .....                           [ 11%]
backend/tests/api/test_api_authz_and_mcp.py .....                        [ 17%]
backend/tests/api/test_full_rest_api_v1.py ...                           [ 21%]
backend/tests/api/test_remediation_fase3_persistence_and_concurrency.py ..... [ 27%]
backend/tests/domain/test_domain_and_schemas.py ....                     [ 32%]
backend/tests/golden/test_golden_examples.py ..........                  [ 44%]
backend/tests/mechanism/test_minimum_shippable_and_journeys.py ......    [ 51%]
backend/tests/ops/test_privacy_observability_and_ops.py .......          [ 59%]
backend/tests/payments/test_payments_and_failures.py .....               [ 65%]
backend/tests/policy_engine/test_mechanism_verification.py ............. [ 80%]
.....                                                                    [ 86%]
backend/tests/remediation/test_remediation_fase4_ai_and_calibration.py ....... [ 95%]
backend/tests/state_machine/test_return_state_machine.py ....            [100%]

================= 84 passed, 2 deselected, 1 warning in 3.27s =================
```

Cross-reference verification:
```bash
uv run python scripts/check_refs.py
```
Output:
```
check-refs PASSED (XR-01..XR-10 verified).
```
