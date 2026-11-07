"""Round 4 Task T1: Enforce dispute and reversal freezes on the database refund path (RV3-11 HIGH, FR-75)."""

from __future__ import annotations

import hashlib
import hmac
import json
import pathlib
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.config import ProofReturnSettings
from backend.db.models import OrderItem, Return
from backend.db.repository import DatabaseRepository


class FakePayPalClient:
    """Fake PayPal client recording live refund calls."""

    has_credentials = True

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def refund_capture_live(
        self,
        *,
        capture_id: str,
        request_id: str,
        amount_minor: int,
        currency: str = "USD",
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "capture_id": capture_id,
                "request_id": request_id,
                "amount_minor": amount_minor,
                "currency": currency,
            }
        )
        return {
            "id": f"PP-LIVE-REF-{len(self.calls)}",
            "status": "COMPLETED",
            "paypal_debug_id": f"dbg_live_{len(self.calls)}",
        }


def _sign_webhook(secret: str, payload: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return raw, {
        "Content-Type": "application/json",
        "X-Demo-Webhook-Signature": sig,
    }


def _make_settings(db_url: str, webhook_secret: str = "r4_t1_webhook_secret_key_32bytes!") -> ProofReturnSettings:
    return ProofReturnSettings(
        database_url=db_url,
        demo_mode=True,
        mode="judge",
        enable_scheduler=False,
        demo_webhook_secret=webhook_secret,
    )


def _complete_r0_and_confirm(
    client: TestClient,
    repo: DatabaseRepository,
    return_id: str = "ret_demo_1",
    order_id: str = "ord_demo_1",
) -> int:
    """Submit declaration + evidence to plan R0, then run outbox to confirm R0."""
    shopper_token = mint_shopper_token(order_id=order_id, shopper_id="shopper_1")
    admin_token = mint_staff_token(merchant_id="merch_a", role="MERCHANT_ADMIN", sub="admin_01")

    ret = repo.get_return(return_id)
    assert ret is not None
    nonce = ret.challenge_nonce

    client.post(
        f"/v1/returns/{return_id}/declaration",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "declared_grade": "B",
            "fast_lane_terms_accepted": True,
            "shopper_nonce": "nonce_r4_t1",
        },
    )
    r_ev = client.post(
        f"/v1/returns/{return_id}/evidence",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "sha256": "a" * 64,
            "text_in_media": nonce,
            "faces_detected": 0,
            "client_blur_applied": True,
        },
    )
    assert r_ev.status_code == 200, r_ev.text
    r0_minor = r_ev.json()["r0_tranche_minor"]
    assert r0_minor > 0

    r_outbox = client.post(
        "/v1/ops/outbox/run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_outbox.status_code == 200
    assert r_outbox.json()["confirmed"] == 1

    ord_row = repo.get_order(order_id)
    assert ord_row is not None
    assert ord_row.confirmed_refunded_minor == r0_minor
    assert ord_row.pending_refunded_minor == 0
    return r0_minor


@pytest.mark.req("FR-75", "RV3-11")
def test_dispute_webhook_after_r0_confirmed_blocks_subsequent_planning_with_409_order_frozen(
    tmp_path: pathlib.Path,
) -> None:
    """Dispute webhook after R0 is confirmed -> evidence/review that would plan R1 returns 409 ORDER_FROZEN, and no new RefundAction row exists."""
    db_url = f"sqlite:///{tmp_path / 't1_disp_plan.db'}"
    settings = _make_settings(db_url)
    repo = DatabaseRepository(database_url=db_url)
    fake_pp = FakePayPalClient()
    app = create_app(settings=settings, repository=repo, demo_mode=True, paypal_client=fake_pp)
    client = TestClient(app)

    r0_minor = _complete_r0_and_confirm(client, repo)
    actions_before = repo.list_refund_actions_by_order("ord_demo_1")
    assert len(actions_before) == 1
    assert actions_before[0].status == "CONFIRMED"

    # Send signed CUSTOMER.DISPUTE.CREATED webhook
    secret = settings.demo_webhook_secret.get_secret_value()
    raw_wh, headers_wh = _sign_webhook(
        secret,
        {
            "id": "WH-R4-DISP-001",
            "event_type": "CUSTOMER.DISPUTE.CREATED",
            "resource": {"custom_id": "ord_demo_1", "dispute_id": "PP-DISP-R4-001"},
        },
    )
    r_wh = client.post("/v1/webhooks/paypal", content=raw_wh, headers=headers_wh)
    assert r_wh.status_code == 200

    # Verify DB columns set on orders table
    ord_after_wh = repo.get_order("ord_demo_1")
    assert ord_after_wh is not None
    assert ord_after_wh.frozen_by_dispute is True
    assert ord_after_wh.frozen_at is not None
    assert ord_after_wh.frozen_reason == "PP-DISP-R4-001"
    assert repo.is_order_frozen("ord_demo_1") is True
    # Already-released money is not clawed back
    assert ord_after_wh.confirmed_refunded_minor == r0_minor

    # 1. Review decision that would plan settlement/R1 must return 409 ORDER_FROZEN
    reviewer_token = mint_staff_token(merchant_id="merch_a", role="REVIEWER", sub="rev_01")
    r_rev = client.post(
        "/v1/review/ret_demo_1/decision",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={
            "verified_grade": "B",
            "outcome": "CONFIRMED",
            "notes": "Verified grade B at warehouse.",
        },
    )
    assert r_rev.status_code == 409, r_rev.text
    assert r_rev.json()["code"] == "ORDER_FROZEN"

    # No new RefundAction row exists
    actions_after_rev = repo.list_refund_actions_by_order("ord_demo_1")
    assert len(actions_after_rev) == 1

    # 2. Evidence submission on a return under the frozen order also returns 409 ORDER_FROZEN
    repo.save_order_item(
        OrderItem(
            order_item_id="item_demo_3",
            order_id="ord_demo_1",
            passport_id="pass_demo_1",
            sku="PR-HP-XM5",
            price_minor=38000,
            currency="USD",
        )
    )
    ret2 = Return(
        return_id="ret_frozen_ev",
        order_id="ord_demo_1",
        order_item_id="item_demo_3",
        merchant_id="merch_a",
        shopper_id="shopper_1",
        state="DECLARED",
        declared_grade="B",
        challenge_nonce="NONCE-FROZEN-EV",
        consent_recorded=True,
    )
    repo.save_return(ret2)
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")
    r_ev2 = client.post(
        "/v1/returns/ret_frozen_ev/evidence",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "sha256": "b" * 64,
            "text_in_media": "NONCE-FROZEN-EV",
            "faces_detected": 0,
            "client_blur_applied": True,
        },
    )
    assert r_ev2.status_code == 409, r_ev2.text
    assert r_ev2.json()["code"] == "ORDER_FROZEN"
    assert len(repo.list_refund_actions_by_order("ord_demo_1")) == 1


