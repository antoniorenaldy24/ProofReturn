"""Remediation Tahap 13: Guards from data, no keep-offer fallback, caps and tier in decisions (Task T6, RV-03, RV2-03, RV2-05)."""

from __future__ import annotations

import hashlib
import math
import secrets
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import SecretStr
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_agent_token, mint_shopper_token, mint_staff_token
from backend.config import ProofReturnSettings
from backend.db.models import Assessment, Order, Return, ReturnEvidence, ShopperAccount
from backend.db.repository import DatabaseRepository
from backend.domain.audit_commitment import (
    AuditCommitment,
    create_audit_commitment,
    reveal_and_draw_audit,
)
from backend.domain.return_state import (
    InvalidStateTransitionError,
    ReturnEntity,
    ReturnStateMachine,
)

VALID_BOOTSTRAP_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
VALID_WEBHOOK_SECRET = "webhooksecret0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture
def test_repo(tmp_path: Path) -> DatabaseRepository:
    db_file = tmp_path / "test_t6.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)
    repo.seed_demo_data()
    return repo


@pytest.fixture
def demo_settings() -> ProofReturnSettings:
    return ProofReturnSettings(
        demo_mode=True,
        demo_bootstrap_key=SecretStr(VALID_BOOTSTRAP_KEY),
        demo_webhook_secret=SecretStr(VALID_WEBHOOK_SECRET),
    )


def test_state_machine_rejects_tsm01_when_any_guard_false() -> None:
    """T-SM01: SUBMIT_DECLARATION requires within_window, authorized, and consent_recorded."""
    sm = ReturnStateMachine()

    # 1. within_window is False
    ent1 = ReturnEntity(return_id="r1", order_id="o1", state="REQUESTED")
    with pytest.raises(InvalidStateTransitionError, match="T-SM01"):
        sm.apply(ent1, "SUBMIT_DECLARATION", within_window=False, authorized=True, consent_recorded=True)

    # 2. authorized is False
    ent2 = ReturnEntity(return_id="r2", order_id="o2", state="REQUESTED")
    with pytest.raises(InvalidStateTransitionError, match="T-SM01"):
        sm.apply(ent2, "SUBMIT_DECLARATION", within_window=True, authorized=False, consent_recorded=True)

    # 3. consent_recorded is False
    ent3 = ReturnEntity(return_id="r3", order_id="o3", state="REQUESTED")
    with pytest.raises(InvalidStateTransitionError, match="T-SM01"):
        sm.apply(ent3, "SUBMIT_DECLARATION", within_window=True, authorized=True, consent_recorded=False)


def test_guard_retakes_ok_false_returns_409(test_repo: DatabaseRepository, demo_settings: ProofReturnSettings) -> None:
    """Guard retakes_ok: stored retakes exceeding limit -> 409 INVALID_STATE_TRANSITION."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    ret = test_repo.get_return("ret_demo_1")
    assert ret is not None
    ret.state = "DECLARED"
    ret.retake_count = 5  # Exceeds max retakes limit (FR-66)
    test_repo.save_return(ret)

    token = mint_shopper_token("ord_demo_1", "shopper_1")
    resp = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "ik-t13-ev-retakes"},
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": "raw/ret_demo_1/challenge.mp4",
            "sha256": "a" * 64,
            "challenge_step": 1,
            "faces_detected": 0,
            "client_blur_applied": False,
            "blur_latency_ms": 10.0,
        },
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "INVALID_STATE_TRANSITION"


def test_guard_challenge_valid_false_returns_409(test_repo: DatabaseRepository, demo_settings: ProofReturnSettings) -> None:
    """Guard challenge_valid: stored challenge nonce does not match media text -> 409 INVALID_STATE_TRANSITION."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    ret = test_repo.get_return("ret_demo_1")
    assert ret is not None
    ret.state = "DECLARED"
    ret.retake_count = 0
    ret.challenge_nonce = "NONCE-CORRECT-1234"
    test_repo.save_return(ret)

    token = mint_shopper_token("ord_demo_1", "shopper_1")
    resp = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "ik-t13-ev-bad-nonce"},
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": "raw/ret_demo_1/challenge.mp4",
            "sha256": "a" * 64,
            "challenge_step": 1,
            "faces_detected": 0,
            "client_blur_applied": False,
            "blur_latency_ms": 10.0,
            "text_in_media": "WRONG-NONCE-CODE",
        },
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "INVALID_STATE_TRANSITION"

    # RV4-02: Partial nonce fragments must also be rejected with 409 (never accept substrings of stored nonce)
    for frag in ["NONCE", "CORRECT", "1234", "7", "-", "N"]:
        r_frag = client.post(
            "/v1/returns/ret_demo_1/evidence",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": f"ik-t13-ev-frag-{frag}"},
            json={
                "kind": "VIDEO_CHALLENGE",
                "object_key": "raw/ret_demo_1/challenge.mp4",
                "sha256": "a" * 64,
                "challenge_step": 1,
                "faces_detected": 0,
                "client_blur_applied": False,
                "blur_latency_ms": 10.0,
                "text_in_media": frag,
            },
        )
        assert r_frag.status_code == 409, f"Fragment '{frag}' should be rejected with 409"
        assert r_frag.json()["code"] == "INVALID_STATE_TRANSITION"


