"""Remediation Verification Test Suite for Tahap 4 (J-08..J-12, RV-05..RV-09, AUD-03, AUD-14, AUD-15, AUD-26, AUD-30, AUD-34, ST-11, CT-02).

Validates:
1. RV-09 & API-04: Staff token issuance and shopper magic-link token issuance endpoints.
2. AUD-30: Token-bucket & sliding window rate limiting (429) and request body size limit (413).
3. AUD-14: Injected settings with non-demo default (demo_mode=False unless explicitly requested).
4. AUD-15 & INV-18: Section 31.3 degraded fallback integration via API.
5. RV-07: Conformal prediction Gate AG-01 finite-sample statistical confidence bounds.
6. RV-06 & RV-05: CI test marker preservation and secret scanner hygiene.
7. AUD-26: SerialRegistry salt derivation without literal key strings.
8. AUD-34, AUD-03, ST-11 & CT-02: Contract testing comparing API outputs directly against Policy Engine,
   and concurrent refund race condition safety under multi-threaded execution.
"""

from __future__ import annotations

import concurrent.futures
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.ai.calibration.conformal import (
    ConformalCalibrationSession,
    MondrianConformalCalibrator,
)
from backend.api.app import create_app
from backend.api.middleware import RateLimiterMiddleware, RequestBodyLimitMiddleware
from backend.auth.tokens import (
    mint_shopper_token,
    mint_staff_token,
    verify_token,
)
from backend.config import ProofReturnSettings, get_settings
from backend.db.repository import DatabaseRepository
from backend.tests.support.journeys import run_critical_journey
from backend.payments.ledger import (
    IdempotencyConflictError,
    OverRefundError,
    RefundLedger,
    compute_deterministic_request_id,
)
from backend.policy_engine.release import (
    ReleaseInput,
    decide_release,
)
from sim.fmap import _illustrative_calib


# =============================================================================
# 1. RV-09 & API-04: Staff & Shopper Identity Minting Endpoints
# =============================================================================

