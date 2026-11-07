"""Tests for TASK T1: Close open token issuance and forced demo mode (RV2-01 CRITICAL, AUD-14)."""

import os
from pathlib import Path
import pytest
from pydantic import SecretStr, ValidationError
from starlette.testclient import TestClient

from backend.api.app import create_app
from backend.config import ProofReturnSettings, reset_settings_cache
from backend.db.repository import DatabaseRepository


VALID_BOOTSTRAP_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
WRONG_BOOTSTRAP_KEY = "wrongkeywrongkeywrongkeywrongkeywrongkeywrongkeywrongkeywrongkey"


@pytest.fixture
def test_repo(tmp_path: Path) -> DatabaseRepository:
    db_file = tmp_path / "test_t1.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)
    repo.seed_demo_data()
    return repo


@pytest.fixture
def demo_settings() -> ProofReturnSettings:
    return ProofReturnSettings(
        demo_mode=True,
        demo_bootstrap_key=SecretStr(VALID_BOOTSTRAP_KEY),
    )


@pytest.fixture
def prod_settings() -> ProofReturnSettings:
    return ProofReturnSettings(
        demo_mode=False,
        carrier_events_manual=False,
    )


def test_staff_token_requires_bootstrap_key_in_demo(test_repo: DatabaseRepository, demo_settings: ProofReturnSettings) -> None:
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    body = {
        "merchant_id": "merch_demo_1",
        "staff_id": "usr_reviewer_1",
        "role": "REVIEWER",
        "ttl_seconds": 3600,
    }

    # 1. No header -> 401
    resp_no_header = client.post("/v1/auth/staff-token", json=body)
    assert resp_no_header.status_code == 401
    assert resp_no_header.headers["content-type"] == "application/problem+json"

    # 2. Wrong key -> 401
    resp_wrong = client.post(
        "/v1/auth/staff-token",
        json=body,
        headers={"X-Demo-Bootstrap-Key": WRONG_BOOTSTRAP_KEY},
    )
    assert resp_wrong.status_code == 401
    assert resp_wrong.headers["content-type"] == "application/problem+json"

    # 3. Correct key -> 200 with demo_only=True and TTL clamped to at most 8 hours
    resp_ok = client.post(
        "/v1/auth/staff-token",
        json=body,
        headers={"X-Demo-Bootstrap-Key": VALID_BOOTSTRAP_KEY},
    )
    assert resp_ok.status_code == 200
    data = resp_ok.json()
    assert data["token_type"] == "Bearer"
    assert "access_token" in data
    assert data["demo_only"] is True
    assert data["expires_in"] <= 28800


def test_magic_link_requires_bootstrap_key_in_demo(test_repo: DatabaseRepository, demo_settings: ProofReturnSettings) -> None:
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    body = {
        "order_id": "ord_demo_1",
        "email": "buyer@example.com",
        "ttl_seconds": 3600,
    }

    # 1. No header -> 401
    resp_no_header = client.post("/v1/auth/shopper-magic-link", json=body)
    assert resp_no_header.status_code == 401
    assert resp_no_header.headers["content-type"] == "application/problem+json"

    # 2. Wrong key -> 401
    resp_wrong = client.post(
        "/v1/auth/shopper-magic-link",
        json=body,
        headers={"X-Demo-Bootstrap-Key": WRONG_BOOTSTRAP_KEY},
    )
    assert resp_wrong.status_code == 401
    assert resp_wrong.headers["content-type"] == "application/problem+json"

    # 3. Correct key -> 200 with demo_only=True and TTL clamped to at most 24 hours
    resp_ok = client.post(
        "/v1/auth/shopper-magic-link",
        json=body,
        headers={"X-Demo-Bootstrap-Key": VALID_BOOTSTRAP_KEY},
    )
    assert resp_ok.status_code == 200
    data = resp_ok.json()
    assert data["token_type"] == "Bearer"
    assert "access_token" in data
    assert "magic_link_url" in data
    assert data["demo_only"] is True
    assert data["expires_in"] <= 86400


def test_staff_token_disabled_outside_demo(test_repo: DatabaseRepository, prod_settings: ProofReturnSettings) -> None:
    app = create_app(repository=test_repo, settings=prod_settings, demo_mode=False)
    client = TestClient(app)

    body = {
        "merchant_id": "merch_demo_1",
        "staff_id": "usr_reviewer_1",
        "role": "REVIEWER",
    }
    resp = client.post(
        "/v1/auth/staff-token",
        json=body,
        headers={"X-Demo-Bootstrap-Key": VALID_BOOTSTRAP_KEY},
    )
    assert resp.status_code == 404


def test_magic_link_outside_demo_never_returns_token(test_repo: DatabaseRepository, prod_settings: ProofReturnSettings) -> None:
    app = create_app(repository=test_repo, settings=prod_settings, demo_mode=False)
    client = TestClient(app)

    body = {
        "order_id": "ord_demo_1",
        "email": "buyer@example.com",
    }
    resp = client.post("/v1/auth/shopper-magic-link", json=body)
    assert resp.status_code == 202
    data = resp.json()
    assert "access_token" not in data
    assert "magic_link_url" not in data
    assert data.get("status") == "ACCEPTED"


def test_module_app_respects_demo_mode_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("CARRIER_EVENTS_MANUAL", "false")
    reset_settings_cache()
    db_file = tmp_path / "test_module_app.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)
    app = create_app(repository=repo)
    assert app.state.demo_mode is False


def test_demo_mode_without_bootstrap_key_fails_closed() -> None:
    # 1. Missing bootstrap key when demo_mode=True -> ValueError
    with pytest.raises((ValueError, ValidationError)):
        ProofReturnSettings(demo_mode=True, demo_bootstrap_key=SecretStr(""))

    # 2. Too short bootstrap key (< 32 bytes) -> ValueError
    with pytest.raises((ValueError, ValidationError)):
        ProofReturnSettings(demo_mode=True, demo_bootstrap_key=SecretStr("short_key_16byte"))

    # 3. Placeholder bootstrap key -> ValueError
    with pytest.raises((ValueError, ValidationError)):
        ProofReturnSettings(
            demo_mode=True,
            demo_bootstrap_key=SecretStr("replace_with_at_least_32_bytes_random_hex_key"),
        )
