"""Tests for TASK T10: ST-01 through the system in PayPal Sandbox (AUD-02 HIGH, ARC-19).

Verifies:
1. Dry-run mode drives the full system path using FakePayPalSandboxClient.
2. Order 1: Real order -> capture -> return flow -> outbox dispatch -> PayPal capture refunds match DB actions.
3. Order 2 (Dispute Scenario): Real order -> capture -> R0 refund confirmed -> CUSTOMER.DISPUTE.CREATED ->
   order frozen -> outbox run -> zero subsequent refunds created at PayPal.
4. Output JSON evidence written with real/synthetic IDs and no secret tokens.
5. st01-system-run-R3-SUPERSEDED.txt contains proper superseded header.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from backend.db.repository import DatabaseRepository
from scripts.st01_system_run import run_st01_flow


@pytest.mark.req("AUD-02", "ST-01", "FR-75", "INV-01", "INV-03")
def test_st01_dry_run_system_execution(tmp_path: Path, reset_db: Any) -> None:
    """Verify that ST-01 dry-run executes cleanly across all lifecycle steps and passes CI."""
    evidence_json = tmp_path / "st01-test-evidence.json"

    result = run_st01_flow(
        dry_run=True,
        auto_approve=True,
        output_path=evidence_json,
    )

    # 1. Evidence document verified
    assert result["test_id"] == "ST-01"
    assert result["round"] == "R4"
    assert result["mode"] == "dry-run"
    assert evidence_json.exists()

    with open(evidence_json, "r", encoding="utf-8") as f:
        doc = json.load(f)

    # 2. Order 1 Happy Path
    ord1 = doc["order_1_happy_path"]
    assert ord1["capture_status"] == "COMPLETED"
    assert ord1["confirmed_actions_count"] == 2
    tranches = {a["tranche"] for a in ord1["actions"]}
    assert "R0" in tranches
    assert "SETTLEMENT" in tranches
    assert ord1["paypal_capture_verification"]["refunds_count"] == 2
    assert ord1["paypal_capture_verification"]["status"] == "COMPLETED"

    # 3. Order 2 Dispute Scenario & Freeze
    ord2 = doc["order_2_dispute_scenario"]
    assert ord2["capture_status"] == "COMPLETED"
    assert ord2["order_frozen_by_dispute"] is True
    assert ord2["pre_dispute_refunds_count_at_paypal"] == 1
    assert ord2["post_freeze_refunds_count_at_paypal"] == 1
    assert ord2["no_further_refund_verified"] is True

    # 4. No secrets leaked
    raw_text = evidence_json.read_text(encoding="utf-8")
    for forbidden in ["client_secret", "access_token", "Bearer ", "password", "bootstrap_key"]:
        assert forbidden not in raw_text


def test_st01_r3_superseded_file_format() -> None:
    """Verify that st01-system-run-R3-SUPERSEDED.txt exists and contains the required supersede notice."""
    superseded_file = Path("docs/evidence/st01-system-run-R3-SUPERSEDED.txt")
    assert superseded_file.is_file(), "st01-system-run-R3-SUPERSEDED.txt must exist"

    first_line = superseded_file.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == "Narrative only; superseded by st01-R4.json.", (
        f"Expected supersede header, got: {first_line}"
    )
