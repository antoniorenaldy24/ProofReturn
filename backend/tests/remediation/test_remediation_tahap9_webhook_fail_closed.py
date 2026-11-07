"""Tests for TASK T2: Fail-closed PayPal webhook verification (AUD-24 HIGH)."""

import hashlib
import hmac
import json
from pathlib import Path
from typing import Any
import pytest
from pydantic import SecretStr
from starlette.testclient import TestClient

from backend.api.app import create_app
from backend.config import ProofReturnSettings
from backend.db.models import Order
from backend.db.repository import DatabaseRepository


VALID_BOOTSTRAP_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
DEMO_WEBHOOK_SECRET = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"


def sign_webhook_body(body_bytes: bytes, secret: str = DEMO_WEBHOOK_SECRET) -> str:
    """Helper to compute HMAC-SHA256 signature for webhook body."""
    return hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()


@pytest.fixture
def test_repo(tmp_path: Path) -> DatabaseRepository:
    db_file = tmp_path / "test_t2.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)
    repo.seed_demo_data()
    return repo


@pytest.fixture
def demo_settings() -> ProofReturnSettings:
    return ProofReturnSettings(
        demo_mode=True,
        demo_bootstrap_key=SecretStr(VALID_BOOTSTRAP_KEY),
        demo_webhook_secret=SecretStr(DEMO_WEBHOOK_SECRET),
    )


@pytest.fixture
def live_paypal_settings() -> ProofReturnSettings:
    return ProofReturnSettings(
        demo_mode=False,
        carrier_events_manual=False,
        paypal_client_id=SecretStr("LIVE_CLIENT_ID_REAL_HEX_1234567890"),
        paypal_client_secret=SecretStr("LIVE_CLIENT_SECRET_REAL_HEX_1234567890"),
        paypal_webhook_id=SecretStr("WH-REAL-WEBHOOK-ID-1234567890"),
    )


def test_webhook_rejects_client_signature_header(test_repo: DatabaseRepository, demo_settings: ProofReturnSettings) -> None:
    """Client-controlled bypass headers must be ignored; without valid demo HMAC it must return 400."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    payload = {
        "id": "WH-TEST-FORGED-01",
        "event_type": "PAYMENT.CAPTURE.REVERSED",
        "resource": {"custom_id": "ord_demo_1"},
    }
    body_bytes = json.dumps(payload).encode("utf-8")

    # Send with client signature header that attacker previously tried to use
    resp = client.post(
        "/v1/webhooks/paypal",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Client-Signature-Bypass": "true",
        },
    )
    assert resp.status_code == 400
    assert resp.headers["content-type"] == "application/problem+json"
    assert resp.json()["code"] == "INVALID_WEBHOOK_SIGNATURE"


def test_webhook_rejects_spoofed_paypal_cert_url_without_credentials(test_repo: DatabaseRepository, demo_settings: ProofReturnSettings) -> None:
    """Spoofed paypal-cert-url prefix without credentials or demo HMAC must return 400."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    payload = {
        "id": "WH-TEST-SPOOFED-CERT-01",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {"custom_id": "ord_demo_1"},
    }
    body_bytes = json.dumps(payload).encode("utf-8")

    resp = client.post(
        "/v1/webhooks/paypal",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "paypal-transmission-id": "fake_trans_id",
            "paypal-transmission-sig": "fake_sig",
            "paypal-transmission-time": "2026-11-04T00:00:00Z",
            "paypal-cert-url": "https://api.sandbox.paypal.com/v1/fake-cert.pem",
            "paypal-auth-algo": "SHA256withRSA",
        },
    )
    assert resp.status_code == 400
    assert resp.headers["content-type"] == "application/problem+json"
    assert resp.json()["code"] == "INVALID_WEBHOOK_SIGNATURE"


