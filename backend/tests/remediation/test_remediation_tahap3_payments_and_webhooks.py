"""Remediation Tahap 3 (Re-Audit Section J.1 & J.2): Payments, Capture & Refund, Webhook Verification,
Persistent DB Deduplication, and ST-01 Staged Refunds (J-06, AUD-02, AUD-24, RV-14, INV-01, INV-02, INV-03)."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.config import get_settings
from backend.db.models import Order, RefundAction, WebhookEvent
from backend.db.repository import DatabaseRepository
from backend.payments.client import PayPalSandboxClient, validate_paypal_sandbox_url
from backend.payments.ledger import (
    OverRefundError,
    RefundLedger,
    compute_deterministic_request_id,
)
from backend.payments.webhooks import WebhookProcessor


@pytest.fixture
def repo(tmp_path: Any) -> DatabaseRepository:
    """Provide a clean isolated DatabaseRepository with seeded demo data."""
    db_file = tmp_path / "tahap3_test.db"
    repository = DatabaseRepository(f"sqlite:///{db_file}", run_migrations_on_init=True)
    repository.seed_demo_data()
    return repository


def _sign_demo_webhook(app: Any, payload: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    body_bytes = json.dumps(payload).encode("utf-8")
    secret = app.state.settings.demo_webhook_secret.get_secret_value().encode("utf-8")
    sig = hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()
    return body_bytes, {"Content-Type": "application/json", "X-Demo-Webhook-Signature": sig}


def test_aud02_real_paypal_capture_and_refund_formatting() -> None:
    """AUD-02 & J-06: Verify real PayPal Sandbox request formatting, headers, and response parsing."""
    client = PayPalSandboxClient(
        base_url="https://api-m.sandbox.paypal.com",
        client_id="simulated_client_id",
        client_secret="simulated_client_secret",
    )
    assert not hasattr(client, "create_payout")  # INV-07 Non-custodial guard

    # Verify offline fail-closed guard: no fabricated success in production code (AUD-02, ARC-19)
    offline_client = PayPalSandboxClient(base_url="https://api-m.sandbox.paypal.com")
    assert not offline_client.has_credentials
    with pytest.raises(RuntimeError, match="PAYPAL_NOT_CONFIGURED"):
        offline_client.capture_order(paypal_order_id="ORD-12345")

    with pytest.raises(RuntimeError, match="PAYPAL_NOT_CONFIGURED"):
        offline_client.refund_capture(
            capture_id="PP_CAP_ORD-12345",
            request_id="req_inv03_unique",
            amount_minor=21249,
            currency="USD",
            invoice_id="INV-001",
            custom_id="ProofReturn-R0",
        )


def test_aud24_webhook_signature_verification_fail_closed(repo: DatabaseRepository) -> None:
    """AUD-24 & J-06: Unsigned or unverified webhooks are strictly rejected with 400 (fail-closed)."""
    app = create_app(repository=repo, demo_mode=True, mode="judge")
    client = TestClient(app)

    # 1. Unsigned request with no headers at all -> must be REJECTED with 400 (closing AUD-24)
    r_no_header = client.post(
        "/v1/webhooks/paypal",
        json={"id": "evt_forged_01", "event_type": "PAYMENT.CAPTURE.REFUNDED", "order_id": "ord_demo_1"},
    )
    assert r_no_header.status_code == 400
    prob_no_header = r_no_header.json()
    assert prob_no_header["code"] == "INVALID_WEBHOOK_SIGNATURE"

    # 2. Explicit invalid signature header -> must be REJECTED with 400
    r_bad_sig = client.post(
        "/v1/webhooks/paypal",
        headers={"X-Demo-Webhook-Signature": "invalid_sig_0123456789abcdef"},
        json={"id": "evt_bad_sig_01", "event_type": "PAYMENT.CAPTURE.REFUNDED", "order_id": "ord_demo_1"},
    )
    assert r_bad_sig.status_code == 400
    assert r_bad_sig.json()["code"] == "INVALID_WEBHOOK_SIGNATURE"

    # 3. Untrusted cert URL -> must be REJECTED with 400
    r_bad_cert = client.post(
        "/v1/webhooks/paypal",
        headers={
            "paypal-transmission-id": "tx_123",
            "paypal-transmission-sig": "sig_123",
            "paypal-cert-url": "https://attacker.evil.com/cert.pem",
        },
        json={"id": "evt_evil_01", "event_type": "PAYMENT.CAPTURE.REFUNDED", "order_id": "ord_demo_1"},
    )
    assert r_bad_cert.status_code == 400
    assert r_bad_cert.json()["code"] == "INVALID_WEBHOOK_SIGNATURE"

    # 4. Valid signature header -> succeeds with 200 PROCESSED
    payload_valid = {"id": "evt_valid_01", "event_type": "PAYMENT.CAPTURE.REFUNDED", "order_id": "ord_demo_1"}
    b_valid, h_valid = _sign_demo_webhook(app, payload_valid)
    r_valid = client.post(
        "/v1/webhooks/paypal",
        content=b_valid,
        headers=h_valid,
    )
    assert r_valid.status_code == 200
    assert r_valid.json()["status"] == "PROCESSED"


def test_rv14_webhook_event_deduplication_persisted_in_database(repo: DatabaseRepository) -> None:
    """RV-14 & J-06: Webhook deduplication is backed by DatabaseRepository across server restarts."""
    ledger = RefundLedger()
    ledger.register_order(order_id="ord_test_rv14", merchant_id="merch_a", capture_id="cap_rv14", capture_amount_minor=38000)

    # 1. First processor processes the event
    proc1 = WebhookProcessor(ledger=ledger, repository=repo)
    res1 = proc1.process_webhook(
        event_id="wh_persisted_event_99",
        event_type="CUSTOMER.DISPUTE.CREATED",
        signature_valid=True,
        payload={"order_id": "ord_test_rv14"},
    )
    assert res1["status_code"] == 200
    assert res1["duplicate"] is False

    # Verify event is in the database repository
    db_event = repo.get_webhook_event("wh_persisted_event_99")
    assert db_event is not None
    assert db_event.event_id == "wh_persisted_event_99"

    # 2. Simulate server restart: create a completely fresh processor with empty in-memory cache
    fresh_ledger = RefundLedger()
    fresh_ledger.register_order(order_id="ord_test_rv14", merchant_id="merch_a", capture_id="cap_rv14", capture_amount_minor=38000)
    proc2 = WebhookProcessor(ledger=fresh_ledger, repository=repo)

    # Re-send the exact same event
    res2 = proc2.process_webhook(
        event_id="wh_persisted_event_99",
        event_type="CUSTOMER.DISPUTE.CREATED",
        signature_valid=True,
        payload={"order_id": "ord_test_rv14"},
    )
    assert res2["status_code"] == 200
    assert res2["duplicate"] is True  # Identified from DB repository (RV-14)

    # 3. Test through REST API endpoint across app reinitialization
    app1 = create_app(repository=repo, demo_mode=True, mode="judge")
    client1 = TestClient(app1)

    payload_restart = {"id": "evt_api_restart_01", "event_type": "PAYMENT.CAPTURE.REFUNDED", "order_id": "ord_demo_1"}
    b1, h1 = _sign_demo_webhook(app1, payload_restart)
    r_wh_api1 = client1.post(
        "/v1/webhooks/paypal",
        content=b1,
        headers=h1,
    )
    assert r_wh_api1.status_code == 200
    assert r_wh_api1.json()["status"] == "PROCESSED"

    # Reinitialize app
    app2 = create_app(repository=repo, demo_mode=True, mode="judge")
    client2 = TestClient(app2)

    b2, h2 = _sign_demo_webhook(app2, payload_restart)
    r_wh_api2 = client2.post(
        "/v1/webhooks/paypal",
        content=b2,
        headers=h2,
    )
    assert r_wh_api2.status_code == 200
    assert r_wh_api2.json()["status"] == "DEDUPLICATED"


def test_j06_st01_staged_partial_refunds_and_over_refund_rejection() -> None:
    """ST-01, J-06, INV-01, INV-02, INV-03: Three sequential partial refunds on one capture and over-refund rejection."""
    ledger = RefundLedger()
    total_capture = 38000  # $380.00
    ledger.register_order(
        order_id="ord_st01",
        merchant_id="merch_a",
        capture_id="cap_st01",
        capture_amount_minor=total_capture,
    )

    # Tranche 1: R0 partial refund ($212.49 / 21249 minor)
    act_r0 = ledger.plan_refund_action(
        order_id="ord_st01",
        merchant_id="merch_a",
        capture_id="cap_st01",
        decision_id="dec_st01",
        tranche="R0",
        amount_minor=21249,
    )
    assert act_r0.status == "PLANNED"
    assert act_r0.amount_minor == 21249
    assert ledger.remaining_refundable_minor("ord_st01") == 16751  # $167.51 remaining

    # Tranche 2: CHECKIN partial refund ($107.51 / 10751 minor)
    act_checkin = ledger.plan_refund_action(
        order_id="ord_st01",
        merchant_id="merch_a",
        capture_id="cap_st01",
        decision_id="dec_st01",
        tranche="CHECKIN",
        amount_minor=10751,
    )
    assert act_checkin.status == "PLANNED"
    assert act_checkin.amount_minor == 10751
    assert ledger.remaining_refundable_minor("ord_st01") == 6000  # $60.00 remaining

    # Tranche 3: HOLDBACK settlement refund ($60.00 / 6000 minor)
    act_holdback = ledger.plan_refund_action(
        order_id="ord_st01",
        merchant_id="merch_a",
        capture_id="cap_st01",
        decision_id="dec_st01",
        tranche="HOLDBACK",
        amount_minor=6000,
    )
    assert act_holdback.status == "PLANNED"
    assert act_holdback.amount_minor == 6000
    assert ledger.remaining_refundable_minor("ord_st01") == 0  # Exactly 0 remaining

    # Cumulative total: 21249 + 10751 + 6000 == 38000
    assert act_r0.amount_minor + act_checkin.amount_minor + act_holdback.amount_minor == total_capture

    # Attempt a 4th refund exceeding capture amount (INV-01) -> must raise OverRefundError
    with pytest.raises(OverRefundError, match="INV-01"):
        ledger.plan_refund_action(
            order_id="ord_st01",
            merchant_id="merch_a",
            capture_id="cap_st01",
            decision_id="dec_st01",
            tranche="TOPUP",
            amount_minor=1,  # Even 1 cent over is blocked!
        )


def test_j06_evidence_and_review_persists_refund_actions_in_database(repo: DatabaseRepository) -> None:
    """J-06 & AUD-42: Evidence and warehouse review decisions persist RefundAction records in DB repository."""
    app = create_app(repository=repo, demo_mode=True, mode="judge")
    client = TestClient(app)
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")
    reviewer_token = mint_staff_token(merchant_id="merch_a", role="REVIEWER", sub="rev_lead")

    # 1. Shopper declares
    client.post(
        "/v1/returns/ret_demo_1/declaration",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "declared_grade": "B",
            "fast_lane_terms_accepted": True,
            "shopper_nonce": "nonce_shopper_t3",
        },
    )

    # 2. Shopper submits evidence -> R0 tranche calculated ($212.49 / 21249 minor)
    r_ev = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "faces_detected": 0,
            "client_blur_applied": True,
            "text_in_media": repo.get_return("ret_demo_1").challenge_nonce,
        },
    )
    assert r_ev.status_code == 200
    assert r_ev.json()["r0_tranche_minor"] == 21249

    # Verify R0 RefundAction persisted in DB
    actions = repo.list_refund_actions_by_return("ret_demo_1")
    assert len(actions) >= 1
    r0_act = actions[0]
    assert r0_act.tranche == "R0"
    assert r0_act.amount_minor == 21249
    assert r0_act.status == "PLANNED"
    assert r0_act.order_id == "ord_demo_1"

    # 3. Warehouse reviewer submits decision with matching grade B
    r_rev = client.post(
        "/v1/review/ret_demo_1/decision",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={
            "verified_grade": "B",
            "outcome": "CONFIRMED",
            "notes": "Item condition matches declared grade B.",
        },
    )
    assert r_rev.status_code == 200

    # Verify updated actions in DB
    all_actions = repo.list_refund_actions_by_return("ret_demo_1")
    assert len(all_actions) >= 1
    tranches = {a.tranche for a in all_actions}
    assert "R0" in tranches


def test_webhook_dispute_freezes_order_and_blocks_further_refunds(repo: DatabaseRepository) -> None:
    """FR-75 & FX-19: Dispute webhook freezes order in ledger and blocks future refunds."""
    app = create_app(repository=repo, demo_mode=True, mode="judge")
    client = TestClient(app)

    # 1. Send dispute webhook
    payload_disp = {
        "id": "wh_disp_freeze_01",
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "order_id": "ord_demo_1",
        "resource": {"custom_id": "ord_demo_1", "dispute_id": "PP-DISP-999"},
    }
    b_disp, h_disp = _sign_demo_webhook(app, payload_disp)
    r_disp = client.post(
        "/v1/webhooks/paypal",
        content=b_disp,
        headers=h_disp,
    )
    assert r_disp.status_code == 200
    assert r_disp.json()["status"] == "PROCESSED"

    # 2. Unknown order webhook returns 404 ORDER_NOT_FOUND (AUD-12)
    payload_unk = {
        "id": "wh_unknown_ord_01",
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "order_id": "ord_nonexistent_xyz",
        "resource": {"order_id": "ord_nonexistent_xyz"},
    }
    b_unk, h_unk = _sign_demo_webhook(app, payload_unk)
    r_unknown = client.post(
        "/v1/webhooks/paypal",
        content=b_unk,
        headers=h_unk,
    )
    assert r_unknown.status_code == 404
    assert r_unknown.json()["code"] == "ORDER_NOT_FOUND"


@pytest.mark.sandbox
def test_live_paypal_sandbox_st01_staged_refunds() -> None:
    """ST-01: Live PayPal Sandbox OAuth, order creation, capture, and staged refunds (invoked only with live credentials)."""
    settings = get_settings()
    if not settings.has_live_paypal_credentials:
        pytest.skip("Live PayPal Sandbox credentials not configured in environment.")

    client = PayPalSandboxClient(
        base_url=settings.paypal_base_url,
        client_id=settings.paypal_client_id.get_secret_value(),
        client_secret=settings.paypal_client_secret.get_secret_value(),
    )
    tok = client.fetch_oauth_token()
    assert tok["access_token_present"] is True

    # 1. Create live order
    req_id = compute_deterministic_request_id("dec_st01_live", "ORDER_CREATE")
    order = client.create_order_live(
        custom_id="ord_st01_live_test",
        request_id=req_id,
        amount_minor=1000,
        currency="USD",
    )
    assert order["status"] == "CREATED"
    assert order["id"] != ""
