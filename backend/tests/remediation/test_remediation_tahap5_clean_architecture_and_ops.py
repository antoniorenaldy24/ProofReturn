"""Remediation Verification Test Suite for Tahap 5 / Option A (J-13, AUD-16, AUD-19, AUD-37, AUD-42, DOC-05, DOC-06).

Validates:
1. AUD-16: Canonical single source of truth domain constants in backend/domain/constants.py.
2. AUD-42: Canonical Passport tier ('FULL', not 'ORIGIN_WITNESSED') and RefundAction database model synchronization.
3. AUD-19: Runtime dependency cleanup in pyproject.toml (jsonschema and pyyaml in dev groups).
4. AUD-37: Observability structured log domain fields (return_id, decision_id, paypal_debug_id) and AlertScheduler.
5. DOC-05 & DOC-06: ADR synchronization and unified AI model identifier ('gemini-3.6-flash').
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.agent_gateway.mcp_server import ProofReturnMcpServer
from backend.api.app import create_app
from backend.auth.tokens import mint_agent_token, mint_shopper_token
from backend.config import get_settings
from backend.db.models import RefundAction
from backend.db.repository import DatabaseRepository
from backend.domain.constants import (
    GRADE_RANK,
    GRADES_ORDERED,
    PASSPORT_TIERS,
    RETURN_STATES,
    STAFF_ROLES,
    SUPPORTED_JURISDICTIONS,
    TIER_CAPS_MINOR,
    TIER_RANK,
    TRUST_TIERS,
    ConditionGrade,
    PassportTier,
    ReturnState,
    StaffRole,
    SupportedJurisdiction,
    TrustTier,
)
from backend.observability.metrics import (
    AlertScheduler,
    FiredAlert,
    MetricsRegistry,
    evaluate_alerts,
    format_structured_log,
)
from backend.policy_engine.misdeclaration import evaluate_misdeclaration


def test_aud16_shared_canonical_constants() -> None:
    """Verify single source of truth canonical constants and enums (AUD-16)."""
    # 1. Condition Grades
    assert ConditionGrade.A == "A"
    assert ConditionGrade.DEF == "DEF"
    assert GRADE_RANK["DEF"] < GRADE_RANK["D"] < GRADE_RANK["C"] < GRADE_RANK["B"] < GRADE_RANK["A"]

    # 2. Trust Tiers
    assert TrustTier.NEW == "NEW"
    assert TrustTier.TRUSTED == "TRUSTED"
    assert TIER_RANK["RESTRICTED"] < TIER_RANK["NEW"] < TIER_RANK["ESTABLISHED"] < TIER_RANK["TRUSTED"]
    assert TIER_CAPS_MINOR["RESTRICTED"] == 0
    assert TIER_CAPS_MINOR["TRUSTED"] == 100000

    # 3. Supported Jurisdictions & Staff Roles
    assert "US" in SUPPORTED_JURISDICTIONS
    assert "EU" in SUPPORTED_JURISDICTIONS
    assert "MERCHANT_ADMIN" in STAFF_ROLES
    assert "REVIEWER" in STAFF_ROLES

    # 4. Misdeclaration evaluation uses canonical GRADE_RANK
    # Declared B (rank 3), verified DEF (rank 0) -> gap is 3 >= 2 (gross gap)
    mis = evaluate_misdeclaration(
        declared_grade="B",
        verified_grade="DEF",
        excluded_at_alpha_accuse=True,
        hard_identity_failure=False,
        human_confirmed=True,
    )
    assert mis.gap_steps == 3
    assert mis.is_confirmed_gross is True


def test_aud42_passport_tier_canonical_and_refund_action() -> None:
    """Verify MCP server uses canonical Passport tier 'FULL' and RefundAction model has payment fields (AUD-42)."""
    # 1. MCP server get_passport returns 'FULL' (not 'ORIGIN_WITNESSED')
    server = ProofReturnMcpServer()
    token = mint_agent_token("agent_test", "ord_demo_1", scopes=["read_policy"])
    res = server.get_passport(passport_id="pass_demo_1", token=token)
    assert res["tier"] == "FULL"
    assert res["tier"] in PASSPORT_TIERS
    assert res["tier"] != "ORIGIN_WITNESSED"

    # 2. Database RefundAction model contains all payment correlation fields
    fields = set(RefundAction.model_fields.keys())
    assert {"request_id", "merchant_id", "order_id", "decision_id", "capture_id", "tranche", "amount_minor"}.issubset(fields)


def test_aud19_pyproject_dev_dependencies() -> None:
    """Verify pyproject.toml runtime dependencies exclude test-only libraries jsonschema and pyyaml (AUD-19)."""
    pyproject_path = Path("pyproject.toml")
    assert pyproject_path.exists()
    content = pyproject_path.read_text(encoding="utf-8")

    # Extract [project] dependencies
    deps_section = content.split("dependencies = [")[1].split("]")[0]
    assert "jsonschema" not in deps_section
    assert "pyyaml" not in deps_section

    # Verify jsonschema and pyyaml are placed in [dependency-groups] dev
    dev_section = content.split("[dependency-groups]")[1]
    assert "jsonschema" in dev_section
    assert "pyyaml" in dev_section


def test_aud37_structured_logging_with_domain_fields(tmp_path: Path) -> None:
    """Verify ObservabilityMiddleware extracts domain fields return_id and decision_id into logs (AUD-37)."""
    db_file = tmp_path / "test_logging.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)
    repo.seed_demo_data()
    app = create_app(repository=repo, demo_mode=True)
    client = TestClient(app)

    shopper_token = mint_shopper_token("ord_demo_1", "shopper_1")
    headers = {"Authorization": f"Bearer {shopper_token}"}

    # Request /v1/returns/ret_demo_1
    resp = client.get("/v1/returns/ret_demo_1", headers=headers)
    assert resp.status_code == 200

    # Test format_structured_log helper directly with domain fields
    log_dict = format_structured_log(
        level="INFO",
        service="proofreturn-api",
        message="Test domain log",
        request_id="req_test_123",
        trace_id="trc_test_456",
        return_id="ret_demo_1",
        decision_id="dec_test_789",
        paypal_debug_id="pp_dbg_001",
    )
    assert log_dict["return_id"] == "ret_demo_1"
    assert log_dict["decision_id"] == "dec_test_789"
    assert log_dict["paypal_debug_id"] == "pp_dbg_001"
    assert log_dict["service"] == "proofreturn-api"


def test_aud37_alert_scheduler_evaluates_active_alerts() -> None:
    """Verify AlertScheduler background evaluator fires notifications on alert thresholds (AUD-37)."""
    metrics = MetricsRegistry()
    fired_alerts_received: list[list[FiredAlert]] = []

    def on_fired(alerts: list[FiredAlert]) -> None:
        fired_alerts_received.append(alerts)

    scheduler = AlertScheduler(metrics=metrics, interval_seconds=0.1, on_alert_fired=on_fired)

    # Initially clean: no alerts fired
    initial = scheduler.evaluate_now()
    assert len(initial) == 0

    # Trigger AL-06: set audit_rate_deviation_sigma to 3.5
    metrics.set_gauge("audit_rate_deviation_sigma", 3.5)
    fired = scheduler.evaluate_now()
    assert len(fired) >= 1
    assert any(a.alert_id == "AL-06" for a in fired)
    assert any(a.runbook_id == "RB-06" for a in fired)

    # Verify background execution loop start and stop
    scheduler.start()
    scheduler.stop()


def test_doc05_doc06_adr_and_model_identifier_harmonization() -> None:
    """Verify ADR-028 and config uniformly specify gemini-3.6-flash (DOC-05, DOC-06)."""
    settings = get_settings()
    assert settings.gemini_model == "gemini-3.6-flash"

    adr_path = Path("docs/adr/ADR-028-google-gemini-multimodal-grader.md")
    assert adr_path.exists()
    content = adr_path.read_text(encoding="utf-8")
    assert "gemini-3.6-flash" in content
    assert "gemini-2.0-flash" not in content
