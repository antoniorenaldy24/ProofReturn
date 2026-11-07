"""Remediation tests for Task T10: Integration and contract tests, plus Audit Mutants M01-M11.

Requirements:
1. CI job with a Postgres service container (verified in .github/workflows/ci.yml).
2. Contract tests: for 3 fixed scenarios (TRUSTED declared B, ESTABLISHED declared A, NEW),
   the API response values (lane, X, R0 tranche, holdback) equal decide_release() for the same inputs.
3. Browser UI check: state that no browser DOM exists after J-14; controllers tested via node --test.
4. Re-run the audit's mutants M01-M11 against the suite and verify each mutant is killed.
"""

from __future__ import annotations

from fractions import Fraction
import math
import secrets
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.db.models import (
    Merchant,
    Order,
    OrderItem,
    Passport,
    Return,
    ShopperAccount,
)
from backend.domain.audit_commitment import (
    create_audit_commitment,
    reveal_and_draw_audit,
)
from backend.domain.policy import PolicyConfig
from backend.domain.return_state import (
    InvalidStateTransitionError,
    ReturnEntity,
    ReturnStateMachine,
)
from backend.domain.trust import (
    TrustProfile,
    compute_account_exposure_cap_minor,
    evaluate_tier_promotion,
)
from backend.payments.ledger import (
    IdempotencyConflictError,
    OverRefundError,
    RefundLedger,
)
from backend.payments.webhooks import WebhookProcessor
from backend.policy_engine.keep_offer import KeepOfferInput, compute_posted_keep_offer
from backend.policy_engine.misdeclaration import evaluate_misdeclaration
from backend.policy_engine.release import (
    CalibrationInput,
    GapCalibration,
    ReleaseInput,
    compute_x_max_k,
    decide_release,
)
from backend.policy_engine.settlement import SettlementInput, settle_return
from sim.fmap import _illustrative_calib


# ==============================================================================
# Requirement 2: Contract Tests for 3 Fixed Scenarios
# ==============================================================================