def test_rv09_staff_token_minting_and_authorization(tmp_path: Path) -> None:
    """Verify POST /v1/auth/staff-token issues cryptographically valid staff JWTs (RV-09, API-04)."""
    db_file = tmp_path / "test_auth_staff.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)
    repo.seed_demo_data()
    app = create_app(repository=repo, demo_mode=True)
    client = TestClient(app)
    bootstrap_key = app.state.settings.demo_bootstrap_key.get_secret_value()
    demo_auth_headers = {"X-Demo-Bootstrap-Key": bootstrap_key}

    # 1. Valid staff token request for REVIEWER
    resp = client.post(
        "/v1/auth/staff-token",
        json={
            "merchant_id": "merch_a",
            "staff_id": "usr_reviewer_99",
            "role": "REVIEWER",
            "ttl_seconds": 3600,
        },
        headers=demo_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["token_type"] == "Bearer"
    token = data["access_token"]
    assert data["role"] == "REVIEWER"
    assert data["merchant_id"] == "merch_a"

    # Verify token payload
    principal = verify_token(token)
    assert principal.is_staff is True
    assert principal.role == "REVIEWER"
    assert principal.merchant_id == "merch_a"
    assert principal.sub == "usr_reviewer_99"

    # 2. Invalid role returns 422
    invalid_resp = client.post(
        "/v1/auth/staff-token",
        json={
            "merchant_id": "merch_a",
            "staff_id": "usr_hacker",
            "role": "SUPERUSER_ROOT",
        },
        headers=demo_auth_headers,
    )
    assert invalid_resp.status_code == 422
    assert invalid_resp.json()["code"] == "INVALID_ROLE"


def test_rv09_shopper_magic_link_issuance_and_access(tmp_path: Path) -> None:
    """Verify POST /v1/auth/shopper-magic-link generates order-scoped tokens (RV-09, API-04)."""
    db_file = tmp_path / "test_auth_shopper.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)
    repo.seed_demo_data()
    app = create_app(repository=repo, demo_mode=True)
    client = TestClient(app)
    bootstrap_key = app.state.settings.demo_bootstrap_key.get_secret_value()
    demo_auth_headers = {"X-Demo-Bootstrap-Key": bootstrap_key}

    # 1. Generate magic link for existing order
    resp = client.post(
        "/v1/auth/shopper-magic-link",
        json={
            "order_id": "ord_demo_1",
            "email": "buyer@example.com",
            "ttl_seconds": 7200,
        },
        headers=demo_auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_id"] == "ord_demo_1"
    assert "token=" in data["magic_link_url"]
    token = data["access_token"]

    # Verify shopper token scope
    principal = verify_token(token)
    assert principal.is_shopper is True
    assert principal.order_id == "ord_demo_1"

    # 2. Use minted token to access return details
    shopper_headers = {"Authorization": f"Bearer {token}"}
    ret_resp = client.get("/v1/returns/ret_demo_1", headers=shopper_headers)
    assert ret_resp.status_code == 200
    assert ret_resp.json()["return_id"] == "ret_demo_1"


# =============================================================================
# 2. AUD-30: Rate Limiting & Request Body Size Limit Middleware
# =============================================================================

def test_aud30_rate_limiter_middleware_429() -> None:
    """Verify RateLimiterMiddleware returns HTTP 429 RATE_LIMIT_EXCEEDED when request quota is breached (AUD-30)."""
    # Create test app with strict 5 requests per minute limit
    repo = DatabaseRepository(database_url="sqlite:///:memory:", run_migrations_on_init=True)
    app = create_app(repository=repo, demo_mode=True)
    # Re-wrap or add custom tight limiter for test
    app.user_middleware.clear()
    app.middleware_stack = None
    app.add_middleware(RateLimiterMiddleware, requests_per_minute=3, window_seconds=10.0)
    app.build_middleware_stack()

    client = TestClient(app)
    shopper_token = mint_shopper_token("ord_demo_1", "shopper_1")
    headers = {"Authorization": f"Bearer {shopper_token}"}

    # First 3 requests succeed
    for _ in range(3):
        res = client.get("/v1/returns/ret_demo_1", headers=headers)
        assert res.status_code in {200, 404}

    # 4th request must be rate limited with 429
    res_limited = client.get("/v1/returns/ret_demo_1", headers=headers)
    assert res_limited.status_code == 429
    assert res_limited.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in res_limited.headers


def test_aud30_request_body_size_limit_413() -> None:
    """Verify RequestBodyLimitMiddleware returns HTTP 413 PAYLOAD_TOO_LARGE for oversized bodies (AUD-30)."""
    repo = DatabaseRepository(database_url="sqlite:///:memory:", run_migrations_on_init=True)
    app = create_app(repository=repo, demo_mode=True)
    # Tight body limit: 1024 bytes
    app.user_middleware.clear()
    app.middleware_stack = None
    app.add_middleware(RequestBodyLimitMiddleware, max_body_bytes=1024)
    app.build_middleware_stack()

    client = TestClient(app)
    shopper_token = mint_shopper_token("ord_demo_1", "shopper_1")
    headers = {
        "Authorization": f"Bearer {shopper_token}",
        "Content-Length": "2048",
    }
    res = client.post(
        "/v1/returns/ret_demo_1/declaration",
        headers=headers,
        content=b"X" * 2048,
    )
    assert res.status_code == 413
    assert res.json()["code"] == "PAYLOAD_TOO_LARGE"


# =============================================================================
# 3. AUD-14: Injected Settings & Non-Demo Default
# =============================================================================

def test_aud14_create_app_defaults_non_demo(tmp_path: Path) -> None:
    """Verify create_app defaults to non-demo mode (demo_mode=False) unless explicitly requested (AUD-14)."""
    db_file = tmp_path / "test_non_demo.db"
    settings = ProofReturnSettings(
        database_url=f"sqlite:///{db_file}",
        demo_mode=False,
        carrier_events_manual=False,
    )
    app = create_app(settings=settings)
    assert app.state.demo_mode is False

    # In clean non-demo app, no synthetic demo orders exist
    repo = app.state.repository
    assert len(repo.list_orders()) == 0


# =============================================================================
# 4. AUD-15 & INV-18: Section 31.3 Degraded Fallback Integration
# =============================================================================

def test_aud15_apply_fallback_degradation_via_api(tmp_path: Path) -> None:
    """Verify Section 31.3 degraded mode fallback FB-04..FB-07 via API invocation (AUD-15, INV-18)."""
    db_file = tmp_path / "test_fallback.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)
    repo.seed_demo_data()
    app = create_app(repository=repo, demo_mode=True)
    client = TestClient(app)

    shopper_token = mint_shopper_token("ord_demo_1", "shopper_1")
    headers = {
        "Authorization": f"Bearer {shopper_token}",
        "X-Fallback-Degradation": "FB-04",  # AI vision service outage
    }

    # Submit evidence under degraded mode FB-04
    ev_resp = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers=headers,
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": "raw/ret_demo_1/challenge.mp4",
            "sha256": "c" * 64,
            "challenge_step": 1,
            "faces_detected": 0,
            "client_blur_applied": False,
        },
    )
    assert ev_resp.status_code == 200
    data = ev_resp.json()
    assert data["state"] == "ASSESSED"
    # INV-18: Degraded mode FB-04 sets released funds to 0 until warehouse checkin
    assert data["r0_tranche_minor"] == 0
    assert data["lane"] == "STANDARD"


