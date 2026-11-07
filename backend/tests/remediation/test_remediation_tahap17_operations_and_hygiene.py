"""Remediation tests for Tahap 17 / Task T11: Operations and Configuration Hygiene.

Audited requirements:
- Migrations run as a separate command (compose one-shot service), not on every app start (AUD-38)
- Rate limiter history is bounded (TTL eviction of idle keys) (AUD-30, AUD-39)
- Backup and restore script for Postgres plus drill and reconciliation (AUD-37, BK-01..BK-07, NFR-13)
- Pin base images by digest (AUD-38)
- /v1/simulate reports measured latency and cost, never constants (NFR-16, AUD-37)
- Single source for tier caps and jurisdiction sets (domain/constants.py, AUD-16); remove 14 unused .env.example keys; declared_grade is required (AUD-04)
- AG-01 margin accounts for calibration-set uncertainty (a calibrated model must pass in at least 9 of 10 seeded repetitions; a degraded model must fail) (RV-07)
- Compose has no credential defaults (AUD-31, AUD-38)
"""

from __future__ import annotations

import math
import random
import re
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.ai.calibration.conformal import (
    ConformalCalibrationSession,
    MondrianConformalCalibrator,
)
from backend.api.app import create_app
from backend.api.middleware import RateLimiterMiddleware
from backend.api.schemas import ReturnDeclarationRequest, SimulateRequest
from backend.config import ProofReturnSettings, get_settings
from backend.db.models import Return
from backend.db.repository import DatabaseRepository
from backend.domain.constants import (
    COUNTER_VERIFIED_DROPOFF_CAP_MINOR,
    FEE_PROHIBITED_JURISDICTIONS,
    TIER_CAPS_MINOR,
)
from backend.domain.policy import FEE_PROHIBITED_JURISDICTIONS as POLICY_FEE_JURISDICTIONS
from backend.domain.trust import (
    COUNTER_VERIFIED_DROPOFF_CAP_MINOR as TRUST_COUNTER_CAP,
    TIER_CAPS_MINOR as TRUST_TIER_CAPS,
)
from scripts.backup_restore import execute_drill

ROOT = Path(__file__).resolve().parents[3]


