"""Invariant tests for INV-09, INV-10, INV-11, INV-12, INV-13 through the API (SSOT Section 29.1).

INV-09: Passport & decision events append-only, hash-chained; tampered event/key -> chain_valid=False.
INV-10: Gross finding requires conformal exclusion AND human confirmation.
INV-11: Jurisdiction cap violation -> 422/409, zero holdback, zero fee.
INV-12: Agents cannot complete physical evidence challenge; agent token cannot submit evidence,
        finish assessment, or accept keep-offer before ASSESSED (403/409).
INV-13: No plaintext serials/PII in logs; unblurred face evidence rejected (422).
"""

from __future__ import annotations

from typing import Any
from fastapi.testclient import TestClient
from sqlmodel import select

from backend.api.app import create_app
from backend.auth.tokens import mint_agent_token, mint_shopper_token, mint_staff_token
from backend.db.models import Passport, PassportEvent, Policy, Return, ReturnEvidence


def test_inv09_tampered_passport_chain_fails_validation(reset_db: Any) -> None:
    """INV-09 NEGATIVE: Tampered passport event hash or signature results in chain_valid=False.

    Tampered state must never be verified as valid.
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    tok_packer = mint_staff_token("merch_a", "PACKER", sub="pack_inv09")
    tok_shopper = mint_shopper_token("ord_demo_1", "shopper_1")

    # 1. Mint a dedicated passport for tamper verification
    r_mint = client.post(
        "/v1/passports",
        headers={"Authorization": f"Bearer {tok_packer}", "Idempotency-Key": "ik-inv09-mint"},
        json={
            "passport_id": "pass_inv09_tamper",
            "sku": "PR-INV09",
            "origin_grade": "A",
            "weight_g": 250,
            "self_test_passed": True,
            "line_price_minor": 38000,
        },
    )
    assert r_mint.status_code == 201

    # Verify initial chain is valid
    r_init = client.get(
        "/v1/passports/pass_inv09_tamper/verify",
        headers={"Authorization": f"Bearer {tok_shopper}"},
    )
    assert r_init.status_code == 200
    assert r_init.json()["chain_valid"] is True

    # 2. Tamper with the passport event in the database
    with reset_db.get_session() as session:
        event = session.exec(
            select(PassportEvent).where(PassportEvent.passport_id == "pass_inv09_tamper")
        ).first()
        assert event is not None
        event.payload_json = '{"tampered": true, "sku": "FORGED_SKU"}'
        session.add(event)
        session.commit()

    # 3. Requesting passport verification now must report chain_valid == False
    r_tampered = client.get(
        "/v1/passports/pass_inv09_tamper/verify",
        headers={"Authorization": f"Bearer {tok_shopper}"},
    )
    assert r_tampered.status_code == 200
    assert r_tampered.json()["chain_valid"] is False


def test_inv10_gross_finding_without_conformal_exclusion_charges_zero_fee(reset_db: Any) -> None:
    """INV-10: Gross finding requires conformal exclusion AND human confirmation to be status-affecting.

    NEGATIVE: Even if reviewer provides excluded_at_alpha_accuse=true in request body,
    server computes conformal test server-side; if not excluded, f_charged_minor == 0
    and status_affected is False.
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    tok_reviewer = mint_staff_token("merch_a", "REVIEWER", sub="rev_inv10")

    # Settle ret_demo_escalated (declared B, verified D).
    # Request body tries to force excluded_at_alpha_accuse=true
    r_dec = client.post(
        "/v1/review/ret_demo_escalated/decision",
        headers={"Authorization": f"Bearer {tok_reviewer}", "Idempotency-Key": "ik-inv10-gross"},
        json={
            "outcome": "SETTLE_VERIFIED",
            "verified_grade": "D",
            "excluded_at_alpha_accuse": True,  # Server must ignore this body field (T7)
            "notes": "Testing conformal calibration gate",
        },
    )
    assert r_dec.status_code == 200
    dec_data = r_dec.json()

    # In illustrative calibration profile, grade is not excluded -> fee must be 0 and status unaffected
    assert dec_data.get("f_charged_minor") == 0
    assert dec_data.get("status_affected") is False