@pytest.mark.req("FR-75", "RV3-11")
def test_dispute_webhook_while_r1_planned_marks_blocked_by_dispute_and_releases_pending(
    tmp_path: pathlib.Path,
) -> None:
    """Dispute webhook while R1 is PLANNED -> outbox run sends nothing to fake PayPal client, action becomes BLOCKED_BY_DISPUTE, pending_refunded_minor returns to prior value."""
    db_url = f"sqlite:///{tmp_path / 't1_disp_outbox.db'}"
    settings = _make_settings(db_url)
    repo = DatabaseRepository(database_url=db_url)
    fake_pp = FakePayPalClient()
    app = create_app(settings=settings, repository=repo, demo_mode=True, paypal_client=fake_pp)
    client = TestClient(app)

    r0_minor = _complete_r0_and_confirm(client, repo)
    fake_pp.calls.clear()

    # Plan R1 / settlement via warehouse review BEFORE dispute arrives
    reviewer_token = mint_staff_token(merchant_id="merch_a", role="REVIEWER", sub="rev_01")
    r_rev = client.post(
        "/v1/review/ret_demo_1/decision",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={
            "verified_grade": "B",
            "outcome": "CONFIRMED",
            "notes": "Verified grade B before dispute.",
        },
    )
    assert r_rev.status_code == 200, r_rev.text
    r1_minor = r_rev.json()["additional_refund_minor"]
    assert r1_minor > 0

    ord_planned = repo.get_order("ord_demo_1")
    assert ord_planned is not None
    assert ord_planned.pending_refunded_minor == r1_minor
    assert ord_planned.confirmed_refunded_minor == r0_minor

    # Now dispute webhook arrives while R1 is PLANNED
    secret = settings.demo_webhook_secret.get_secret_value()
    raw_wh, headers_wh = _sign_webhook(
        secret,
        {
            "id": "WH-R4-DISP-002",
            "event_type": "CUSTOMER.DISPUTE.CREATED",
            "resource": {"custom_id": "ord_demo_1", "dispute_id": "PP-DISP-R4-002"},
        },
    )
    r_wh = client.post("/v1/webhooks/paypal", content=raw_wh, headers=headers_wh)
    assert r_wh.status_code == 200

    # Run outbox executor via API
    admin_token = mint_staff_token(merchant_id="merch_a", role="MERCHANT_ADMIN", sub="admin_01")
    r_outbox = client.post(
        "/v1/ops/outbox/run",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_outbox.status_code == 200

    # Nothing sent to fake PayPal client
    assert len(fake_pp.calls) == 0

    # Action status is BLOCKED_BY_DISPUTE
    actions = repo.list_refund_actions_by_order("ord_demo_1")
    r1_actions = [a for a in actions if a.tranche == "SETTLEMENT"]
    assert len(r1_actions) == 1
    assert r1_actions[0].status == "BLOCKED_BY_DISPUTE"

    # pending_refunded_minor returned to its prior value (0), confirmed_refunded_minor intact
    ord_after = repo.get_order("ord_demo_1")
    assert ord_after is not None
    assert ord_after.pending_refunded_minor == 0
    assert ord_after.confirmed_refunded_minor == r0_minor


@pytest.mark.req("FR-75", "RV3-11")
def test_capture_reversed_webhook_blocks_planning_and_outbox_execution(
    tmp_path: pathlib.Path,
) -> None:
    """PAYMENT.CAPTURE.REVERSED -> same two checks (blocks planning with 409 ORDER_FROZEN and blocks outbox execution as BLOCKED_BY_DISPUTE)."""
    # Check 1: Capture reversed after R0 confirmed -> planning R1 returns 409 ORDER_FROZEN
    db_url_1 = f"sqlite:///{tmp_path / 't1_rev_plan.db'}"
    settings_1 = _make_settings(db_url_1)
    repo_1 = DatabaseRepository(database_url=db_url_1)
    fake_pp_1 = FakePayPalClient()
    app_1 = create_app(settings=settings_1, repository=repo_1, demo_mode=True, paypal_client=fake_pp_1)
    client_1 = TestClient(app_1)

    _complete_r0_and_confirm(client_1, repo_1)
    secret = settings_1.demo_webhook_secret.get_secret_value()
    raw_wh1, headers_wh1 = _sign_webhook(
        secret,
        {
            "id": "WH-R4-REV-001",
            "event_type": "PAYMENT.CAPTURE.REVERSED",
            "resource": {"custom_id": "ord_demo_1"},
        },
    )
    r_wh1 = client_1.post("/v1/webhooks/paypal", content=raw_wh1, headers=headers_wh1)
    assert r_wh1.status_code == 200

    ord_1 = repo_1.get_order("ord_demo_1")
    assert ord_1 is not None
    assert ord_1.capture_reversed is True
    assert ord_1.reversed_at is not None
    assert repo_1.is_order_frozen("ord_demo_1") is True

    reviewer_token = mint_staff_token(merchant_id="merch_a", role="REVIEWER", sub="rev_01")
    r_rev1 = client_1.post(
        "/v1/review/ret_demo_1/decision",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"verified_grade": "B", "outcome": "CONFIRMED", "notes": "After reversal."},
    )
    assert r_rev1.status_code == 409
    assert r_rev1.json()["code"] == "ORDER_FROZEN"
    assert len(repo_1.list_refund_actions_by_order("ord_demo_1")) == 1

    # Check 2: Capture reversed while R1 is PLANNED -> outbox marks BLOCKED_BY_DISPUTE and releases pending
    db_url_2 = f"sqlite:///{tmp_path / 't1_rev_outbox.db'}"
    settings_2 = _make_settings(db_url_2)
    repo_2 = DatabaseRepository(database_url=db_url_2)
    fake_pp_2 = FakePayPalClient()
    app_2 = create_app(settings=settings_2, repository=repo_2, demo_mode=True, paypal_client=fake_pp_2)
    client_2 = TestClient(app_2)

    r0_minor_2 = _complete_r0_and_confirm(client_2, repo_2)
    fake_pp_2.calls.clear()

    r_rev2 = client_2.post(
        "/v1/review/ret_demo_1/decision",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"verified_grade": "B", "outcome": "CONFIRMED", "notes": "Before reversal."},
    )
    assert r_rev2.status_code == 200

    raw_wh2, headers_wh2 = _sign_webhook(
        secret,
        {
            "id": "WH-R4-REV-002",
            "event_type": "PAYMENT.CAPTURE.REVERSED",
            "resource": {"custom_id": "ord_demo_1"},
        },
    )
    assert client_2.post("/v1/webhooks/paypal", content=raw_wh2, headers=headers_wh2).status_code == 200

    admin_token = mint_staff_token(merchant_id="merch_a", role="MERCHANT_ADMIN", sub="admin_01")
    assert client_2.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200

    assert len(fake_pp_2.calls) == 0
    r1_acts = [a for a in repo_2.list_refund_actions_by_order("ord_demo_1") if a.tranche == "SETTLEMENT"]
    assert len(r1_acts) == 1
    assert r1_acts[0].status == "BLOCKED_BY_DISPUTE"
    ord_2 = repo_2.get_order("ord_demo_1")
    assert ord_2 is not None
    assert ord_2.pending_refunded_minor == 0
    assert ord_2.confirmed_refunded_minor == r0_minor_2


