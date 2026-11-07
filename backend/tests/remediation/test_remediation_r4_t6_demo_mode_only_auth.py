"""Round 4 Task T6-B: Declare the hackathon release as DEMO_MODE only (RV3-05 MEDIUM, API-04)."""

from __future__ import annotations

import logging
import pathlib
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.api.app import create_app
from backend.config import ProofReturnSettings
from backend.db.models import Order
from backend.db.repository import DatabaseRepository

VALID_BOOTSTRAP_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
DEMO_WEBHOOK_SECRET = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"


def _make_settings(db_url: str, *, demo_mode: bool) -> ProofReturnSettings:
    return ProofReturnSettings(
        database_url=db_url,
        demo_mode=demo_mode,
        mode="judge",
        enable_scheduler=False,
        carrier_events_manual=False,
        demo_bootstrap_key=SecretStr(VALID_BOOTSTRAP_KEY),
        demo_webhook_secret=SecretStr(DEMO_WEBHOOK_SECRET),
    )


@pytest.mark.req("RV3-05", "API-04")
def test_ready_reports_demo_only_outside_demo_and_logs_startup_warning(
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When DEMO_MODE is false, the app logs AUTH_NOT_AVAILABLE_OUTSIDE_DEMO and /v1/ready reports 'auth': 'demo_only'."""
    db_url = f"sqlite:///{tmp_path / 't6_ready.db'}"
    settings = _make_settings(db_url, demo_mode=False)
    repo = DatabaseRepository(database_url=db_url)

    with caplog.at_level(logging.WARNING):
        app = create_app(settings=settings, repository=repo, demo_mode=False)

    # 1. Verify startup warning logged
    warning_logs = [rec.message for rec in caplog.records if rec.levelno >= logging.WARNING]
    assert any("AUTH_NOT_AVAILABLE_OUTSIDE_DEMO" in msg for msg in warning_logs), (
        f"Expected AUTH_NOT_AVAILABLE_OUTSIDE_DEMO warning in logs, found: {warning_logs}"
    )

    # 2. Verify /v1/ready reports "auth": "demo_only"
    client = TestClient(app)
    resp = client.get("/v1/ready")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "ready"
    assert data["demo_mode"] is False
    assert data.get("auth") == "demo_only"


@pytest.mark.req("RV3-05", "API-04")
def test_no_endpoint_returns_a_token_outside_demo(
    tmp_path: pathlib.Path,
) -> None:
    """Outside DEMO_MODE, no endpoint returns an access or bearer token (RV3-05)."""
    db_url = f"sqlite:///{tmp_path / 't6_notoken.db'}"
    settings = _make_settings(db_url, demo_mode=False)
    repo = DatabaseRepository(database_url=db_url)
    # Seed an order to test shopper magic-link order lookup
    repo.save_order(
        Order(
            order_id="ord_t6_real",
            merchant_id="merch_a",
            account_id="shopper_real",
            policy_version="pol_electronics_us_v1",
            capture_id="CAP-REAL-T6",
            capture_amount_minor=10000,
            currency="USD",
        )
    )

    app = create_app(settings=settings, repository=repo, demo_mode=False)
    client = TestClient(app)

    # 1. Staff token endpoint is disabled outside demo mode -> 404
    r_staff = client.post(
        "/v1/auth/staff-token",
        json={"merchant_id": "merch_a", "role": "MERCHANT_ADMIN", "staff_id": "admin_01"},
    )
    assert r_staff.status_code == 404
    assert "token" not in r_staff.text.lower() or "not found" in r_staff.text.lower()
    assert "access_token" not in r_staff.json()

    # 2. Shopper magic link endpoint records delivery request -> 202, NEVER returns a token or magic_link_url
    r_shopper = client.post(
        "/v1/auth/shopper-magic-link",
        json={"order_id": "ord_t6_real", "shopper_id": "shopper_real"},
    )
    assert r_shopper.status_code == 202, r_shopper.text
    data_shopper = r_shopper.json()
    assert data_shopper["status"] == "ACCEPTED"
    assert "token" not in data_shopper
    assert "magic_link_url" not in data_shopper

    # 3. Agent tokens endpoint requires authenticated shopper principal -> 401
    r_agent = client.post(
        "/v1/agent/tokens",
        json={"order_id": "ord_t6_real", "scopes": ["read_return"], "agent_label": "Bot"},
    )
    assert r_agent.status_code == 401
    assert "token" not in r_agent.json()


@pytest.mark.req("RV3-05", "API-04")
def test_demo_mode_retains_token_minting_with_bootstrap_key(
    tmp_path: pathlib.Path,
) -> None:
    """When DEMO_MODE is true, token minting remains fully functional with X-Demo-Bootstrap-Key."""
    db_url = f"sqlite:///{tmp_path / 't6_demo.db'}"
    settings = _make_settings(db_url, demo_mode=True)
    repo = DatabaseRepository(database_url=db_url)
    repo.seed_demo_data()

    app = create_app(settings=settings, repository=repo, demo_mode=True)
    client = TestClient(app)

    # /v1/ready reports demo_mode: True
    r_ready = client.get("/v1/ready")
    assert r_ready.status_code == 200
    assert r_ready.json()["demo_mode"] is True
    assert r_ready.json().get("auth") in {"demo", "ready", None}

    # Staff token succeeds with valid bootstrap key
    r_staff = client.post(
        "/v1/auth/staff-token",
        headers={"X-Demo-Bootstrap-Key": VALID_BOOTSTRAP_KEY},
        json={"merchant_id": "merch_a", "role": "MERCHANT_ADMIN", "staff_id": "admin_demo"},
    )
    assert r_staff.status_code == 200
    assert "access_token" in r_staff.json()

    # Shopper magic link succeeds with valid bootstrap key
    r_shopper = client.post(
        "/v1/auth/shopper-magic-link",
        headers={"X-Demo-Bootstrap-Key": VALID_BOOTSTRAP_KEY},
        json={"order_id": "ord_demo_1"},
    )
    assert r_shopper.status_code == 200
    assert "access_token" in r_shopper.json()