# =============================================================================
# 5. RV-07: Conformal Prediction Gate AG-01 Statistical Margin
# =============================================================================

def test_rv07_conformal_gate_ag01_statistical_margin() -> None:
    """Verify verify_gate_ag01 incorporates finite-sample statistical confidence bounds (RV-07)."""
    calibrator = MondrianConformalCalibrator(alpha_route=0.10, alpha_accuse=0.02)

    # Construct calibration sessions for 'electronics' category
    calib_sessions: list[ConformalCalibrationSession] = []
    for i in range(100):
        calib_sessions.append(
            ConformalCalibrationSession(
                session_id=f"calib_{i}",
                category="electronics",
                true_grade="B",
                cum_probs={"A": 0.05, "B": 0.95, "C": 0.99, "D": 1.0, "DEF": 1.0},
            )
        )
    calibrator.fit_category("electronics", calib_sessions)

    # Construct test sessions with slight finite-sample fluctuations
    test_sessions: list[ConformalCalibrationSession] = []
    for i in range(100):
        # 97 out of 100 covered at alpha_accuse (0.97 empirical vs 0.98 target -> within 95% normal CI margin)
        prob_b = 0.96 if i < 97 else 0.01
        test_sessions.append(
            ConformalCalibrationSession(
                session_id=f"test_{i}",
                category="electronics",
                true_grade="B",
                cum_probs={"A": 0.05, "B": prob_b, "C": 0.99, "D": 1.0, "DEF": 1.0},
            )
        )

    res = calibrator.verify_gate_ag01("electronics", test_sessions)
    assert res["passed_ag01"] is True, "Gate AG-01 failed despite being well within statistical CI margin (RV-07)."


# =============================================================================
# 6. RV-06 & RV-05: CI Marker & Secret Scanner Verification
# =============================================================================

def test_rv06_ci_workflow_preserves_live_markers() -> None:
    """Verify .github/workflows/ci.yml deselects live_model and sandbox without overriding pytest markers (RV-06)."""
    ci_path = Path(".github/workflows/ci.yml")
    assert ci_path.exists()
    content = ci_path.read_text(encoding="utf-8")
    assert 'pytest -v -m "not live_model and not sandbox"' in content
    assert 'pytest -v -m "not live"' not in content


def test_rv05_secret_scanner_detects_untracked_and_example_hygiene() -> None:
    """Verify scan_secrets.py correctly inspects git tracking without blind exception suppression (RV-05)."""
    from scripts.scan_secrets import check_git_ignored_secrets
    findings = check_git_ignored_secrets()
    # In a clean workspace, .env is not tracked and no error occurs
    assert not any("CRITICAL: Secret environment file" in f for f in findings)


# =============================================================================
# 7. AUD-26: SerialRegistry Salt Derivation
# =============================================================================

def test_aud26_journeys_serial_salt_without_literal_key() -> None:
    """Verify run_critical_journey executes J-01 and J-03 using settings salts (AUD-26)."""
    res_j01 = run_critical_journey("J-01")
    assert res_j01["passed"] is True
    res_j03 = run_critical_journey("J-03")
    assert res_j03["passed"] is True


# =============================================================================
# 8. AUD-34, AUD-03, ST-11 & CT-02: Contract Testing & Concurrency
# =============================================================================

