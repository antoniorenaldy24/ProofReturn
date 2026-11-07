"""Remediation tests for Fase R4: AI Pipeline Hardening & Conformal Calibration (AUD-08, AUD-09, AUD-10, AUD-13, AUD-17, AUD-18, ADR-017, AG-01)."""

from __future__ import annotations

import random
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from backend.agent_gateway.mcp_server import ProofReturnMcpServer
from backend.ai.calibration.conformal import (
    ConformalCalibrationSession,
    MondrianConformalCalibrator,
    compute_conformal_quantile,
)
from backend.api.app import create_app
from backend.auth.tokens import mint_agent_token, mint_shopper_token
from backend.domain.policy import PolicyConfig
from backend.domain.trust import TrustProfile, evaluate_tier_promotion
from backend.payments.ledger import IdempotencyConflictError, RefundLedger
from backend.policy_engine.release import (
    CalibrationInput,
    GapCalibration,
    ReleaseInput,
    decide_release,
)
from backend.policy_engine.settlement import SettlementInput, settle_return


def _dummy_calib_b() -> CalibrationInput:
    return CalibrationInput(
        declared_grade="B",
        adjacent_gap=GapCalibration(true_grade="C", q=Fraction(40, 100), d=Fraction(50, 100)),
        gross_gaps=[GapCalibration(true_grade="D", q=Fraction(90, 100), d=Fraction(95, 100))],
    )


@pytest.mark.req("AUD-08", "FR-73", "INV-10")
def test_aud08_gross_misdeclaration_escalates_and_freezes_tranches() -> None:
    """AUD-08 / Rule 5 / FR-73: Unconfirmed gross mismatch must route to ESCALATED and freeze tranches."""
    policy = PolicyConfig.default_us()

    # Shopper declared B, merchant verified D (gap = 2 steps).
    # Before human review (human_confirmed_gross=False):
    unconfirmed_inp = SettlementInput(
        price_minor=40000,
        capture_amount_minor=40000,
        declared_grade="B",
        verified_grade="D",
        x_released_minor=22157,
        holdback_minor=6000,
        f_minor=2000,
        human_confirmed_gross=False,
        excluded_at_alpha_accuse=True,
        has_merchant_evidence=True,
    )
    s_escalated = settle_return(unconfirmed_inp, policy)

    assert s_escalated.status == "ESCALATED"
    assert s_escalated.is_escalated is True
    # Tranches are frozen: shopper keeps released X, but receives 0 additional refund until review
    assert s_escalated.final_total_refund_minor == 22157
    assert s_escalated.additional_refund_minor == 0
    assert s_escalated.f_charged_minor == 0
    assert s_escalated.status_affected is False
    assert s_escalated.new_tier_override is None
    assert "Remaining tranches are frozen" in s_escalated.explanation

    # After human confirmation (human_confirmed_gross=True) with conformal exclusion:
    confirmed_inp = SettlementInput(
        price_minor=40000,
        capture_amount_minor=40000,
        declared_grade="B",
        verified_grade="D",
        x_released_minor=22157,
        holdback_minor=6000,
        f_minor=2000,
        human_confirmed_gross=True,
        excluded_at_alpha_accuse=True,
        has_merchant_evidence=True,
    )
    s_confirmed = settle_return(confirmed_inp, policy)

    assert s_confirmed.status == "SETTLED"
    assert s_confirmed.is_escalated is False
    assert s_confirmed.f_charged_minor == policy.compute_f_minor(40000)
    assert s_confirmed.status_affected is True
    assert s_confirmed.new_tier_override == "RESTRICTED"


