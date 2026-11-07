"""Invariant tests for INV-05, INV-06, INV-07, INV-08 through the API (SSOT Section 29.1).

INV-05: Model output never directly triggers a PayPal call. Only deterministic policy engine does.
INV-06: Every money decision has a non-empty explanation; bounds (k_max, p_max) are never disclosed.
INV-07: Non-custodial: ProofReturn never holds, pools, or moves funds between third parties;
        no ProofReturn wallet, no Payouts client.
INV-08: No insurance or risk-pooling products; custody liability is records only (records_only=True).
"""

from __future__ import annotations

from typing import Any
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token


def test_inv05_model_output_cannot_directly_trigger_paypal(reset_db: Any) -> None:
    """INV-05 NEGATIVE: AI Model outputs can NEVER directly trigger a PayPal call or refund.

    Only the deterministic Policy Engine plans and validates financial actions.
    Attempting to directly trigger payment from AI model endpoints or bypassing Policy Engine is blocked.
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    tok_reviewer = mint_staff_token("merch_a", "REVIEWER", sub="rev_inv05")

    # 1. Attempting to directly call any hypothetical direct-refund endpoint without Policy Engine fails
    r_direct = client.post(
        "/v1/payments/execute-raw",
        headers={"Authorization": f"Bearer {tok_reviewer}", "Idempotency-Key": "ik-inv05-raw"},
        json={"amount_minor": 10000, "reason": "AI_SUGGESTION"},
    )
    assert r_direct.status_code in {404, 405}

    # 2. Decision via review endpoint MUST report via_policy_engine == True
    r_review = client.post(
        "/v1/review/ret_demo_escalated/decision",
        headers={"Authorization": f"Bearer {tok_reviewer}", "Idempotency-Key": "ik-inv05-pe"},
        json={"outcome": "SETTLE_VERIFIED", "verified_grade": "D"},
    )
    assert r_review.status_code == 200
    res_data = r_review.json()
    assert res_data.get("via_policy_engine") is True


def test_inv06_explanation_required_and_bounds_never_disclosed(reset_db: Any) -> None:
    """INV-06: Every money decision has a non-empty explanation.

    NEGATIVE: Bounds (k_max, p_max, exposure limits) are NEVER disclosed to shoppers or public.
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    tok_shopper = mint_shopper_token("ord_demo_1", "shopper_1")

    # 1. Submit evidence to get R0 decision
    r_ev = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {tok_shopper}", "Idempotency-Key": "ik-inv06-ev"},
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": "raw/ret_demo_1/evidence.mp4",
            "sha256": "a" * 64,
            "challenge_step": 1,
            "faces_detected": 0,
            "client_blur_applied": False,
            "blur_latency_ms": 12.0,
        },
    )
    assert r_ev.status_code == 200
    ev_data = r_ev.json()

    # Explanation must be non-empty string
    explanation = ev_data.get("explanation")
    assert isinstance(explanation, str)
    assert len(explanation.strip()) > 0

    # NEGATIVE: Internal bounds must NOT be present in shopper-visible response
    serialized = str(ev_data).lower()
    assert "k_max" not in serialized
    assert "p_max" not in serialized
    assert "instant_exposure_cap" not in serialized

    # 2. Query policy endpoint
    r_pol = client.get(
        "/v1/orders/ord_demo_1/policy",
        headers={"Authorization": f"Bearer {tok_shopper}"},
    )
    assert r_pol.status_code == 200
    pol_data = r_pol.json()
    pol_serialized = str(pol_data).lower()
    assert "k_max" not in pol_serialized
    assert "p_max" not in pol_serialized


def test_inv07_non_custodial_no_wallet_no_payouts_client(reset_db: Any) -> None:
    """INV-07 NEGATIVE: ProofReturn is non-custodial; never holds, pools, or moves funds between third parties.

    Asserts no wallet, escrow, or PayPal Payouts client endpoints or capabilities exist.
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    tok_admin = mint_staff_token("merch_a", "MERCHANT_ADMIN", sub="admin_inv07")

    # Negative endpoint checks: no wallet or payout endpoints exist
    for endpoint in ["/v1/wallets", "/v1/escrow/balance", "/v1/payouts", "/v1/paypal/payouts"]:
        r = client.get(endpoint, headers={"Authorization": f"Bearer {tok_admin}"})
        assert r.status_code in {404, 405}, f"Endpoint {endpoint} must not exist (INV-07 non-custodial)."

    # Verify PayPal client interface only has capture refund capability, no payouts client
    from backend.payments.client import PayPalSandboxClient
    pp_client = PayPalSandboxClient()
    assert not hasattr(pp_client, "create_payout"), "PayPal client must not have create_payout (INV-07)."
    assert not hasattr(pp_client, "payouts"), "PayPal client must not have payouts client (INV-07)."
    assert hasattr(pp_client, "refund_capture_live"), "PayPal client must support refund_capture_live."


def test_inv08_records_only_custody_no_insurance_or_risk_pooling(reset_db: Any) -> None:
    """INV-08: No insurance or risk-pooling products; custody liability is records only (records_only=True).

    NEGATIVE: Attempting to claim indemnity or insurance returns 404/422.
    """
    from backend.domain.custody import CustodyAttribution, CustodyLedger, CustodyCheckpoint

    # Verify domain module enforces records_only=True
    ledger = CustodyLedger(passport_id="pass_inv08_test", origin_grade="A", origin_weight_g=250)
    ledger.record_checkpoint(
        CustodyCheckpoint(
            interval="ORIGIN",
            actor="pack_01",
            grade_observed="A",
            weight_g=250,
            seal_intact=True,
        )
    )
    attr = ledger.attribute_condition_change(target_grade="B")
    assert attr.records_only is True

    # Any attempt to set financial liability or claim insurance fails or is non-existent
    assert not hasattr(attr, "insurance_coverage_minor")
    assert not hasattr(attr, "indemnity_payout_minor")

    # API verification: no insurance claim endpoints exist
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)
    tok_shopper = mint_shopper_token("ord_demo_1", "shopper_1")

    r_claim = client.post(
        "/v1/returns/ret_demo_1/insurance-claim",
        headers={"Authorization": f"Bearer {tok_shopper}"},
        json={"amount_minor": 10000},
    )
    assert r_claim.status_code in {404, 405}
