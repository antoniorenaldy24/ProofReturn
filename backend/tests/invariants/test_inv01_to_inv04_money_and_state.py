"""Invariant tests for INV-01, INV-02, INV-03, INV-04 through the API (SSOT Section 29.1).

INV-01: Sum of all refunds against a capture never exceeds capture. Concurrent refund planning
        for one order never exceeds the capture.
INV-02: Refunds issued only against merchant's own capture for that order; cross-merchant -> 404.
INV-03: Mutating PayPal calls require persisted decision + unique request id; retries reuse the same
        PayPal-Request-Id.
INV-04: State machine transitions follow valid paths; each guard false -> 409, state unchanged, no call.
"""

from __future__ import annotations

from typing import Any
from fastapi.testclient import TestClient
from sqlmodel import select

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.db.models import Order, RefundAction, Return


def test_inv01_over_refund_attempt_rejected_and_unpersisted(reset_db: Any) -> None:
    """INV-01 NEGATIVE: An attempt to plan or settle a refund exceeding the capture amount

    must be REJECTED with 409 REFUND_LIMIT_EXCEEDED, and nothing must be persisted.
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    tok_reviewer = mint_staff_token("merch_a", "REVIEWER", sub="rev_inv01")

    # Order ord_demo_1 has capture of 38000 minor.
    # Check initial database state
    with reset_db.get_session() as session:
        initial_order = session.get(Order, "ord_demo_1")
        assert initial_order is not None
        initial_pending = initial_order.pending_refunded_minor
        initial_confirmed = initial_order.confirmed_refunded_minor
        initial_actions_count = len(session.exec(select(RefundAction).where(RefundAction.order_id == "ord_demo_1")).all())

    # First settle ret_demo_escalated legitimately (outcome SETTLE_VERIFIED -> 19000 minor)
    r1 = client.post(
        "/v1/review/ret_demo_escalated/decision",
        headers={"Authorization": f"Bearer {tok_reviewer}", "Idempotency-Key": "ik-inv01-legit"},
        json={"outcome": "SETTLE_VERIFIED", "verified_grade": "D", "notes": "Half refund"},
    )
    assert r1.status_code == 200

    # Now attempt a SECOND settlement on ret_demo_1 that requests another refund
    # that would exceed the remaining refundable amount (e.g. 25000 minor when only 19000 remains).
    # ret_demo_1 declared grade B on 38000 item. Let's try to settle ret_demo_1 with full refund
    # or an excessive amount.
    r_excess = client.post(
        "/v1/review/ret_demo_1/decision",
        headers={"Authorization": f"Bearer {tok_reviewer}", "Idempotency-Key": "ik-inv01-excess"},
        json={"outcome": "SETTLE_VERIFIED", "verified_grade": "A", "notes": "Attempting excess settlement"},
    )
    # Must fail with 409 REFUND_LIMIT_EXCEEDED
    assert r_excess.status_code == 409
    err = r_excess.json()
    assert err["code"] == "REFUND_LIMIT_EXCEEDED"

    # Verify NEGATIVE assertion: nothing persisted for the excessive attempt
    with reset_db.get_session() as session:
        order_after = session.get(Order, "ord_demo_1")
        assert order_after is not None
        # Total pending + confirmed must NEVER exceed capture (38000)
        assert order_after.pending_refunded_minor + order_after.confirmed_refunded_minor <= 38000
        # No refund action exists for ik-inv01-excess
        excess_action = session.exec(
            select(RefundAction).where(RefundAction.decision_id == "ik-inv01-excess")
        ).first()
        assert excess_action is None


def test_inv02_cross_merchant_refund_rejected_with_404(reset_db: Any) -> None:
    """INV-02 NEGATIVE: Cross-merchant refund or access attempt must return 404 (BOLA isolation TZ-04).

    Nothing must be persisted or modified on the victim merchant's resources.
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    # Merchant B attacker staff token
    tok_merch_b = mint_staff_token("merch_b", "REVIEWER", sub="rev_merch_b")

    # Record Merchant A return state before attack
    with reset_db.get_session() as session:
        ret_before = session.get(Return, "ret_demo_1")
        assert ret_before is not None
        initial_ret_state = ret_before.state
        order_before = session.get(Order, "ord_demo_1")
        assert order_before is not None
        initial_order_pending = order_before.pending_refunded_minor

    # Attacker attempts to settle or decide Merchant A's return
    r_attack = client.post(
        "/v1/review/ret_demo_1/decision",
        headers={"Authorization": f"Bearer {tok_merch_b}", "Idempotency-Key": "ik-inv02-cross"},
        json={"outcome": "SETTLE_VERIFIED", "verified_grade": "A"},
    )
    assert r_attack.status_code == 404
    assert r_attack.json()["code"] in {"RESOURCE_NOT_FOUND", "RETURN_NOT_FOUND", "NOT_FOUND"}

    # Attacker attempts to view Merchant A's receipts or evidence pack
    r_receipts = client.get(
        "/v1/returns/ret_demo_1/receipts",
        headers={"Authorization": f"Bearer {tok_merch_b}"},
    )
    assert r_receipts.status_code == 404

    # Verify NEGATIVE assertion: victim return and order are completely untouched
    with reset_db.get_session() as session:
        ret_after = session.get(Return, "ret_demo_1")
        assert ret_after is not None
        assert ret_after.state == initial_ret_state
        order_after = session.get(Order, "ord_demo_1")
        assert order_after is not None
        assert order_after.pending_refunded_minor == initial_order_pending