@pytest.mark.req("AUD-09", "FR-32", "INV-10")
def test_aud09_protective_settlement_defaults_and_inv10_conformal_requirement() -> None:
    """AUD-09: SettlementInput defaults must be safe (False); human review without conformal exclusion cannot charge F."""
    policy = PolicyConfig.default_us()

    raw_inp = SettlementInput(
        price_minor=40000,
        capture_amount_minor=40000,
        declared_grade="B",
        verified_grade="D",
        x_released_minor=22157,
        holdback_minor=6000,
        f_minor=2000,
    )
    assert raw_inp.has_merchant_evidence is False
    assert raw_inp.excluded_at_alpha_accuse is False
    assert raw_inp.human_confirmed_gross is False

    # FR-32: If merchant claims D without evidence, effective grade falls back to declared B
    s_no_evidence = settle_return(raw_inp, policy)
    assert s_no_evidence.effective_verified_grade == "B"
    assert s_no_evidence.status == "SETTLED"
    assert not s_no_evidence.status_affected

    # INV-10: Reviewer confirms D, but no conformal exclusion (excluded_at_alpha_accuse=False) and no hard failure:
    s_no_conformal = settle_return(
        SettlementInput(
            price_minor=40000,
            capture_amount_minor=40000,
            declared_grade="B",
            verified_grade="D",
            x_released_minor=22157,
            holdback_minor=6000,
            f_minor=2000,
            human_confirmed_gross=True,
            excluded_at_alpha_accuse=False,
            hard_identity_failure=False,
            has_merchant_evidence=True,
        ),
        policy,
    )
    # Cannot charge F or restrict tier without objective statistical backing
    assert s_no_conformal.f_charged_minor == 0
    assert s_no_conformal.status_affected is False
    assert s_no_conformal.new_tier_override is None


@pytest.mark.req("AUD-10", "FR-08", "FR-09", "INV-06")
def test_aud10_refund_curve_reconciled_across_api_mcp_defaults() -> None:
    """AUD-10: Refund curves across API, MCP, and policy config must agree (C=0.80, D=0.50)."""
    # 1. Config defaults
    policy = PolicyConfig.default_us()
    assert policy.curve_json["A"] == "1.00"
    assert policy.curve_json["B"] == "0.95"
    assert policy.curve_json["C"] == "0.80"
    assert policy.curve_json["D"] == "0.50"

    # 2. REST API
    client = TestClient(create_app(demo_mode=True))
    shopper_token = mint_shopper_token("ord_demo_1", "shopper_1")
    resp = client.get("/v1/orders/ord_demo_1/policy", headers={"Authorization": f"Bearer {shopper_token}"})
    assert resp.status_code == 200
    curve_api = resp.json()["curve"]
    assert curve_api["C"] == 0.80
    assert curve_api["D"] == 0.50

    # 3. Agent Gateway MCP
    mcp = ProofReturnMcpServer()
    agent_tok = mint_agent_token(
        agent_id="agt_aud10",
        order_id="ord_demo_1",
        merchant_id="merch_demo_1",
        scopes=["read_policy"],
    )
    pol_mcp = mcp.get_return_policy(order_id="ord_demo_1", token=agent_tok)
    assert pol_mcp["curve"]["C"] == 0.80
    assert pol_mcp["curve"]["D"] == 0.50


@pytest.mark.req("AUD-13", "FR-91")
def test_aud13_single_step_trust_promotion() -> None:
    """AUD-13: Trust promotion must be single-step per Section 8.7; NEW cannot leapfrog to TRUSTED."""
    prof_new = TrustProfile(
        tier="NEW",
        clean_count=5,
        audited_confirmed_count=1,
        cumulative_verified_value_minor=75000,
        largest_clean_value_minor=20000,
        account_age_days=95,
    )
    # Satisfies ESTABLISHED requirements; must promote to ESTABLISHED, NOT TRUSTED
    promoted = evaluate_tier_promotion(prof_new)
    assert promoted == "ESTABLISHED"

    # Once at ESTABLISHED with the same high metrics, promote to TRUSTED
    prof_established = TrustProfile(
        tier="ESTABLISHED",
        clean_count=5,
        audited_confirmed_count=1,
        cumulative_verified_value_minor=75000,
        largest_clean_value_minor=20000,
        account_age_days=95,
    )
    assert evaluate_tier_promotion(prof_established) == "TRUSTED"


@pytest.mark.req("AUD-17", "FR-74", "INV-06")
def test_aud17_no_passport_lane_reported_explicitly() -> None:
    """AUD-17 & FR-74: When order has no origin passport, decision lane is preserved as NO_PASSPORT."""
    policy = PolicyConfig.default_us()
    calib = _dummy_calib_b()

    decision = decide_release(
        ReleaseInput(price_minor=10000, declared_grade="B", tier="TRUSTED", has_origin_passport=False),
        policy,
        calib,
    )
    assert decision.lane == "NO_PASSPORT"
    assert decision.timing == "R1"