def test_guard_eligible_false_returns_409() -> None:
    """Guard eligible: OFFER_KEEP when eligible=False -> InvalidStateTransitionError."""
    sm = ReturnStateMachine()
    ent = ReturnEntity(return_id="r_el", order_id="o_el", state="ASSESSED")
    with pytest.raises(InvalidStateTransitionError, match="ineligible"):
        sm.apply(ent, "OFFER_KEEP", eligible=False)


def test_guard_not_expired_false_returns_409() -> None:
    """Guard not_expired: ACCEPT_KEEP_OFFER when not_expired=False -> InvalidStateTransitionError."""
    sm = ReturnStateMachine()
    ent = ReturnEntity(return_id="r_exp", order_id="o_exp", state="KEEP_OFFERED")
    with pytest.raises(InvalidStateTransitionError, match="not_expired"):
        sm.apply(ent, "ACCEPT_KEEP_OFFER", not_expired=False)


def test_guard_seal_nonce_matches_false_returns_409(test_repo: DatabaseRepository, demo_settings: ProofReturnSettings) -> None:
    """Guard seal_nonce_matches: carrier scan seal nonce mismatch -> 409 INVALID_STATE_TRANSITION."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    ret = test_repo.get_return("ret_demo_1")
    assert ret is not None
    ret.state = "AWAITING_SHIPMENT"
    ret.seal_nonce_hash = hashlib.sha256(b"CORRECT-SEAL-NONCE").hexdigest()
    test_repo.save_return(ret)

    receiver_token = mint_staff_token(merchant_id="merch_a", role="RECEIVER", user_id="recv_01")
    resp = client.post(
        "/v1/carrier-events",
        headers={"Authorization": f"Bearer {receiver_token}"},
        json={"return_id": "ret_demo_1", "type": "CARRIER_FIRST_SCAN", "seal_nonce": "TAMPERED-SEAL-NONCE"},
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "INVALID_STATE_TRANSITION"


def test_guard_assessment_exists_false_returns_409() -> None:
    """Guard assessment_exists: FINISH_ASSESSMENT when assessment_exists=False -> InvalidStateTransitionError."""
    sm = ReturnStateMachine()
    ent = ReturnEntity(return_id="r_ass", order_id="o_ass", state="EVIDENCE_SUBMITTED")
    with pytest.raises(InvalidStateTransitionError, match="assessment_exists"):
        sm.apply(ent, "FINISH_ASSESSMENT", assessment_exists=False)


def test_agent_cannot_accept_keep_offer_before_assessment(test_repo: DatabaseRepository, demo_settings: ProofReturnSettings) -> None:
    """Keep-offer ACCEPT only from ASSESSED; from REQUESTED or DECLARED -> 409."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    # Return in DECLARED state
    ret = test_repo.get_return("ret_demo_1")
    assert ret is not None
    ret.state = "DECLARED"
    test_repo.save_return(ret)

    agent_token = mint_agent_token("agent_test", "ord_demo_1", "merch_a", scopes=["keep_offer"])
    resp = client.post(
        "/v1/returns/ret_demo_1/keep-offer/respond",
        headers={"Authorization": f"Bearer {agent_token}", "Idempotency-Key": "ik-t13-ko-agent"},
        json={"action": "ACCEPT"},
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "INVALID_STATE_TRANSITION"

    # Ensure return state is still DECLARED and no assessment was created
    updated_ret = test_repo.get_return("ret_demo_1")
    assert updated_ret is not None
    assert updated_ret.state == "DECLARED"


def test_ineligible_keep_offer_returns_404_and_no_refund(test_repo: DatabaseRepository, demo_settings: ProofReturnSettings) -> None:
    """If compute_posted_keep_offer returns no price -> GET and respond return 404 NO_KEEP_OFFER."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    # Create a shopper with NEW tier (not eligible for keep-offer: needs ESTABLISHED or TRUSTED)
    shopper = test_repo.get_shopper("shopper_2")
    if not shopper:
        shopper = ShopperAccount(account_id="shopper_2", trust_tier="NEW")
        test_repo.save_shopper(shopper)
    else:
        shopper.trust_tier = "NEW"
        test_repo.save_shopper(shopper)

    order = test_repo.get_order("ord_demo_2")
    if not order:
        order = Order(order_id="ord_demo_2", merchant_id="merch_a", account_id="shopper_2", policy_version="pol_v1_us_ca", capture_amount_minor=10000, capture_id="CAP-ORD-2")
        test_repo.save_order(order)

    ret = test_repo.get_return("ret_demo_new")
    if not ret:
        ret = Return(return_id="ret_demo_new", order_id="ord_demo_2", order_item_id="item_demo_new_1", merchant_id="merch_a", shopper_id="shopper_2", state="ASSESSED")
        test_repo.save_return(ret)
    else:
        ret.state = "ASSESSED"
        test_repo.save_return(ret)

    token = mint_shopper_token("ord_demo_2", "shopper_2")
    resp_get = client.get(
        "/v1/returns/ret_demo_new/keep-offer",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_get.status_code == 404
    assert resp_get.json()["code"] == "NO_KEEP_OFFER"

    resp_post = client.post(
        "/v1/returns/ret_demo_new/keep-offer/respond",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "ik-t13-ko-ineligible"},
        json={"action": "ACCEPT"},
    )
    assert resp_post.status_code == 404
    assert resp_post.json()["code"] == "NO_KEEP_OFFER"

    # Ensure no refund action was planned
    actions = test_repo.list_refund_actions_by_return("ret_demo_new")
    assert len(actions) == 0


def test_decide_release_receives_account_and_merchant_caps(test_repo: DatabaseRepository, demo_settings: ProofReturnSettings) -> None:
    """Compute tier and caps from DB: NEW account has account cap = 0, so X = 0 and timing R2."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    shopper = test_repo.get_shopper("shopper_2")
    if not shopper:
        shopper = ShopperAccount(account_id="shopper_2", trust_tier="NEW", clean_Counter_verified_returns=0, account_age_days=5)
        test_repo.save_shopper(shopper)
    else:
        shopper.trust_tier = "NEW"
        shopper.clean_Counter_verified_returns = 0
        shopper.account_age_days = 5
        test_repo.save_shopper(shopper)

    order = test_repo.get_order("ord_demo_2")
    if not order:
        order = Order(order_id="ord_demo_2", merchant_id="merch_a", account_id="shopper_2", policy_version="pol_v1_us_ca", capture_amount_minor=38000, capture_id="CAP-ORD-2")
        test_repo.save_order(order)
    else:
        order.capture_id = "CAP-ORD-2"
        test_repo.save_order(order)

    ret = test_repo.get_return("ret_demo_new")
    if not ret:
        ret = Return(return_id="ret_demo_new", order_id="ord_demo_2", order_item_id="item_demo_new_2", merchant_id="merch_a", shopper_id="shopper_2", state="DECLARED", declared_grade="B")
        test_repo.save_return(ret)
    else:
        ret.state = "DECLARED"
        ret.declared_grade = "B"
        test_repo.save_return(ret)

    token = mint_shopper_token("ord_demo_2", "shopper_2")
    resp = client.post(
        "/v1/returns/ret_demo_new/evidence",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "ik-t13-ev-new-tier"},
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": "raw/ret_demo_new/challenge.mp4",
            "sha256": "a" * 64,
            "challenge_step": 1,
            "faces_detected": 0,
            "client_blur_applied": False,
            "blur_latency_ms": 10.0,
        },
    )
    assert resp.status_code == 200
    ev_data = resp.json()
    assert ev_data["accepted"] is True
    assert ev_data["state"] == "ASSESSED"
    # NEW account has account_cap = 0, so X released must be 0!
    assert ev_data["r0_tranche_minor"] == 0


def test_audit_selection_direction_and_rate() -> None:
    """Audit selection: selected iff u < p; empirical rate within 3 standard errors of p over 20,000 draws."""
    p_frac = Fraction(8, 100)  # p = 0.08
    p_float = float(p_frac)
    n_draws = 20_000

    seed_platform = secrets.token_bytes(32)
    commitment = create_audit_commitment(seed_platform, "ret_audit_sim", p_frac)

    selected_count = 0
    for i in range(n_draws):
        nonce_shopper = f"shopper_nonce_{i}"
        reveal = reveal_and_draw_audit(commitment, seed_platform, nonce_shopper)
        # 1. Check exact direction: selected iff u < p
        assert reveal.selected == (reveal.u < p_frac)
        if reveal.selected:
            selected_count += 1

    empirical_p = selected_count / n_draws
    se = math.sqrt(p_float * (1.0 - p_float) / n_draws)
    # Empirical rate must be within 3 standard errors of p
    assert abs(empirical_p - p_float) <= 3.0 * se, (
        f"Empirical audit rate {empirical_p:.4f} outside 3 SE ({3*se:.4f}) of {p_float:.4f}"
    )