@pytest.mark.req("FR-75", "RV3-11")
def test_freeze_survives_application_restart(tmp_path: pathlib.Path) -> None:
    """Freeze survives an application restart (new app instance on the same database)."""
    db_url = f"sqlite:///{tmp_path / 't1_restart.db'}"
    settings = _make_settings(db_url)
    repo_1 = DatabaseRepository(database_url=db_url)
    app_1 = create_app(settings=settings, repository=repo_1, demo_mode=True, paypal_client=FakePayPalClient())
    client_1 = TestClient(app_1)

    _complete_r0_and_confirm(client_1, repo_1)

    secret = settings.demo_webhook_secret.get_secret_value()
    raw_wh, headers_wh = _sign_webhook(
        secret,
        {
            "id": "WH-R4-RESTART-001",
            "event_type": "CUSTOMER.DISPUTE.CREATED",
            "resource": {"custom_id": "ord_demo_1", "dispute_id": "PP-DISP-RESTART"},
        },
    )
    assert client_1.post("/v1/webhooks/paypal", content=raw_wh, headers=headers_wh).status_code == 200

    # Simulate full application restart with a fresh DatabaseRepository and create_app on the same DB
    repo_2 = DatabaseRepository(database_url=db_url)
    app_2 = create_app(settings=settings, repository=repo_2, demo_mode=True, paypal_client=FakePayPalClient())
    client_2 = TestClient(app_2)

    assert repo_2.is_order_frozen("ord_demo_1") is True
    reviewer_token = mint_staff_token(merchant_id="merch_a", role="REVIEWER", sub="rev_01")
    r_rev = client_2.post(
        "/v1/review/ret_demo_1/decision",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"verified_grade": "B", "outcome": "CONFIRMED", "notes": "Attempt after restart."},
    )
    assert r_rev.status_code == 409
    assert r_rev.json()["code"] == "ORDER_FROZEN"
    assert len(repo_2.list_refund_actions_by_order("ord_demo_1")) == 1


