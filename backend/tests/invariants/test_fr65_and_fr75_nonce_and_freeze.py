"""Invariant tests for FR-65 (challenge nonce verification) and FR-75 (dispute freeze) through the API.

FR-65: Challenge nonce verification (missing/mismatched nonce -> standard lane, CHALLENGE_NOT_VERIFIED, no FAST release).
FR-75: Dispute and capture reversal freeze blocks refund planning (409 ORDER_FROZEN) and outbox execution (BLOCKED_BY_DISPUTE).
"""

from __future__ import annotations

from typing import Any
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.db.models import Order, RefundAction, Return
from backend.payments.outbox import RefundOutboxExecutor


def test_fr65_missing_or_mismatched_nonce_routes_to_standard_lane(reset_db: Any) -> None:
    """FR-65 NEGATIVE: Submitting evidence without valid OCR challenge nonce

    must NOT trigger FAST release (r0_tranche_minor == 0) and must route to STANDARD lane
    with reason CHALLENGE_NOT_VERIFIED recorded in response.
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    tok_shopper = mint_shopper_token("ord_demo_1", "shopper_1")

    # 1. Declaration with FAST lane accepted
    r_decl = client.post(
        "/v1/returns/ret_demo_1/declaration",
        headers={"Authorization": f"Bearer {tok_shopper}"},
        json={
            "declared_grade": "B",
            "fast_lane_terms_accepted": True,
            "shopper_nonce": "shopper_nonce_fr65",
        },
    )
    assert r_decl.status_code == 200

    # 2. Submit evidence WITHOUT text_in_media (or with text that does not contain the nonce)
    r_ev = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {tok_shopper}", "Idempotency-Key": "ik-fr65-no-nonce"},
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": "raw/ret_demo_1/no_nonce.mp4",
            "sha256": "d" * 64,
            "challenge_step": 1,
            "text_in_media": "",  # Missing nonce!
            "faces_detected": 0,
            "client_blur_applied": False,
            "blur_latency_ms": 10.0,
        },
    )
    assert r_ev.status_code == 200
    ev_data = r_ev.json()

    # Invariant assertions: No FAST release, routed to STANDARD lane
    assert ev_data.get("r0_tranche_minor") == 0
    assert ev_data.get("lane") == "STANDARD"
    assert ev_data.get("reason") == "CHALLENGE_NOT_VERIFIED"


def test_fr75_dispute_freeze_blocks_refund_planning_with_409(reset_db: Any) -> None:
    """FR-75 NEGATIVE: An order frozen by dispute or chargeback blocks refund planning

    with 409 ORDER_FROZEN, and outbox execution marks actions BLOCKED_BY_DISPUTE.
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    tok_reviewer = mint_staff_token("merch_a", "REVIEWER", sub="rev_fr75")

    # Freeze order ord_demo_1 in database
    with reset_db.get_session() as session:
        order = session.get(Order, "ord_demo_1")
        assert order is not None
        order.frozen_by_dispute = True
        order.frozen_reason = "CUSTOMER.DISPUTE.CREATED"
        session.add(order)
        session.commit()

    try:
        # Attempt to settle or plan refund on frozen order -> 409 ORDER_FROZEN
        r_freeze = client.post(
            "/v1/review/ret_demo_escalated/decision",
            headers={"Authorization": f"Bearer {tok_reviewer}", "Idempotency-Key": "ik-fr75-freeze"},
            json={"outcome": "SETTLE_VERIFIED", "verified_grade": "D"},
        )
        assert r_freeze.status_code == 409
        err = r_freeze.json()
        assert err["code"] == "ORDER_FROZEN"

        # Outbox execution negative test: action on frozen order cannot execute
        with reset_db.get_session() as session:
            frozen_action = RefundAction(
                request_id="pp_req_fr75_frozen_act",
                order_id="ord_demo_1",
                return_id="ret_demo_escalated",
                decision_id="dec_fr75_frozen",
                amount_minor=5000,
                currency="USD",
                action_type="REFUND_R0",
                status="PLANNED",
            )
            session.add(frozen_action)
            session.commit()

        called_paypal = False

        class MockPayPalLive:
            def refund_capture_live(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
                nonlocal called_paypal
                called_paypal = True
                return {"status": "COMPLETED", "id": "PP-FORBIDDEN"}

        executor = RefundOutboxExecutor(repository=reset_db, client=MockPayPalLive())
        executor.run_once()

        # PayPal MUST NOT have been called
        assert called_paypal is False

        # Action status must be updated to BLOCKED_BY_DISPUTE
        with reset_db.get_session() as session:
            act = session.get(RefundAction, "pp_req_fr75_frozen_act")
            assert act is not None
            assert act.status == "BLOCKED_BY_DISPUTE"
    finally:
        with reset_db.get_session() as session:
            o = session.get(Order, "ord_demo_1")
            if o:
                o.frozen_by_dispute = False
                o.frozen_reason = None
                session.add(o)
                session.commit()
