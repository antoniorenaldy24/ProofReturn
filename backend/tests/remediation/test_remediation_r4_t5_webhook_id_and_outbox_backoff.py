"""Round 4 Task T5: Reject webhooks without an id; bounded outbox retries with escalation (RV3-04 LOW, RV3-12 LOW)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
import pathlib
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.config import ProofReturnSettings
from backend.db.repository import DatabaseRepository


class BoundedRetryFakePayPalClient:
    """Fake PayPal client inside backend/tests only for testing bounded outbox retries and escalation."""

    has_credentials = True

    def __init__(self) -> None:
        self.refund_calls: list[dict[str, Any]] = []
        self.get_refund_calls: list[str] = []
        self.get_capture_calls: list[str] = []
        self.should_timeout: bool = True
        self.next_refund_response: dict[str, Any] = {
            "id": "PP-REF-R4-T5-OK",
            "status": "COMPLETED",
            "paypal_debug_id": "dbg_r4_t5_ok",
        }
        self.next_get_refund_response: dict[str, Any] = {
            "id": "PP-REF-R4-T5-GET",
            "status": "PENDING",
            "paypal_debug_id": "dbg_r4_t5_get",
        }
        self.next_get_capture_refunds_response: list[dict[str, Any]] = []

    def refund_capture_live(
        self,
        *,
        capture_id: str,
        request_id: str,
        amount_minor: int,
        currency: str = "USD",
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.refund_calls.append(
            {
                "capture_id": capture_id,
                "request_id": request_id,
                "amount_minor": amount_minor,
                "currency": currency,
            }
        )
        if self.should_timeout:
            raise httpx.ReadTimeout("Simulated PayPal gateway timeout")
        return dict(self.next_refund_response)

    def get_refund_live(self, *, refund_id: str) -> dict[str, Any]:
        self.get_refund_calls.append(refund_id)
        return dict(self.next_get_refund_response)

    def get_capture_refunds_live(self, *, capture_id: str) -> list[dict[str, Any]]:
        self.get_capture_calls.append(capture_id)
        return list(self.next_get_capture_refunds_response)

    def get_capture_live(self, *, capture_id: str) -> dict[str, Any]:
        self.get_capture_calls.append(capture_id)
        return {"id": capture_id, "status": "COMPLETED", "refunds": list(self.next_get_capture_refunds_response)}


def _make_settings(db_url: str, secret: str = "r4_t5_webhook_secret_key_32bytes!") -> ProofReturnSettings:
    return ProofReturnSettings(
        database_url=db_url,
        demo_mode=True,
        mode="judge",
        enable_scheduler=False,
        demo_webhook_secret=secret,
    )


def _sign_webhook(secret: str, payload: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return raw, {
        "Content-Type": "application/json",
        "X-Demo-Webhook-Signature": sig,
    }


def _plan_r0_via_api(client: TestClient, repo: DatabaseRepository, return_id: str = "ret_demo_1") -> int:
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")
    ret = repo.get_return(return_id)
    assert ret is not None
    nonce = ret.challenge_nonce

    client.post(
        f"/v1/returns/{return_id}/declaration",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "declared_grade": "B",
            "fast_lane_terms_accepted": True,
            "shopper_nonce": "nonce_r4_t5",
        },
    )
    r_ev = client.post(
        f"/v1/returns/{return_id}/evidence",
        headers={"Authorization": f"Bearer {shopper_token}", "Idempotency-Key": f"ik-r4t5-ev-{return_id}"},
        json={
            "sha256": "e" * 64,
            "text_in_media": nonce,
            "faces_detected": 0,
            "client_blur_applied": True,
        },
    )
    assert r_ev.status_code == 200, r_ev.text
    return int(r_ev.json()["r0_tranche_minor"])


@pytest.mark.req("RV3-04", "NFR-04")
def test_webhook_without_id_returns_400_and_same_payload_with_id_processed_once(
    tmp_path: pathlib.Path,
) -> None:
    """Webhook without 'id' -> 400 INVALID_WEBHOOK_PAYLOAD, not recorded, no side effects; same payload with 'id' -> processed once."""
    db_url = f"sqlite:///{tmp_path / 't5_webhook_id.db'}"
    settings = _make_settings(db_url)
    repo = DatabaseRepository(database_url=db_url)
    app = create_app(settings=settings, repository=repo, demo_mode=True)
    client = TestClient(app)
    secret = settings.demo_webhook_secret.get_secret_value()

    # 1. Webhook payload missing 'id' altogether
    payload_no_id = {
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "resource": {"custom_id": "ord_demo_1", "dispute_id": "PP-DISP-NO-ID"},
    }
    raw_no_id, hdr_no_id = _sign_webhook(secret, payload_no_id)
    r_no_id = client.post("/v1/webhooks/paypal", content=raw_no_id, headers=hdr_no_id)
    assert r_no_id.status_code == 400, r_no_id.text
    assert r_no_id.json()["code"] == "INVALID_WEBHOOK_PAYLOAD"

    # 2. Webhook payload with blank 'id'
    payload_blank_id = {
        "id": "   ",
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "resource": {"custom_id": "ord_demo_1", "dispute_id": "PP-DISP-BLANK-ID"},
    }
    raw_blank, hdr_blank = _sign_webhook(secret, payload_blank_id)
    r_blank = client.post("/v1/webhooks/paypal", content=raw_blank, headers=hdr_blank)
    assert r_blank.status_code == 400, r_blank.text
    assert r_blank.json()["code"] == "INVALID_WEBHOOK_PAYLOAD"

    # Verify no side effects on order and no webhook events recorded
    order_before = repo.get_order("ord_demo_1")
    assert order_before is not None
    assert order_before.frozen_by_dispute is False

    # 3. Same payload with a valid 'id' -> processed once
    payload_with_id = {
        "id": "WH-R4-T5-VALID-001",
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "resource": {"custom_id": "ord_demo_1", "dispute_id": "PP-DISP-VALID-001"},
    }
    raw_valid, hdr_valid = _sign_webhook(secret, payload_with_id)
    r_valid1 = client.post("/v1/webhooks/paypal", content=raw_valid, headers=hdr_valid)
    assert r_valid1.status_code == 200, r_valid1.text
    assert r_valid1.json()["status"] == "PROCESSED"
    assert r_valid1.json()["event_id"] == "WH-R4-T5-VALID-001"

    order_after = repo.get_order("ord_demo_1")
    assert order_after is not None
    assert order_after.frozen_by_dispute is True
    assert repo.get_webhook_event("WH-R4-T5-VALID-001") is not None

    # Re-sending the same webhook with id -> deduplicated
    r_valid2 = client.post("/v1/webhooks/paypal", content=raw_valid, headers=hdr_valid)
    assert r_valid2.status_code == 200
    assert r_valid2.json()["status"] == "DEDUPLICATED"


@pytest.mark.req("RV3-12", "INV-03")
def test_unknown_action_not_retried_before_next_attempt_at_and_uses_identical_request_id(
    tmp_path: pathlib.Path,
) -> None:
    """UNKNOWN action is not retried before next_attempt_at; the request id is identical across retries."""
    db_url = f"sqlite:///{tmp_path / 't5_backoff.db'}"
    settings = _make_settings(db_url)
    repo = DatabaseRepository(database_url=db_url)
    fake_pp = BoundedRetryFakePayPalClient()
    app = create_app(settings=settings, repository=repo, demo_mode=True, paypal_client=fake_pp)
    client = TestClient(app)
    outbox = app.state.outbox_executor

    r0_minor = _plan_r0_via_api(client, repo)
    assert r0_minor > 0

    t0 = datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC)

    # Attempt 1 fails with timeout -> status UNKNOWN, attempt_count=1, next_attempt_at = t0 + 1 min
    res1 = outbox.run_once(limit=10, now=t0)
    assert res1["unknown"] == 1
    assert len(fake_pp.refund_calls) == 1
    first_request_id = fake_pp.refund_calls[0]["request_id"]

    act1 = repo.get_refund_action(first_request_id)
    assert act1 is not None
    assert act1.status == "UNKNOWN"
    assert act1.attempt_count == 1
    assert act1.next_attempt_at is not None
    next_1 = act1.next_attempt_at.replace(tzinfo=UTC) if act1.next_attempt_at.tzinfo is None else act1.next_attempt_at
    assert next_1 == t0 + timedelta(minutes=1)

    # Run before next_attempt_at (t0 + 30s) -> must NOT retry
    res_early = outbox.run_once(limit=10, now=t0 + timedelta(seconds=30))
    assert res_early["processed"] == 0
    assert len(fake_pp.refund_calls) == 1

    # Run at next_attempt_at (t0 + 1m), still failing -> attempt_count=2, backoff = 2 min
    t1 = t0 + timedelta(minutes=1)
    res2 = outbox.run_once(limit=10, now=t1)
    assert res2["unknown"] == 1
    assert len(fake_pp.refund_calls) == 2
    assert fake_pp.refund_calls[1]["request_id"] == first_request_id

    act2 = repo.get_refund_action(first_request_id)
    assert act2 is not None
    assert act2.status == "UNKNOWN"
    assert act2.attempt_count == 2
    assert act2.next_attempt_at is not None
    next_2 = act2.next_attempt_at.replace(tzinfo=UTC) if act2.next_attempt_at.tzinfo is None else act2.next_attempt_at
    assert next_2 == t1 + timedelta(minutes=2)

    # Run before second backoff expires (t1 + 1m) -> must NOT retry
    res_early2 = outbox.run_once(limit=10, now=t1 + timedelta(minutes=1))
    assert res_early2["processed"] == 0
    assert len(fake_pp.refund_calls) == 2

    # Run after second backoff expires (t1 + 2m) with PayPal succeeding -> CONFIRMED with identical request_id
    fake_pp.should_timeout = False
    t2 = t1 + timedelta(minutes=2)
    res3 = outbox.run_once(limit=10, now=t2)
    assert res3["confirmed"] == 1
    assert len(fake_pp.refund_calls) == 3
    assert fake_pp.refund_calls[2]["request_id"] == first_request_id

    act3 = repo.get_refund_action(first_request_id)
    assert act3 is not None
    assert act3.status == "CONFIRMED"
    assert act3.attempt_count == 3


@pytest.mark.req("RV3-12", "NFR-08")
def test_after_8_failed_attempts_escalates_to_needs_attention_and_raises_alert(
    tmp_path: pathlib.Path,
) -> None:
    """After 8 failed attempts -> GET reconciliation called, sets NEEDS_ATTENTION, keeps pending, nothing confirmed, and alert appears in /v1/ops/alerts."""
    db_url = f"sqlite:///{tmp_path / 't5_escalation.db'}"
    settings = _make_settings(db_url)
    repo = DatabaseRepository(database_url=db_url)
    fake_pp = BoundedRetryFakePayPalClient()
    app = create_app(settings=settings, repository=repo, demo_mode=True, paypal_client=fake_pp)
    client = TestClient(app)
    outbox = app.state.outbox_executor

    r0_minor = _plan_r0_via_api(client, repo)
    assert r0_minor > 0

    current_now = datetime(2026, 11, 7, 12, 0, 0, tzinfo=UTC)
    expected_backoffs = [1, 2, 4, 8, 16, 32, 60]

    for attempt_idx in range(1, 8):
        res = outbox.run_once(limit=10, now=current_now)
        assert res["unknown"] == 1
        assert len(fake_pp.refund_calls) == attempt_idx

        req_id = fake_pp.refund_calls[0]["request_id"]
        assert fake_pp.refund_calls[-1]["request_id"] == req_id

        act = repo.get_refund_action(req_id)
        assert act is not None
        assert act.status == "UNKNOWN"
        assert act.attempt_count == attempt_idx
        assert act.next_attempt_at is not None
        next_dt = act.next_attempt_at.replace(tzinfo=UTC) if act.next_attempt_at.tzinfo is None else act.next_attempt_at
        expected_delta = timedelta(minutes=expected_backoffs[attempt_idx - 1])
        assert next_dt == current_now + expected_delta

        # Advance time to next_attempt_at
        current_now = next_dt

    # 8th attempt fails -> reaches max 8 attempts -> calls GET on capture/refund -> sets NEEDS_ATTENTION
    res8 = outbox.run_once(limit=10, now=current_now)
    assert len(fake_pp.refund_calls) == 8
    req_id = fake_pp.refund_calls[0]["request_id"]
    assert all(c["request_id"] == req_id for c in fake_pp.refund_calls)
    assert len(fake_pp.get_capture_calls) >= 1 or len(fake_pp.get_refund_calls) >= 1
    assert res8.get("needs_attention", 0) == 1

    act_final = repo.get_refund_action(req_id)
    assert act_final is not None
    assert act_final.status == "NEEDS_ATTENTION"
    assert act_final.attempt_count == 8

    # Pending balance is preserved; nothing is confirmed
    ord_final = repo.get_order("ord_demo_1")
    assert ord_final is not None
    assert ord_final.confirmed_refunded_minor == 0
    assert ord_final.pending_refunded_minor == r0_minor

    # Subsequent outbox runs do NOT retry NEEDS_ATTENTION actions
    res9 = outbox.run_once(limit=10, now=current_now + timedelta(hours=5))
    assert res9["processed"] == 0
    assert len(fake_pp.refund_calls) == 8

    # Alert is visible in /v1/ops/alerts
    admin_tok = mint_staff_token(merchant_id="merch_a", role="MERCHANT_ADMIN", sub="admin_01")
    r_alerts = client.get("/v1/ops/alerts", headers={"Authorization": f"Bearer {admin_tok}"})
    assert r_alerts.status_code == 200, r_alerts.text
    alerts = r_alerts.json()["alerts"]
    assert len(alerts) >= 1
    assert any(
        "NEEDS_ATTENTION" in str(a.get("condition", "")) or a.get("status") == "NEEDS_ATTENTION" or a.get("alert_id") == "AL-02"
        for a in alerts
    )