@pytest.mark.req("FR-75", "RV3-11", "AUD-24")
def test_rejected_unsigned_webhook_does_not_freeze_anything(tmp_path: pathlib.Path) -> None:
    """Rejected (unsigned) webhook does not freeze anything."""
    db_url = f"sqlite:///{tmp_path / 't1_unsigned.db'}"
    settings = _make_settings(db_url)
    repo = DatabaseRepository(database_url=db_url)
    app = create_app(settings=settings, repository=repo, demo_mode=True, paypal_client=FakePayPalClient())
    client = TestClient(app)

    for evt_type in ("CUSTOMER.DISPUTE.CREATED", "PAYMENT.CAPTURE.REVERSED"):
        resp = client.post(
            "/v1/webhooks/paypal",
            json={
                "id": f"WH-UNSIGNED-{evt_type}",
                "event_type": evt_type,
                "resource": {"custom_id": "ord_demo_1", "dispute_id": "PP-FAKE-DISP"},
            },
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == "INVALID_WEBHOOK_SIGNATURE"

    ord_row = repo.get_order("ord_demo_1")
    assert ord_row is not None
    assert ord_row.frozen_by_dispute is False
    assert ord_row.frozen_at is None
    assert ord_row.frozen_reason is None
    assert ord_row.capture_reversed is False
    assert ord_row.reversed_at is None
    assert repo.is_order_frozen("ord_demo_1") is False
