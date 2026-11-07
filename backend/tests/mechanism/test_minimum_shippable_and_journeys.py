"""Tests for Database Schema (Section 30), Remaining Minimum Shippable Mechanism (F-07..F-15), and All 14 Critical Journeys J-01..J-14 (Section 35.1)."""

from __future__ import annotations

import pytest

from backend.db.schema import CANONICAL_TABLES, get_initial_migration_sql
from backend.domain.appeals import AppealPortal, SameReviewerAppealError
from backend.domain.disposition import evaluate_disposition_options
from backend.domain.evidence_pack import generate_evidence_pack
from backend.tests.support.journeys import run_critical_journey
from backend.domain.resale import create_certified_open_box_listing
from backend.domain.serial_registry import SerialRegistry
from backend.domain.sla_and_holds import compute_sla_breach_credit, validate_rental_duration_days


@pytest.mark.req("INV-01", "INV-09", "FR-09")
def test_canonical_database_schema_20_tables_and_constraints() -> None:
    """Section 10.4 & Section 30: Verify all 22 canonical tables and SQL constraints/triggers exist."""
    assert len(CANONICAL_TABLES) == 22
    sql = get_initial_migration_sql()
    for table_name in CANONICAL_TABLES:
        assert f"CREATE TABLE {table_name}" in sql
    # INV-01 check constraint, INV-09 append-only trigger, CT-01 partial unique index
    assert "chk_inv01_cumulative_refund" in sql
    assert "trg_passport_events_append_only" in sql
    assert "idx_returns_one_active_per_order_item" in sql


@pytest.mark.req("FR-32", "FR-33", "FR-34", "FR-35")
def test_f07_evidence_pack_generation_and_hash() -> None:
    """F-07 (FR-32..35): Evidence Pack contains passport chain, decision trace, refund IDs, custody timeline, and SHA-256."""
    pack = generate_evidence_pack(
        return_id="ret_ep_01",
        order_id="ord_ep_01",
        passport_id="pass_ep_01",
        decision_id="dec_ep_01",
        refund_request_ids=["req_r0_01"],
        custody_intervals=["ORIGIN", "CARRIER_OUT", "SHOPPER"],
        dispute_id="PP-DISP-99",
    )
    assert pack.return_id == "ret_ep_01"
    assert len(pack.canonical_sha256) == 64
    assert pack.buyer_downloadable is True
    assert "PP-DISP-99" in pack.summary_markdown


@pytest.mark.req("FR-38", "FR-39", "FR-40", "FR-41", "FR-42", "FR-43")
def test_f08_disposition_and_f09_certified_open_box_resale() -> None:
    """F-08 & F-09: Side-by-side disposition comparison and Certified Open-Box Resale listing with privacy projection."""
    comp = evaluate_disposition_options(
        price_minor=38000,
        verified_grade="B",
        estimated_resale_minor=31500,
        refurb_cost_minor=2500,
        return_shipping_minor=850,
        handling_minor=550,
    )
    assert len(comp.options) == 5
    assert comp.recommended_option in {"OPEN_BOX_RESALE", "RESTOCK_AS_NEW", "REFURBISH"}

    listing = create_certified_open_box_listing(
        passport_id="pass_ob_01",
        sku="PR-HP-XM5",
        verified_grade="B",
        list_price_minor=31500,
        prior_owner_ref="secret_buyer_ref",
        prior_buyer_email="secret@example.com",
    )
    assert listing["certified_open_box"] is True
    assert listing["verified_grade"] == "B"
    assert "secret_buyer_ref" not in str(listing)
    assert "secret@example.com" not in str(listing)


@pytest.mark.req("FR-53", "INV-13")
def test_f12_serial_registry_keyed_hmac_and_swap_detection() -> None:
    """F-12 (FR-53, INV-13): Keyed HMAC-SHA256 catches serial swaps and double-refund attempts without plaintext storage."""
    reg = SerialRegistry(merchant_secret=b"merch_secret_key_32_bytes_minimum")
    entry = reg.register_origin_serial(
        merchant_id="merch_a",
        order_id="ord_1",
        passport_id="pass_1",
        raw_serial="SN-XM5-0001",
    )
    assert "SN-XM5-0001" not in str(entry)
    assert len(entry.serial_Commitment) == 64

    # Matching return serial passes
    chk_ok = reg.verify_return_serial(merchant_id="merch_a", order_id="ord_1", raw_serial="sn-xm5-0001")
    assert chk_ok["matched"] is True
    assert chk_ok["status"] == "MATCHED_ACTIVE"

    # Mismatched serial (swap attempt) flagged
    chk_swap = reg.verify_return_serial(merchant_id="merch_a", order_id="ord_1", raw_serial="SN-XM5-9999")
    assert chk_swap["matched"] is False
    assert chk_swap["flag"] == "SERIAL_MISMATCH"

    # Previously refunded serial cannot be refunded again
    reg.mark_serial_refunded(merchant_id="merch_a", order_id="ord_1")
    chk_dup = reg.verify_return_serial(merchant_id="merch_a", order_id="ord_1", raw_serial="SN-XM5-0001")
    assert chk_dup["matched"] is False
    assert chk_dup["flag"] == "SERIAL_ALREADY_REFUNDED"


@pytest.mark.req("FR-54", "FR-55", "FR-56", "FR-69", "FR-70")
def test_f13_f14_f15_rental_cap_sla_credit_and_appeals() -> None:
    """F-13, F-14, F-15: Rental duration guard, SLA breach auto-credit, and Appeal different-reviewer enforcement."""
    # FR-55: <= 3 days until ST-03 verified
    assert validate_rental_duration_days(days=3, st03_reauth_verified=False) is True
    with pytest.raises(ValueError, match="FR-55"):
        validate_rental_duration_days(days=5, st03_reauth_verified=False)

    # FR-56: Automatic SLA credit when review exceeds deadline
    sla = compute_sla_breach_credit(elapsed_hours=72, sla_hours=48, disputed_amount_minor=10000, credit_rate_bps=1000)
    assert sla["breached"] is True
    assert sla["credit_minor"] == 1000

    # FR-69 & FR-70: Buyer appeal requires a different reviewer and schedules TOPUP tranche on overturn
    portal = AppealPortal()
    appeal = portal.file_appeal(
        return_id="ret_ap_1",
        order_id="ord_ap_1",
        original_reviewer_id="rev_alice",
        within_window=True,
        buyer_reason="Scratch was lighting glare on housing",
    )
    with pytest.raises(SameReviewerAppealError):
        portal.resolve_appeal(
            appeal_id=appeal.appeal_id,
            appeal_reviewer_id="rev_alice",
            overturn=True,
            topup_amount_minor=3800,
        )

    resolved = portal.resolve_appeal(
        appeal_id=appeal.appeal_id,
        appeal_reviewer_id="rev_bob",
        overturn=True,
        topup_amount_minor=3800,
    )
    assert resolved.status == "OVERTURNED"
    assert resolved.topup_tranche_planned is True
    assert resolved.topup_amount_minor == 3800


@pytest.mark.req(
    "FR-01", "FR-08", "FR-22", "FR-29", "FR-33", "FR-38", "FR-40",
    "FR-45", "FR-53", "FR-67", "FR-69", "FR-71", "FR-74", "FR-88",
)
def test_all_14_critical_journeys_j01_to_j14() -> None:
    """Section 35.1: Execute and verify all 14 critical end-to-end journeys J-01 through J-14."""
    for i in range(1, 15):
        jid = f"J-{i:02d}"
        res = run_critical_journey(jid)
        assert res["passed"] is True, f"{jid} failed: {res}"