def test_inv03_outbox_retry_reuses_identical_request_id(reset_db: Any) -> None:
    """INV-03: Mutating PayPal calls require persisted decision + unique request id.

    Retries of an outbox action reuse the EXACT same PayPal-Request-Id (RV3-04, RV3-12).
    """
    from datetime import datetime, timezone
    from backend.payments.outbox import RefundOutboxExecutor

    with reset_db.get_session() as session:
        # Create an outbox refund action with a specific request_id
        action = RefundAction(
            action_id="act_inv03_test",
            order_id="ord_demo_1",
            return_id="ret_demo_1",
            decision_id="dec_inv03_test",
            request_id="pp_req_inv03_unique_12345",
            amount_minor=5000,
            currency="USD",
            action_type="REFUND_R0",
            status="UNKNOWN",
            attempt_count=1,
            next_attempt_at=datetime.now(timezone.utc),
        )
        session.add(action)
        session.commit()

    recorded_request_ids: list[str] = []

    class MockPayPalLive:
        def refund_capture_live(self, capture_id: str, amount_minor: int, currency: str, request_id: str) -> dict[str, Any]:
            recorded_request_ids.append(request_id)
            # Return pending to simulate retry need
            return {"status": "PENDING", "id": "PP-REF-INV03-TEST"}

    executor = RefundOutboxExecutor(repository=reset_db, client=MockPayPalLive())
    executor.run_once()

    # Assert that the exact same request_id was supplied
    assert len(recorded_request_ids) >= 1
    assert recorded_request_ids[0] == "pp_req_inv03_unique_12345"

    with reset_db.get_session() as session:
        act = session.get(RefundAction, "pp_req_inv03_unique_12345")
        assert act is not None
        # Must retain original request_id
        assert act.request_id == "pp_req_inv03_unique_12345"
        assert act.paypal_refund_id == "PP-REF-INV03-TEST"


def test_inv04_illegal_state_transition_rejected_and_unpersisted(reset_db: Any) -> None:
    """INV-04 NEGATIVE: State transitions must follow valid state machine paths.

    If any guard is false -> 409 INVALID_STATE_TRANSITION, state remains unchanged,
    and no refund actions are executed or persisted.
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    tok_shopper = mint_shopper_token("ord_demo_1", "shopper_1")

    # Set return into SETTLED state
    with reset_db.get_session() as session:
        ret = session.get(Return, "ret_demo_1")
        assert ret is not None
        ret.state = "SETTLED"
        session.add(ret)
        session.commit()

    # Attempting to cancel a settled return is illegal in ReturnStateMachine (FR-88)
    r_illegal = client.post(
        "/v1/returns/ret_demo_1/cancel",
        headers={"Authorization": f"Bearer {tok_shopper}"},
    )
    assert r_illegal.status_code == 409
    err = r_illegal.json()
    assert err["code"] == "INVALID_STATE_TRANSITION"

    # Verify NEGATIVE assertion: state is STILL SETTLED, nothing changed
    with reset_db.get_session() as session:
        ret_after = session.get(Return, "ret_demo_1")
        assert ret_after is not None
        assert ret_after.state == "SETTLED"