@pytest.mark.req("AUD-01", "AUD-36", "FR-60", "FR-87")
def test_contract_scenario_1_trusted_declared_b() -> None:
    """Scenario 1: TRUSTED account declaring Grade B.

    API response values (lane, X, R0 tranche, holdback) must equal decide_release().
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)
    admin_tok = mint_staff_token("merch_a", "MERCHANT_ADMIN")

    price_minor = 38000
    declared_grade = "B"
    tier = "TRUSTED"
    has_origin_passport = True

    policy = PolicyConfig.default_us()
    calib = _illustrative_calib(declared_grade)
    inp = ReleaseInput(
        price_minor=price_minor,
        declared_grade=declared_grade,
        tier=tier,
        has_origin_passport=has_origin_passport,
        account_cap_remaining_minor=100000,
        merchant_cap_remaining_minor=500000,
    )
    expected = decide_release(inp, policy, calib)

    # 1. Verify via POST /v1/simulate
    resp_sim = client.post(
        "/v1/simulate",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={
            "price_minor": price_minor,
            "declared_grade": declared_grade,
            "tier": tier,
            "has_origin_passport": has_origin_passport,
        },
    )
    assert resp_sim.status_code == 200
    sim_data = resp_sim.json()
    assert sim_data["lane"] == expected.lane
    assert sim_data["x_released_minor"] == expected.x_released_minor
    assert sim_data["r0_tranche_minor"] == expected.x_released_minor
    assert sim_data["holdback_minor"] == expected.holdback_minor

    # 2. Verify via POST /v1/returns/{return_id}/evidence
    repo = app.state.repository
    order_id = f"ord_contract_trusted_{uuid.uuid4().hex[:6]}"
    ret_id = f"ret_contract_trusted_{uuid.uuid4().hex[:6]}"
    shopper_id = f"shop_contract_trusted_{uuid.uuid4().hex[:6]}"
    pass_id = f"pass_contract_trusted_{uuid.uuid4().hex[:6]}"

    with repo.get_session() as s:
        s.add(
            ShopperAccount(
                account_id=shopper_id,
                email="trusted_shopper@example.com",
                trust_tier="TRUSTED",
                clean_counter_verified_returns=10,
                account_age_days=180,
            )
        )
        s.add(
            Order(
                order_id=order_id,
                merchant_id="merch_a",
                account_id=shopper_id,
                policy_version="pol_v1_us_ca",
                currency="USD",
                capture_id=f"PAYPAL-CAP-{order_id}",
                capture_amount_minor=price_minor,
                status="CAPTURED",
            )
        )
        s.add(Passport(passport_id=pass_id, merchant_id="merch_a", serial_number="SN-TRUSTED-1", current_owner_ref=shopper_id))
        s.add(OrderItem(order_item_id=f"oi_{order_id}", order_id=order_id, sku="SKU-T1", price_minor=price_minor, passport_id=pass_id))
        s.add(
            Return(
                return_id=ret_id,
                order_id=order_id,
                order_item_id=f"oi_{order_id}",
                merchant_id="merch_a",
                account_id=shopper_id,
                state="DECLARED",
                declared_grade=declared_grade,
                challenge_nonce="NONCE-CONTRACT-T1",
                currency="USD",
            )
        )
        s.commit()

    shopper_tok = mint_shopper_token(order_id, shopper_id)
    resp_ev = client.post(
        f"/v1/returns/{ret_id}/evidence",
        headers={"Authorization": f"Bearer {shopper_tok}"},
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": f"raw/{ret_id}/challenge.mp4",
            "sha256": "c" * 64,
            "challenge_step": 1,
            "faces_detected": 0,
            "client_blur_applied": False,
            "blur_latency_ms": 10.0,
            "text_in_media": "NONCE-CONTRACT-T1",
        },
    )
    assert resp_ev.status_code == 200
    ev_data = resp_ev.json()
    assert ev_data["lane"] == expected.lane
    assert ev_data["x_released_minor"] == expected.x_released_minor
    assert ev_data["r0_tranche_minor"] == expected.x_released_minor
    assert ev_data["holdback_minor"] == expected.holdback_minor


@pytest.mark.req("AUD-01", "AUD-36", "FR-60", "FR-87")
def test_contract_scenario_2_established_declared_a() -> None:
    """Scenario 2: ESTABLISHED account declaring Grade A.

    API response values (lane, X, R0 tranche, holdback) must equal decide_release().
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)
    admin_tok = mint_staff_token("merch_a", "MERCHANT_ADMIN")

    price_minor = 38000
    declared_grade = "A"
    tier = "ESTABLISHED"
    has_origin_passport = True

    policy = PolicyConfig.default_us()
    calib = _illustrative_calib(declared_grade)
    inp = ReleaseInput(
        price_minor=price_minor,
        declared_grade=declared_grade,
        tier=tier,
        has_origin_passport=has_origin_passport,
        account_cap_remaining_minor=50000,
        merchant_cap_remaining_minor=500000,
    )
    expected = decide_release(inp, policy, calib)

    # 1. Verify via POST /v1/simulate
    resp_sim = client.post(
        "/v1/simulate",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={
            "price_minor": price_minor,
            "declared_grade": declared_grade,
            "tier": tier,
            "has_origin_passport": has_origin_passport,
        },
    )
    assert resp_sim.status_code == 200
    sim_data = resp_sim.json()
    assert sim_data["lane"] == expected.lane
    assert sim_data["x_released_minor"] == expected.x_released_minor
    assert sim_data["r0_tranche_minor"] == expected.x_released_minor
    assert sim_data["holdback_minor"] == expected.holdback_minor

    # 2. Verify via POST /v1/returns/{return_id}/evidence
    repo = app.state.repository
    order_id = f"ord_contract_est_{uuid.uuid4().hex[:6]}"
    ret_id = f"ret_contract_est_{uuid.uuid4().hex[:6]}"
    shopper_id = f"shop_contract_est_{uuid.uuid4().hex[:6]}"
    pass_id = f"pass_contract_est_{uuid.uuid4().hex[:6]}"

    with repo.get_session() as s:
        s.add(
            ShopperAccount(
                account_id=shopper_id,
                email="est_shopper@example.com",
                trust_tier="ESTABLISHED",
                clean_counter_verified_returns=4,
                account_age_days=60,
            )
        )
        s.add(
            Order(
                order_id=order_id,
                merchant_id="merch_a",
                account_id=shopper_id,
                policy_version="pol_v1_us_ca",
                currency="USD",
                capture_id=f"PAYPAL-CAP-{order_id}",
                capture_amount_minor=price_minor,
                status="CAPTURED",
            )
        )
        s.add(Passport(passport_id=pass_id, merchant_id="merch_a", serial_number="SN-EST-1", current_owner_ref=shopper_id))
        s.add(OrderItem(order_item_id=f"oi_{order_id}", order_id=order_id, sku="SKU-E1", price_minor=price_minor, passport_id=pass_id))
        s.add(
            Return(
                return_id=ret_id,
                order_id=order_id,
                order_item_id=f"oi_{order_id}",
                merchant_id="merch_a",
                account_id=shopper_id,
                state="DECLARED",
                declared_grade=declared_grade,
                challenge_nonce="NONCE-CONTRACT-E1",
                currency="USD",
            )
        )
        s.commit()

    shopper_tok = mint_shopper_token(order_id, shopper_id)
    resp_ev = client.post(
        f"/v1/returns/{ret_id}/evidence",
        headers={"Authorization": f"Bearer {shopper_tok}"},
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": f"raw/{ret_id}/challenge.mp4",
            "sha256": "d" * 64,
            "challenge_step": 1,
            "faces_detected": 0,
            "client_blur_applied": False,
            "blur_latency_ms": 10.0,
            "text_in_media": "NONCE-CONTRACT-E1",
        },
    )
    assert resp_ev.status_code == 200
    ev_data = resp_ev.json()
    assert ev_data["lane"] == expected.lane
    assert ev_data["x_released_minor"] == expected.x_released_minor
    assert ev_data["r0_tranche_minor"] == expected.x_released_minor
    assert ev_data["holdback_minor"] == expected.holdback_minor


