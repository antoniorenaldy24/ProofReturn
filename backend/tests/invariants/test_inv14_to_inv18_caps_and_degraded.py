"""Invariant tests for INV-14, INV-15, INV-16, INV-17, INV-18 through the API (SSOT Section 29.1).

INV-14: Pre-checkin release never exceeds X_max, account cap, or merchant cap.
INV-15: Adjacent-grade difference (A vs B) never penalized (f_charged_minor == 0, no tier restriction).
INV-16: Audit probability & commitment fixed before shipping; seed hidden before check-in;
        mismatched seed reveal rejected.
INV-17: Intake routing, cancellation, or re-filed returns incur no penalty; re-filed returns never
        receive pre-checkin money (r0_tranche_minor == 0).
INV-18: Degraded modes (FB-xx) never increase release or advance timing.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Any
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.db.models import Merchant, Return
from backend.domain.audit_commitment import AuditCommitment, reveal_and_draw_audit
from backend.domain.return_state import InvalidStateTransitionError, ReturnEntity, ReturnStateMachine


def test_inv14_pre_checkin_release_never_exceeds_merchant_exposure_cap(reset_db: Any) -> None:
    """INV-14 NEGATIVE: When merchant instant exposure cap is exceeded, pre-checkin release

    must be BLOCKED (exposure_cap_ok=False) and fail closed with 409 INVALID_STATE_TRANSITION.
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    tok_shopper = mint_shopper_token("ord_demo_1", "shopper_1")

    # Set merchant exposure to cap limit so outstanding + r0 > cap
    with reset_db.get_session() as session:
        merch = session.get(Merchant, "merch_a")
        assert merch is not None
        orig_exposure = merch.outstanding_instant_exposure_minor
        merch.outstanding_instant_exposure_minor = merch.instant_exposure_cap_minor
        session.add(merch)

        ret = session.get(Return, "ret_demo_1")
        assert ret is not None
        orig_ret_state = ret.state
        orig_ret_r0 = ret.r0_tranche_minor
        orig_ret_lane = ret.lane
        ret.state = "ASSESSED"
        ret.r0_tranche_minor = 21249
        ret.lane = "FAST"
        session.add(ret)
        session.commit()

    try:
        # Attempting dropoff when exposure cap is exhausted must fail closed
        r_drop = client.post(
            "/v1/returns/ret_demo_1/dropoff",
            headers={"Authorization": f"Bearer {tok_shopper}"},
            json={
                "seal_nonce": "SEAL-INV14-TEST",
                "carrier_tracking_number": "1Z999INV14TEST",
            },
        )
        assert r_drop.status_code == 409
        err = r_drop.json()
        assert err["code"] == "INVALID_STATE_TRANSITION"
    finally:
        with reset_db.get_session() as session:
            m = session.get(Merchant, "merch_a")
            if m:
                m.outstanding_instant_exposure_minor = orig_exposure
                session.add(m)
            r = session.get(Return, "ret_demo_1")
            if r:
                r.state = orig_ret_state
                r.r0_tranche_minor = orig_ret_r0
                r.lane = orig_ret_lane
                session.add(r)
            session.commit()


def test_inv15_adjacent_grade_difference_never_penalized(reset_db: Any) -> None:
    """INV-15: Adjacent-grade difference (e.g. A vs B or B vs C) is never penalized.

    f_charged_minor must be 0, status_affected must be False, and no penalty fee is charged.
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    tok_reviewer = mint_staff_token("merch_a", "REVIEWER", sub="rev_inv15")

    # ret_demo_1 has declared_grade = "B". Settle it at adjacent grade "C".
    r_settle = client.post(
        "/v1/review/ret_demo_1/decision",
        headers={"Authorization": f"Bearer {tok_reviewer}", "Idempotency-Key": "ik-inv15-adj"},
        json={"outcome": "DOWNGRADED", "verified_grade": "C", "notes": "Adjacent grade inspection"},
    )
    assert r_settle.status_code == 200
    res = r_settle.json()
    assert res.get("f_charged_minor") == 0
    assert res.get("status_affected") is False


def test_inv16_mismatched_audit_seed_reveal_rejected(reset_db: Any) -> None:
    """INV-16 NEGATIVE: Seed reveal that does not match pre-committed hash c must be REJECTED."""
    from fractions import Fraction

    seed_platform = secrets.token_bytes(32)
    return_id = "ret_inv16_test"
    valid_c = hashlib.sha256(seed_platform + b"||" + return_id.encode("utf-8")).hexdigest()

    record = AuditCommitment(
        return_id=return_id,
        commitment=valid_c,
        p=Fraction(1, 20),
    )
    reveal = reveal_and_draw_audit(
        commitment_record=record,
        seed_platform=seed_platform,
        nonce_shopper="nonce_123",
    )
    assert reveal.verify_commitment(return_id) is True

    # Attempt reveal with tampered/mismatched seed
    forged_seed = secrets.token_bytes(32)
    try:
        reveal_and_draw_audit(
            commitment_record=record,
            seed_platform=forged_seed,
            nonce_shopper="nonce_123",
        )
        assert False, "Must raise ValueError on mismatched seed reveal (INV-16)."
    except ValueError as exc:
        assert "does not match pre-committed hash" in str(exc)


def test_inv17_refiled_returns_never_receive_pre_checkin_money(reset_db: Any) -> None:
    """INV-17 NEGATIVE: Re-filed returns must force STANDARD lane (r0_tranche_minor == 0).

    State machine forbids scheduling a pre-checkin tranche for refiled returns.
    """
    sm = ReturnStateMachine()
    refiled_entity = ReturnEntity(
        return_id="ret_inv17_refile",
        order_id="ord_demo_1",
        state="ASSESSED",
        lane="FAST",
        timing="R0",
        x_minor=10000,
        refiled=True,
    )

    # Attempting to approve pre-checkin tranche on refiled return MUST raise InvalidStateTransitionError
    try:
        sm.apply(refiled_entity, "APPROVE_RETURN", exposure_cap_ok=True)
        assert False, "Refiled return must NEVER be approved with x_minor > 0 or R0 timing (INV-17)."
    except InvalidStateTransitionError as exc:
        assert "Refiled return cannot receive pre-check-in tranche" in str(exc)


def test_inv18_degraded_modes_never_increase_release_or_advance_timing(reset_db: Any) -> None:
    """INV-18 NEGATIVE: Degraded modes (e.g. offline AI model or fallback FB-xx)

    must NEVER increase release amount or advance timing. Forces STANDARD lane and R3 timing.
    """
    from backend.ai.pipeline.evaluator import assess_return_evidence

    # Evaluate evidence in offline/no-keys degraded mode
    res = assess_return_evidence(
        mode="judge",
        evidence_sha256="f" * 64,
        declared_grade="B",
        text_in_media="",
        has_live_model_keys=False,
    )
    # Asserts degraded mode forces STANDARD lane, no FAST release
    assert res.forced_lane == "STANDARD"
    assert "MANUAL" in res.replay_label