def test_webhook_demo_hmac_valid_accepted(test_repo: DatabaseRepository, demo_settings: ProofReturnSettings) -> None:
    """Valid HMAC-SHA256 header in demo mode must accept webhook (200 OK)."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    payload = {
        "id": "WH-TEST-DEMO-VALID-01",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {"custom_id": "ord_demo_1"},
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = sign_webhook_body(body_bytes, DEMO_WEBHOOK_SECRET)

    resp = client.post(
        "/v1/webhooks/paypal",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Demo-Webhook-Signature": sig,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PROCESSED"
    assert data["event_id"] == "WH-TEST-DEMO-VALID-01"


def test_webhook_demo_hmac_invalid_rejected(test_repo: DatabaseRepository, demo_settings: ProofReturnSettings) -> None:
    """Invalid HMAC-SHA256 in demo mode must return 400."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    payload = {
        "id": "WH-TEST-DEMO-INVALID-01",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {"custom_id": "ord_demo_1"},
    }
    body_bytes = json.dumps(payload).encode("utf-8")

    resp = client.post(
        "/v1/webhooks/paypal",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Demo-Webhook-Signature": "invalid_hex_signature_here_1234567890",
        },
    )
    assert resp.status_code == 400
    assert resp.headers["content-type"] == "application/problem+json"
    assert resp.json()["code"] == "INVALID_WEBHOOK_SIGNATURE"


def test_webhook_live_verification_success_failure_timeout(
    test_repo: DatabaseRepository,
    live_paypal_settings: ProofReturnSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live verification handles success, rejection, and network/timeout exceptions fail-closed."""
    app = create_app(repository=test_repo, settings=live_paypal_settings, demo_mode=False)
    client = TestClient(app)

    headers = {
        "Content-Type": "application/json",
        "paypal-transmission-id": "real_trans_id",
        "paypal-transmission-sig": "real_sig",
        "paypal-transmission-time": "2026-11-04T00:00:00Z",
        "paypal-cert-url": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-123",
        "paypal-auth-algo": "SHA256withRSA",
    }
    payload = {
        "id": "WH-TEST-LIVE-01",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {"custom_id": "ord_demo_1"},
    }
    body_bytes = json.dumps(payload).encode("utf-8")

    # 1. Success from PayPal -> 200
    from backend.payments.client import PayPalSandboxClient
    monkeypatch.setattr(PayPalSandboxClient, "verify_webhook_signature_live", lambda *args, **kwargs: True)
    resp_success = client.post("/v1/webhooks/paypal", content=body_bytes, headers=headers)
    assert resp_success.status_code == 200

    # 2. Rejection from PayPal -> 400
    payload["id"] = "WH-TEST-LIVE-02"
    body_bytes2 = json.dumps(payload).encode("utf-8")
    monkeypatch.setattr(PayPalSandboxClient, "verify_webhook_signature_live", lambda *args, **kwargs: False)
    resp_rejected = client.post("/v1/webhooks/paypal", content=body_bytes2, headers=headers)
    assert resp_rejected.status_code == 400

    # 3. Timeout or Network Exception -> Fail closed (400)
    payload["id"] = "WH-TEST-LIVE-03"
    body_bytes3 = json.dumps(payload).encode("utf-8")
    def _raise_timeout(*args: Any, **kwargs: Any) -> bool:
        raise TimeoutError("PayPal API gateway timed out")
    monkeypatch.setattr(PayPalSandboxClient, "verify_webhook_signature_live", _raise_timeout)
    resp_timeout = client.post("/v1/webhooks/paypal", content=body_bytes3, headers=headers)
    assert resp_timeout.status_code == 400
    assert resp_timeout.json()["code"] == "INVALID_WEBHOOK_SIGNATURE"


def test_rejected_webhook_does_not_freeze_order(test_repo: DatabaseRepository, demo_settings: ProofReturnSettings) -> None:
    """Rejected webhook must NOT touch ledger, zero balances, or freeze order."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    order_before = test_repo.get_order("ord_demo_1")
    assert order_before is not None

    payload = {
        "id": "WH-ATTACK-FREEZE-01",
        "event_type": "PAYMENT.CAPTURE.REVERSED",
        "resource": {"custom_id": "ord_demo_1"},
    }
    body_bytes = json.dumps(payload).encode("utf-8")

    # Send forged webhook with invalid signature
    resp = client.post(
        "/v1/webhooks/paypal",
        content=body_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Client-Signature-Bypass": "true",
        },
    )
    assert resp.status_code == 400

    # Order must remain untouched
    order_after = test_repo.get_order("ord_demo_1")
    assert order_after is not None
    assert order_after.capture_amount_minor == order_before.capture_amount_minor
    # Event must NOT be recorded in processed events
    assert test_repo.get_webhook_event("WH-ATTACK-FREEZE-01") is None