@pytest.mark.req("AUD-01", "AUD-36", "FR-60", "FR-87")
def test_contract_scenario_3_new_declared_b() -> None:
    """Scenario 3: NEW account declaring Grade B.

    API response values (lane, X, R0 tranche, holdback) must equal decide_release().
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)
    admin_tok = mint_staff_token("merch_a", "MERCHANT_ADMIN")

    price_minor = 38000
    declared_grade = "B"
    tier = "NEW"
    has_origin_passport = True

    policy = PolicyConfig.default_us()
    calib = _illustrative_calib(declared_grade)
    inp = ReleaseInput(
        price_minor=price_minor,
        declared_grade=declared_grade,
        tier=tier,
        has_origin_passport=has_origin_passport,
        account_cap_remaining_minor=0,
        merchant_cap_remaining_minor=500000,
    )
    expected = decide_release(inp, policy, calib)

    # 1. Verify via POST /v1/simulate
    resp_sim = client.post(
        "/v1/simulate",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={
            "price_minor": price_minor,
            "declared_grade": declared_grade,
            "tier": tier,
            "has_origin_passport": has_origin_passport,
        },
    )
    assert resp_sim.status_code == 200
    sim_data = resp_sim.json()
    assert sim_data["lane"] == expected.lane
    assert sim_data["x_released_minor"] == expected.x_released_minor
    assert sim_data["r0_tranche_minor"] == expected.x_released_minor
    assert sim_data["holdback_minor"] == expected.holdback_minor

    # 2. Verify via POST /v1/returns/{return_id}/evidence
    repo = app.state.repository
    order_id = f"ord_contract_new_{uuid.uuid4().hex[:6]}"
    ret_id = f"ret_contract_new_{uuid.uuid4().hex[:6]}"
    shopper_id = f"shop_contract_new_{uuid.uuid4().hex[:6]}"
    pass_id = f"pass_contract_new_{uuid.uuid4().hex[:6]}"

    with repo.get_session() as s:
        s.add(
            ShopperAccount(
                account_id=shopper_id,
                email="new_shopper@example.com",
                trust_tier="NEW",
                clean_counter_verified_returns=0,
                account_age_days=5,
            )
        )
        s.add(
            Order(
                order_id=order_id,
                merchant_id="merch_a",
                account_id=shopper_id,
                policy_version="pol_v1_us_ca",
                currency="USD",
                capture_id=f"PAYPAL-CAP-{order_id}",
                capture_amount_minor=price_minor,
                status="CAPTURED",
            )
        )
        s.add(Passport(passport_id=pass_id, merchant_id="merch_a", serial_number="SN-NEW-1", current_owner_ref=shopper_id))
        s.add(OrderItem(order_item_id=f"oi_{order_id}", order_id=order_id, sku="SKU-N1", price_minor=price_minor, passport_id=pass_id))
        s.add(
            Return(
                return_id=ret_id,
                order_id=order_id,
                order_item_id=f"oi_{order_id}",
                merchant_id="merch_a",
                account_id=shopper_id,
                state="DECLARED",
                declared_grade=declared_grade,
                challenge_nonce="NONCE-CONTRACT-N1",
                currency="USD",
            )
        )
        s.commit()

    shopper_tok = mint_shopper_token(order_id, shopper_id)
    resp_ev = client.post(
        f"/v1/returns/{ret_id}/evidence",
        headers={"Authorization": f"Bearer {shopper_tok}"},
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": f"raw/{ret_id}/challenge.mp4",
            "sha256": "e" * 64,
            "challenge_step": 1,
            "faces_detected": 0,
            "client_blur_applied": False,
            "blur_latency_ms": 10.0,
            "text_in_media": "NONCE-CONTRACT-N1",
        },
    )
    assert resp_ev.status_code == 200
    ev_data = resp_ev.json()
    assert ev_data["lane"] == expected.lane
    assert ev_data["x_released_minor"] == expected.x_released_minor
    assert ev_data["r0_tranche_minor"] == expected.x_released_minor
    assert ev_data["holdback_minor"] == expected.holdback_minor


# ==============================================================================
# Requirement 4: Verification and Proof of Audit Mutants M01 to M11 Killed
# ==============================================================================


@pytest.mark.req("AUD-36", "INV-01")
def test_mutant_m01_over_refund_ledger_check_killed() -> None:
    """Mutant M01: Cek over-refund ledger dimatikan (INV-01).

    Kill proof: Attempting to plan or commit a refund exceeding the capture amount
    must raise OverRefundError and be rejected with RFC 9457 HTTP 409 REFUND_LIMIT_EXCEEDED.
    """
    ledger = RefundLedger()
    ledger.register_order(
        order_id="ord_m01",
        merchant_id="merch_1",
        capture_id="cap_m01",
        capture_amount_minor=10000,
    )
    # 1. First tranche: $80.00
    act1 = ledger.plan_refund_action(
        order_id="ord_m01",
        merchant_id="merch_1",
        capture_id="cap_m01",
        decision_id="dec_m01_1",
        tranche="R0",
        amount_minor=8000,
    )
    assert act1.status == "PLANNED"

    # 2. Second tranche: $30.00 would make total $110.00 > $100.00 capture -> OverRefundError
    with pytest.raises(OverRefundError) as exc_info:
        ledger.plan_refund_action(
            order_id="ord_m01",
            merchant_id="merch_1",
            capture_id="cap_m01",
            decision_id="dec_m01_2",
            tranche="R1",
            amount_minor=3000,
        )
    assert "INV-01 violation" in str(exc_info.value)


@pytest.mark.req("AUD-18", "AUD-36")
def test_mutant_m02_replan_ledger_conflict_killed() -> None:
    """Mutant M02: Konflik re-plan ledger dimatikan (AUD-18).

    Kill proof: Re-planning an existing refund action with a differing amount
    must raise IdempotencyConflictError, killing the mutant that silently overwrites it.
    """
    ledger = RefundLedger()
    ledger.register_order(
        order_id="ord_m02",
        merchant_id="merch_1",
        capture_id="cap_m02",
        capture_amount_minor=20000,
    )
    # Plan R0 for $50.00
    ledger.plan_refund_action(
        order_id="ord_m02",
        merchant_id="merch_1",
        capture_id="cap_m02",
        decision_id="dec_m02",
        tranche="R0",
        amount_minor=5000,
    )
    # Re-planning with SAME amount returns idempotent existing action
    idem = ledger.plan_refund_action(
        order_id="ord_m02",
        merchant_id="merch_1",
        capture_id="cap_m02",
        decision_id="dec_m02",
        tranche="R0",
        amount_minor=5000,
    )
    assert idem.amount_minor == 5000

    # Re-planning with DIFFERENT amount ($60.00) must raise IdempotencyConflictError
    with pytest.raises(IdempotencyConflictError) as exc_info:
        ledger.plan_refund_action(
            order_id="ord_m02",
            merchant_id="merch_1",
            capture_id="cap_m02",
            decision_id="dec_m02",
            tranche="R0",
            amount_minor=6000,
        )
    assert "AUD-18 idempotency conflict" in str(exc_info.value)


@pytest.mark.req("AUD-12", "AUD-36", "RV-14")
def test_mutant_m03_webhook_deduplication_killed() -> None:
    """Mutant M03: Dedupe webhook dimatikan.

    Kill proof: Submitting the same webhook event_id a second time must return
    duplicate=True and bypass state mutation.
    """
    ledger = RefundLedger()
    ledger.register_order(
        order_id="ord_m03",
        merchant_id="merch_1",
        capture_id="cap_m03",
        capture_amount_minor=15000,
    )
    processor = WebhookProcessor(ledger=ledger)

    event_payload = {
        "id": "wh_evt_m03_001",
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "order_id": "ord_m03",
    }
    # 1. First delivery
    res1 = processor.process_webhook(
        event_id="wh_evt_m03_001",
        event_type="CUSTOMER.DISPUTE.CREATED",
        signature_valid=True,
        payload=event_payload,
    )
    assert res1["status_code"] == 200
    assert res1["duplicate"] is False
    assert ledger.is_order_frozen("ord_m03") is True

    # 2. Duplicate delivery must be detected and marked duplicate=True
    res2 = processor.process_webhook(
        event_id="wh_evt_m03_001",
        event_type="CUSTOMER.DISPUTE.CREATED",
        signature_valid=True,
        payload=event_payload,
    )
    assert res2["status_code"] == 200
    assert res2["duplicate"] is True


@pytest.mark.req("AUD-36", "FR-89", "INV-18")
def test_mutant_m04_safety_margin_mu_in_x_max_killed() -> None:
    """Mutant M04: Margin mu (I_delta) dihapus dari X_max (FR-89).

    Kill proof: With safety margin mu > 0, compute_x_max_k must be strictly smaller
    than without margin (mu = 0), ensuring expected attacker gain satisfies G_k <= -m_k.
    """
    price_minor = 38000
    r_declared = Fraction(95, 100)
    r_true = Fraction(50, 100)
    d_k = Fraction(40, 100)
    p = Fraction(8, 100)
    l_minor = 5000
    mu = Fraction(5, 100)

    # compute with safety margin mu = 0.05
    x_with_margin = compute_x_max_k(
        price_minor=price_minor,
        r_declared=r_declared,
        r_true=r_true,
        d_k=d_k,
        p=p,
        l_minor=l_minor,
        mu=mu,
    )
    # compute with mutant (mu = 0)
    x_without_margin = compute_x_max_k(
        price_minor=price_minor,
        r_declared=r_declared,
        r_true=r_true,
        d_k=d_k,
        p=p,
        l_minor=l_minor,
        mu=Fraction(0, 1),
    )
    # The mutant allows more money pre-check-in, violating the required safety margin
    assert x_with_margin < x_without_margin


@pytest.mark.req("AUD-36", "FR-60")
def test_mutant_m05_standard_routing_on_infeasible_p_killed() -> None:
    """Mutant M05: Rute STANDARD saat p > p_max dimatikan (FR-60).

    Kill proof: When fraud leakage cannot be controlled within [p_min, p_max],
    the engine must route to STANDARD with x_released_minor = 0.
    """
    policy = PolicyConfig.default_us()
    calib = CalibrationInput(
        declared_grade="A",
        gross_gaps=[
            GapCalibration(
                true_grade="D",
                q=Fraction(0, 1),
                d=Fraction(1, 1000),  # very small detection probability requires p > 1.0
            )
        ]
    )
    inp = ReleaseInput(
        price_minor=100000,
        declared_grade="A",
        tier="NEW",
        has_origin_passport=True,
    )
    decision = decide_release(inp, policy, calib)
    assert decision.lane == "STANDARD"
    assert decision.timing == "STANDARD"
    assert decision.x_released_minor == 0
    assert decision.binding_constraint == "FLOOR_OR_LEAKAGE_INFEASIBLE"


@pytest.mark.req("AUD-08", "AUD-36", "FR-73")
def test_mutant_m06_gross_escalation_without_reviewer_killed() -> None:
    """Mutant M06: Eskalasi gross tanpa reviewer dimatikan (AUD-08).

    Kill proof: Unreviewed gross mismatch (human_confirmed_gross=False) must
    yield status='ESCALATED', is_escalated=True, and freeze remaining tranches.
    """
    policy = PolicyConfig.default_us()
    f_minor = policy.compute_f_minor(38000)
    sinp = SettlementInput(
        price_minor=38000,
        capture_amount_minor=38000,
        declared_grade="A",
        verified_grade="D",
        x_released_minor=15000,
        holdback_minor=7600,
        f_minor=f_minor,
        human_confirmed_gross=False,  # Unreviewed!
        excluded_at_alpha_accuse=True,
        has_merchant_evidence=True,
    )
    res = settle_return(sinp, policy)
    assert res.status == "ESCALATED"
    assert res.is_escalated is True
    assert res.additional_refund_minor == 0
    assert res.status_affected is False


@pytest.mark.req("AUD-36", "INV-10")
def test_mutant_m07_human_confirmation_and_conformal_exclusion_killed() -> None:
    """Mutant M07: Syarat konfirmasi manusia INV-10 dihapus.

    Kill proof: Gross mismatch without conformal exclusion cannot charge misdeclaration fee
    nor restrict shopper account status (INV-10).
    """
    policy = PolicyConfig.default_us()
    f_minor = policy.compute_f_minor(38000)
    sinp = SettlementInput(
        price_minor=38000,
        capture_amount_minor=38000,
        declared_grade="A",
        verified_grade="D",
        x_released_minor=15000,
        holdback_minor=7600,
        f_minor=f_minor,
        human_confirmed_gross=True,
        excluded_at_alpha_accuse=False,  # Conformal exclusion NOT established
        has_merchant_evidence=True,
    )
    res = settle_return(sinp, policy)
    assert res.f_charged_minor == 0
    assert res.status_affected is False
    assert res.new_tier_override is None


@pytest.mark.req("AUD-13", "AUD-36", "FR-91")
def test_mutant_m08_new_cannot_leapfrog_to_trusted_killed() -> None:
    """Mutant M08: Promosi NEW langsung ke TRUSTED (AUD-13).

    Kill proof: High volume account in NEW tier can promote at most to ESTABLISHED,
    never leapfrogging directly to TRUSTED.
    """
    profile = TrustProfile(
        tier="NEW",
        clean_count=50,
        cumulative_verified_value_minor=5000000,
        largest_clean_value_minor=200000,
        account_age_days=365,
    )
    promoted = evaluate_tier_promotion(profile)
    assert promoted == "ESTABLISHED"
    assert promoted != "TRUSTED"


@pytest.mark.req("AUD-36", "INV-04")
def test_mutant_m09_tsm01_guards_enforced_killed() -> None:
    """Mutant M09: Guard T-SM01 state machine dimatikan (INV-04).

    Kill proof: Calling transition T-SM01 with any guard False raises InvalidStateTransitionError.
    """
    sm = ReturnStateMachine()
    ent = ReturnEntity(return_id="ret_m09", order_id="ord_m09", state="REQUESTED")

    with pytest.raises(InvalidStateTransitionError):
        sm.apply(
            ent,
            "SUBMIT_DECLARATION",
            within_window=False,
            actor_authorized=True,
            terms_consent_recorded=True,
        )

    with pytest.raises(InvalidStateTransitionError):
        sm.apply(
            ent,
            "SUBMIT_DECLARATION",
            within_window=True,
            actor_authorized=False,
            terms_consent_recorded=True,
        )

    with pytest.raises(InvalidStateTransitionError):
        sm.apply(
            ent,
            "SUBMIT_DECLARATION",
            within_window=True,
            actor_authorized=True,
            terms_consent_recorded=False,
        )


@pytest.mark.req("AUD-36", "FR-37", "FR-78")
def test_mutant_m10_keep_offer_bound_killed() -> None:
    """Mutant M10: Batas (1 - theta_h) * k_max keep-offer dihapus (FR-37).

    Kill proof: Posted keep-offer price must be strictly <= (1 - theta_h) * k_max
    and <= refund_owed_minor.
    """
    policy = PolicyConfig.default_us()
    inp = KeepOfferInput(
        refund_owed_minor=10000,
        reverse_shipping_minor=1500,
        handling_cost_minor=500,
        recovery_lower_bound_minor=2000,
        tier="TRUSTED",
        intake_passed=True,
    )
    dec = compute_posted_keep_offer(inp, policy)
    assert dec.eligible is True
    assert dec.posted_price_minor is not None

    theta_h = policy.theta_h_fraction()
    k_max = inp.refund_owed_minor + inp.reverse_shipping_minor + inp.handling_cost_minor - inp.recovery_lower_bound_minor
    upper_bound = int((Fraction(1, 1) - theta_h) * Fraction(k_max))
    assert dec.posted_price_minor <= upper_bound
    assert dec.posted_price_minor <= inp.refund_owed_minor


@pytest.mark.req("AUD-36", "FR-95", "INV-16")
def test_mutant_m11_audit_selection_direction_killed() -> None:
    """Mutant M11: Arah seleksi audit dibalik (FR-95).

    Kill proof: Audit selection condition is selected iff u < p.
    If the operator is inverted (selected iff u > p), this assertion immediately fails.
    """
    p_frac = Fraction(8, 100)
    seed = secrets.token_bytes(32)
    commitment = create_audit_commitment(seed, "ret_m11", p_frac)

    # Over 500 draws, verify each individual draw evaluates selected == (u < p)
    for i in range(500):
        reveal = reveal_and_draw_audit(commitment, seed, f"nonce_{i}")
        assert reveal.selected == (reveal.u < p_frac)
        # Verify mutant check: reveal.selected must NOT equal (reveal.u > p_frac)
        if reveal.u != p_frac:
            assert reveal.selected != (reveal.u > p_frac)