def test_inv11_jurisdiction_cap_violation_rejected_at_policy_creation(reset_db: Any) -> None:
    """INV-11 NEGATIVE: Curves violating statutory jurisdiction caps (INV-11, FR-10)

    must be REJECTED with 422 JURISDICTION_CAP_VIOLATION and not saved.
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    tok_admin = mint_staff_token("merch_a", "MERCHANT_ADMIN", sub="admin_inv11")

    # Violation 1: EU policy with non-zero fee (EU statutory rule: F = 0)
    r_eu_violation = client.post(
        "/v1/policies",
        headers={"Authorization": f"Bearer {tok_admin}", "Idempotency-Key": "ik-inv11-eu"},
        json={
            "jurisdiction": "EU",
            "fee_f_minor": 1500,  # Illegal: EU requires fee_f_minor == 0
            "c_ship_minor": 500,
            "curve": {"A": 1.0, "B": 0.95, "C": 0.80, "D": 0.50},
        },
    )
    assert r_eu_violation.status_code == 422
    assert r_eu_violation.json()["code"] == "JURISDICTION_CAP_VIOLATION"

    # Violation 2: Probe with excessive holdback (C = 0.50 / holdback 50% exceeds legal cap)
    r_probe_violation = client.post(
        "/v1/policies",
        headers={"Authorization": f"Bearer {tok_admin}", "Idempotency-Key": "ik-inv11-probe"},
        json={
            "jurisdiction": "US_CA",
            "fee_f_minor": 0,
            "c_ship_minor": 500,
            "curve": {"A": 1.0, "B": 0.85, "C": 0.50, "D": 0.20},  # Exceeds max holdback
        },
    )
    assert r_probe_violation.status_code == 422
    assert r_probe_violation.json()["code"] == "JURISDICTION_CAP_VIOLATION"

    # Verify NEGATIVE assertion: neither policy was persisted
    with reset_db.get_session() as session:
        eu_pol = session.get(Policy, "ik-inv11-eu")
        assert eu_pol is None
        probe_pol = session.get(Policy, "ik-inv11-probe")
        assert probe_pol is None


def test_inv12_agent_cannot_complete_physical_challenge_or_act_before_assessed(reset_db: Any) -> None:
    """INV-12 NEGATIVE: Agents cannot complete physical evidence challenge;

    agent token cannot submit evidence (403), request challenge (403),
    or accept keep-offer before ASSESSED (409).
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    tok_agent = mint_agent_token(
        agent_id="bot_inv12",
        order_id="ord_demo_1",
        merchant_id="merch_a",
        scopes=["read_policy", "declare", "keep_offer"],
    )

    # 1. Agent attempts to request challenge -> 403
    r_chal = client.get(
        "/v1/returns/ret_demo_1/challenge",
        headers={"Authorization": f"Bearer {tok_agent}"},
    )
    assert r_chal.status_code == 403
    assert r_chal.json()["code"] in {"ROLE_FORBIDDEN", "FORBIDDEN_ACTION", "AGENT_EVIDENCE_FORBIDDEN"}

    # 2. Agent attempts to submit evidence -> 403
    r_ev = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {tok_agent}", "Idempotency-Key": "ik-inv12-ev"},
        json={"kind": "PHOTO", "object_key": "raw/test.jpg", "sha256": "0" * 64},
    )
    assert r_ev.status_code == 403

    # 3. Agent attempts to accept keep-offer before ASSESSED state -> 409
    # Return ret_demo_1 is in DECLARED state initially
    r_keep = client.post(
        "/v1/returns/ret_demo_1/keep-offer/respond",
        headers={"Authorization": f"Bearer {tok_agent}", "Idempotency-Key": "ik-inv12-keep"},
        json={"action": "ACCEPT"},
    )
    assert r_keep.status_code == 409
    assert r_keep.json()["code"] in {"INVALID_STATE_TRANSITION", "NO_KEEP_OFFER", "KEEP_OFFER_ACTION_INVALID"}


def test_inv13_unblurred_face_evidence_rejected(reset_db: Any) -> None:
    """INV-13 NEGATIVE: Client evidence containing unblurred detected faces

    must be REJECTED with 422 and not saved in the database.
    """
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    tok_shopper = mint_shopper_token("ord_demo_1", "shopper_1")

    # Submit evidence with faces_detected > 0 and client_blur_applied = False
    r_unblurred = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {tok_shopper}", "Idempotency-Key": "ik-inv13-face"},
        json={
            "kind": "PHOTO_PACK",
            "object_key": "raw/ret_demo_1/unblurred_face.jpg",
            "sha256": "c" * 64,
            "faces_detected": 1,
            "client_blur_applied": False,
            "blur_latency_ms": 15.0,
        },
    )
    assert r_unblurred.status_code == 422
    err = r_unblurred.json()
    assert err["code"] in {"UNBLURRED_FACE_REJECTED", "VALIDATION_FAILED"}

    # Verify NEGATIVE assertion: evidence record was NOT saved in database
    with reset_db.get_session() as session:
        ev_rec = session.exec(
            select(ReturnEvidence).where(ReturnEvidence.evidence_sha256 == "c" * 64)
        ).first()
        assert ev_rec is None