# ==============================================================================
# 1. Migrations separate from app start (AUD-38)
# ==============================================================================
@pytest.mark.req("AUD-38")
def test_t11_migrations_separate_from_app_start() -> None:
    """AUD-38: Migrations do not run automatically on app start when run_migrations_on_start is False."""
    settings = ProofReturnSettings(
        run_migrations_on_start=False,
        database_url="postgresql+psycopg://test:test@localhost:5432/test",
        demo_mode=False,
        carrier_events_manual=False,
    )
    assert settings.run_migrations_on_start is False

    # Verify DatabaseRepository called without run_migrations_on_init
    with patch("backend.api.app.DatabaseRepository") as mock_repo_cls:
        mock_repo = MagicMock()
        mock_repo.list_orders.return_value = []
        mock_repo_cls.return_value = mock_repo
        app = create_app(settings=settings)
        mock_repo_cls.assert_called_once_with(
            database_url=settings.database_url,
            run_migrations_on_init=False,
        )

    # Verify docker-compose.yml defines migrate service and api depends on it
    compose_text = (ROOT / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    assert "migrate:" in compose_text
    assert 'command: ["alembic", "upgrade", "head"]' in compose_text
    assert "service_completed_successfully" in compose_text
    assert 'RUN_MIGRATIONS_ON_START: "false"' in compose_text


# ==============================================================================
# 2. Rate limiter history is bounded (TTL eviction of idle keys) (AUD-30, AUD-39)
# ==============================================================================
@pytest.mark.req("AUD-30", "AUD-39")
def test_t11_rate_limiter_bounded_history_and_ttl_eviction() -> None:
    """AUD-30 & AUD-39: RateLimiterMiddleware evicts idle keys older than TTL and enforces bounded capacity."""
    app_mock = MagicMock()
    limiter = RateLimiterMiddleware(
        app=app_mock,
        requests_per_minute=10,
        window_seconds=60.0,
        max_keys=5,
        ttl_seconds=10.0,
    )

    t0 = 1000.0
    # Simulate activity on 5 keys
    for i in range(5):
        key = f"ip:10.0.0.{i}"
        limiter._history[key] = [t0]
        limiter._last_active[key] = t0

    assert len(limiter._history) == 5

    # Advance time past TTL for keys 0 and 1, but keep 2, 3, 4 active
    t1 = t0 + 15.0
    limiter._last_active["ip:10.0.0.2"] = t1
    limiter._last_active["ip:10.0.0.3"] = t1
    limiter._last_active["ip:10.0.0.4"] = t1

    evicted = limiter.evict_idle_keys(now=t1)
    assert evicted == 2  # Keys 0 and 1 were evicted
    assert "ip:10.0.0.0" not in limiter._history
    assert "ip:10.0.0.1" not in limiter._history
    assert "ip:10.0.0.2" in limiter._history

    # Now add more keys to test LRU capacity bounding
    for i in range(5, 12):
        key = f"ip:10.0.0.{i}"
        limiter._history[key] = [t1]
        limiter._last_active[key] = t1

    # Capacity eviction bounds dictionary to max_keys (5)
    limiter.evict_idle_keys(now=t1)
    assert len(limiter._history) <= 5


# ==============================================================================
# 3. Backup & restore script and drill with reconciliation (BK-01..BK-07, NFR-13)
# ==============================================================================
@pytest.mark.req("BK-01", "BK-05", "BK-06", "BK-07", "NFR-13")
def test_t11_backup_restore_script_and_reconciliation_drill() -> None:
    """BK-01..BK-07: Backup & restore drill restores clean instance and runs reconciliation suite."""
    drill_exit_code = execute_drill()
    assert drill_exit_code == 0, "Disaster recovery drill must pass with exit code 0"


# ==============================================================================
# 4. Pin base images by digest (AUD-38)
# ==============================================================================
@pytest.mark.req("AUD-38")
def test_t11_pinned_base_images_by_digest() -> None:
    """AUD-38: Base images in Dockerfile and Compose are pinned by sha256 digest."""
    dockerfile_text = (ROOT / "infra" / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"FROM\s+python:3\.12-slim-bookworm@sha256:[a-f0-9]{64}", dockerfile_text)
    assert re.search(r"ghcr\.io/astral-sh/uv:0\.6\.3@sha256:[a-f0-9]{64}", dockerfile_text)

    compose_text = (ROOT / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    assert re.search(r"pgvector/pgvector:pg16@sha256:[a-f0-9]{64}", compose_text)
    assert re.search(r"redis:7\.4-alpine@sha256:[a-f0-9]{64}", compose_text)
    assert re.search(r"minio/minio:RELEASE\.[0-9T\-Z]+@sha256:[a-f0-9]{64}", compose_text)
    assert re.search(r"temporalio/auto-setup:1\.25\.2@sha256:[a-f0-9]{64}", compose_text)


# ==============================================================================
# 5. /v1/simulate reports measured latency and cost, never constants (NFR-16, AUD-37)
# ==============================================================================
@pytest.mark.req("NFR-16", "AUD-37")
def test_t11_simulate_reports_measured_latency_and_cost() -> None:
    """NFR-16 & AUD-37: /v1/simulate dynamically measures latency and computes cost."""
    repo = DatabaseRepository()
    repo.reset_demo_database()
    app = create_app(repository=repo, demo_mode=True)
    client = TestClient(app)

    shopper_token = repo.mint_shopper_token("ord_demo_1", "shopper_1") if hasattr(repo, "mint_shopper_token") else None
    from backend.auth.tokens import mint_shopper_token, mint_staff_token
    token = mint_staff_token(user_id="staff_analyst", role="MERCHANT_ADMIN", merchant_id="merch_a")

    payload = {
        "price_minor": 45000,
        "declared_grade": "B",
        "tier": "TRUSTED",
        "has_origin_passport": True,
    }
    resp = client.post("/v1/simulate", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()

    metrics = data["cost_latency_metrics"]
    p95 = metrics["p95_eval_seconds"]
    cost = metrics["cost_per_eval_cents"]

    # Latency must be non-zero and measured
    assert isinstance(p95, float)
    assert p95 > 0.0
    assert p95 != 1.2  # Must not be previous hardcoded constant

    # Cost must be non-zero and dynamically calculated
    assert isinstance(cost, float)
    assert cost > 0.0
    assert cost != 0.05  # Must not be previous hardcoded constant


# ==============================================================================
# 6. Single source constants and declared_grade required (AUD-16, AUD-04)
# ==============================================================================
@pytest.mark.req("AUD-16", "AUD-04")
def test_t11_single_source_constants_and_declared_grade_required() -> None:
    """AUD-16 & AUD-04: Single source of constants, 14 dead keys removed, declared_grade required."""
    # Canonical constants agree
    assert TRUST_TIER_CAPS == TIER_CAPS_MINOR
    assert TRUST_COUNTER_CAP == COUNTER_VERIFIED_DROPOFF_CAP_MINOR
    assert POLICY_FEE_JURISDICTIONS == FEE_PROHIBITED_JURISDICTIONS

    # 14 dead keys removed from .env.example
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    dead_keys = [
        "TEMPORAL_HOST", "S3_BUCKET", "TSA_URL", "BEACON_URL",
        "POLICY_DEFAULTS_PATH", "RELEASE_MATRIX_PATH", "JURISDICTION_TABLE_PATH",
        "VALUE_BANDS", "EXPOSURE_CAPS", "ALPHA_ROUTE", "ALPHA_ACCUSE",
        "RETAKE_LIMITS", "MECHANISM_POLICY_VERSION", "FEATURE_FLAGS",
    ]
    for k in dead_keys:
        assert f"{k}=" not in env_example, f"Dead key {k} must not exist in .env.example"

    # ReturnDeclarationRequest requires declared_grade
    with pytest.raises(Exception):
        ReturnDeclarationRequest(
            consent_fast_lane_terms=True,
            reason_code="CHANGED_MIND",
        )

    # SimulateRequest requires declared_grade
    with pytest.raises(Exception):
        SimulateRequest(
            price_minor=40000,
            tier="TRUSTED",
        )

    # Newly initialized return has declared_grade = None
    ret = Return(
        return_id="ret_test_initial",
        order_id="ord_test",
        order_item_id="item_test",
        merchant_id="merch_a",
    )
    assert ret.declared_grade is None

    # Feasibility map query requires declared_grade
    repo = DatabaseRepository()
    repo.reset_demo_database()
    client = TestClient(create_app(repository=repo, demo_mode=True))
    from backend.auth.tokens import mint_staff_token
    token = mint_staff_token("staff_analyst", "MERCHANT_ADMIN", "merch_a")
    resp_no_grade = client.get("/v1/simulate/feasibility-map", headers={"Authorization": f"Bearer {token}"})
    assert resp_no_grade.status_code == 422  # Missing required query param


# ==============================================================================
# 7. AG-01 margin accounts for calibration-set uncertainty (RV-07)
# ==============================================================================
@pytest.mark.req("RV-07", "AG-01")
def test_t11_ag01_margin_calibration_uncertainty_seeded_repetitions() -> None:
    """RV-07: AG-01 margin accounts for calibration uncertainty; calibrated model passes >= 9/10, degraded fails 10/10."""
    def run_repetition(seed: int, degraded: bool) -> bool:
        rng = random.Random(seed)
        def gen_session(sid: str, cat: str, deg: bool) -> ConformalCalibrationSession:
            true_g = rng.choice(["A", "B", "C", "D"])
            if not deg:
                is_hard = rng.random() < 0.01
                noise = rng.uniform(0.08, 0.20) if is_hard else rng.uniform(0.001, 0.02)
            else:
                noise = rng.uniform(0.20, 0.45)
            if true_g == "A":
                probs = {"D": 1.0, "C": 0.99, "B": 0.97, "A": max(0.0, 1.0 - noise)}
            elif true_g == "B":
                probs = {"D": 1.0, "C": 0.99, "B": max(0.0, 1.0 - noise), "A": 0.05}
            elif true_g == "C":
                probs = {"D": 1.0, "C": max(0.0, 1.0 - noise), "B": 0.08, "A": 0.02}
            else:
                probs = {"D": 1.0, "C": 0.05, "B": 0.02, "A": 0.01}
            return ConformalCalibrationSession(session_id=sid, category=cat, true_grade=true_g, cum_probs=probs)

        calib_sessions = [gen_session(f"c_{i}", "electronics", deg=False) for i in range(250)]
        test_sessions = [gen_session(f"t_{i}", "electronics", deg=degraded) for i in range(250)]

        calibrator = MondrianConformalCalibrator(alpha_route=0.10, alpha_accuse=0.02)
        calibrator.fit_category("electronics", calib_sessions)
        gate_res = calibrator.verify_gate_ag01("electronics", test_sessions)
        return bool(gate_res["passed_ag01"])

    calibrated_passes = sum(run_repetition(s, degraded=False) for s in range(10))
    degraded_passes = sum(run_repetition(s, degraded=True) for s in range(10))

    assert calibrated_passes >= 9, f"Calibrated model must pass in at least 9/10 repetitions (got {calibrated_passes}/10)"
    assert degraded_passes == 0, f"Degraded model must fail all repetitions (got {degraded_passes}/10)"


# ==============================================================================
# 8. Compose has no credential defaults (AUD-31, AUD-38)
# ==============================================================================
@pytest.mark.req("AUD-31", "AUD-38")
def test_t11_compose_has_no_credential_defaults() -> None:
    """AUD-31 & AUD-38: docker-compose.yml contains zero fallback defaults (':-')."""
    compose_path = ROOT / "infra" / "docker-compose.yml"
    text = compose_path.read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        assert ":-" not in line, f"Line {i} in docker-compose.yml has fallback default ':-': {line.strip()}"