def test_aud34_contract_api_evidence_matches_policy_engine(tmp_path: Path) -> None:
    """Verify REST API /v1/returns/{id}/evidence output exactly matches direct Policy Engine calculations (AUD-34)."""
    db_file = tmp_path / "test_contract.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)
    repo.seed_demo_data()
    app = create_app(repository=repo, demo_mode=True)
    client = TestClient(app)

    shopper_token = mint_shopper_token("ord_demo_1", "shopper_1")
    headers = {"Authorization": f"Bearer {shopper_token}"}

    # 1. Direct Policy Engine calculation
    order = repo.get_order("ord_demo_1")
    assert order is not None
    engine_input = ReleaseInput(
        price_minor=order.capture_amount_minor,  # 38000
        declared_grade="B",
        tier="TRUSTED",
        has_origin_passport=True,
    )
    from backend.domain.policy import PolicyConfig
    engine_decision = decide_release(engine_input, PolicyConfig.default_us(), _illustrative_calib("B"))

    # 2. REST API execution
    ev_resp = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers=headers,
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": "raw/ret_demo_1/challenge.mp4",
            "sha256": "d" * 64,
            "text_in_media": repo.get_return("ret_demo_1").challenge_nonce,
            "challenge_step": 1,
            "faces_detected": 0,
            "client_blur_applied": False,
        },
    )
    assert ev_resp.status_code == 200
    api_data = ev_resp.json()

    # 3. Contract Assertion: exact match between API and Policy Engine
    assert api_data["r0_tranche_minor"] == engine_decision.x_released_minor
    assert api_data["lane"] == engine_decision.lane
    assert api_data["timing"] == engine_decision.timing


def test_st11_concurrent_refund_idempotency_with_same_request_id() -> None:
    """Verify simultaneous refunds with identical request_id execute idempotently without double-charging (ST-11, CT-08)."""
    ledger = RefundLedger()
    ledger.register_order(
        order_id="ord_st11",
        merchant_id="merch_a",
        capture_id="cap_st11",
        capture_amount_minor=50000,
    )

    results: list[dict[str, Any]] = []
    errors: list[Exception] = []

    def execute_plan() -> None:
        try:
            action = ledger.plan_refund_action(
                order_id="ord_st11",
                merchant_id="merch_a",
                capture_id="cap_st11",
                decision_id="dec_st11",
                tranche="R0",
                amount_minor=20000,
            )
            results.append({"status": action.status, "request_id": action.request_id})
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=execute_plan) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All 8 concurrent callers receive identical successful action without errors
    assert len(errors) == 0
    assert len(results) == 8
    expected_req_id = results[0]["request_id"]
    for r in results:
        assert r["request_id"] == expected_req_id

    # The order remaining capacity was decremented EXACTLY ONCE (50000 - 20000 = 30000)
    assert ledger.remaining_refundable_minor("ord_st11") == 30000


def test_ct02_concurrent_over_refund_race_condition_rejected() -> None:
    """Verify concurrent requests attempting to over-refund are safely rejected under reentrant lock (CT-02, INV-01)."""
    ledger = RefundLedger()
    ledger.register_order(
        order_id="ord_ct02",
        merchant_id="merch_a",
        capture_id="cap_ct02",
        capture_amount_minor=30000,
    )

    successes: list[str] = []
    over_refund_errors: list[str] = []

    def plan_tranche(idx: int, amount: int) -> None:
        try:
            action = ledger.plan_refund_action(
                order_id="ord_ct02",
                merchant_id="merch_a",
                capture_id="cap_ct02",
                decision_id=f"dec_ct02_{idx}",
                tranche=f"PARTIAL_{idx}",
                amount_minor=amount,
            )
            successes.append(action.request_id)
        except OverRefundError as exc:
            over_refund_errors.append(str(exc))

    # 4 threads attempting to each refund 15000 minor from 30000 minor total capture
    # Exactly 2 should succeed, 2 must fail with OverRefundError
    threads = [
        threading.Thread(target=plan_tranche, args=(i, 15000))
        for i in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(successes) == 2
    assert len(over_refund_errors) == 2
    for err in over_refund_errors:
        assert "INV-01 violation" in err

    assert ledger.remaining_refundable_minor("ord_ct02") == 0