@pytest.mark.req("AUD-18", "INV-01")
def test_aud18_ledger_replan_amount_conflict() -> None:
    """AUD-18: Re-planning a tranche with a different amount must raise IdempotencyConflictError."""
    ledger = RefundLedger()
    ledger.register_order(
        order_id="ord_aud18",
        merchant_id="merch_1",
        capture_id="cap_1",
        capture_amount_minor=50000,
    )

    action1 = ledger.plan_refund_action(
        order_id="ord_aud18",
        merchant_id="merch_1",
        capture_id="cap_1",
        decision_id="dec_aud18",
        tranche="R0",
        amount_minor=22157,
    )
    assert action1.amount_minor == 22157

    # Exact replan is idempotent and succeeds
    action_same = ledger.plan_refund_action(
        order_id="ord_aud18",
        merchant_id="merch_1",
        capture_id="cap_1",
        decision_id="dec_aud18",
        tranche="R0",
        amount_minor=22157,
    )
    assert action_same.request_id == action1.request_id

    # Replan with different amount raises conflict
    with pytest.raises(IdempotencyConflictError) as exc_info:
        ledger.plan_refund_action(
            order_id="ord_aud18",
            merchant_id="merch_1",
            capture_id="cap_1",
            decision_id="dec_aud18",
            tranche="R0",
            amount_minor=39999,
        )
    assert "AUD-18 idempotency conflict" in str(exc_info.value)


@pytest.mark.req("ADR-017", "AG-01", "DS-03", "INV-10")
def test_conformal_calibration_quantiles_and_gate_ag01() -> None:
    """ADR-017 & AG-01: Verify one-sided ordinal Mondrian conformal calibrator and deployment gate."""
    rng = random.Random(0)

    def gen_session(sid: str, cat: str) -> ConformalCalibrationSession:
        true_g = rng.choice(["A", "B", "C", "D"])
        is_hard = rng.random() < 0.01
        noise = rng.uniform(0.08, 0.20) if is_hard else rng.uniform(0.001, 0.02)
        if true_g == "A":
            probs = {"D": 1.0, "C": 0.99, "B": 0.97, "A": 1.0 - noise}
        elif true_g == "B":
            probs = {"D": 1.0, "C": 0.99, "B": 1.0 - noise, "A": 0.05}
        elif true_g == "C":
            probs = {"D": 1.0, "C": 1.0 - noise, "B": 0.08, "A": 0.02}
        else:
            probs = {"D": 1.0, "C": 0.05, "B": 0.02, "A": 0.01}
        return ConformalCalibrationSession(session_id=sid, category=cat, true_grade=true_g, cum_probs=probs)

    calib_sessions = [gen_session(f"calib_{i}", "electronics") for i in range(250)]
    test_sessions = [gen_session(f"test_{i}", "electronics") for i in range(250)]

    calibrator = MondrianConformalCalibrator(alpha_route=0.10, alpha_accuse=0.02)
    quantiles = calibrator.fit_category("electronics", calib_sessions)

    assert quantiles.n_samples == 250
    assert 0.0 <= quantiles.q_hat_route <= 1.0
    assert 0.0 <= quantiles.q_hat_accuse <= 1.0
    # Accuse quantile must be at least as conservative as route quantile
    assert quantiles.q_hat_accuse >= quantiles.q_hat_route

    # Test evaluation: Severe mismatch (Declared A, true state D with low probabilities)
    eval_mismatch = calibrator.evaluate(
        category="electronics",
        declared_grade="A",
        cum_probs={"D": 1.0, "C": 0.10, "B": 0.02, "A": 0.005},
    )
    assert eval_mismatch.excluded_at_alpha_route is True
    assert eval_mismatch.excluded_at_alpha_accuse is True
    assert "A" not in eval_mismatch.conformal_set_route
    assert "A" not in eval_mismatch.conformal_set_accuse

    # Verify AG-01 gate passes on test split
    gate_result = calibrator.verify_gate_ag01("electronics", test_sessions)
    assert gate_result["passed_ag01"] is True
    assert gate_result["coverage_route"] >= 0.90
    assert gate_result["coverage_accuse"] >= 0.98
