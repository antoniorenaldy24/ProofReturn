"""Round 4 Task T3: Fail-closed guards and Passport tier from value band (RV3-14, RV3-03, RV3-07, FR-63, FR-65).

Tests:
1. Evidence without text_in_media -> no FAST release (r0_tranche_minor == 0, x_released_minor == 0),
   routed to STANDARD lane, reason CHALLENGE_NOT_VERIFIED recorded in decision explanation and response.
2. Evidence with OCR text that does not contain the stored nonce -> 409 INVALID_STATE_TRANSITION.
3. Dropoff for an order whose merchant row is missing -> 409 MERCHANT_NOT_FOUND, no state change.
4. Passport created with tier "FULL" in the body for a low-value item -> stored tier follows the
   SSOT value band (NONE for <$150, LITE for $150-$600), not the request body.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.config import ProofReturnSettings
from backend.db.models import Decision, Merchant, Order, OrderItem, Passport, RefundAction, Return
from backend.db.repository import DatabaseRepository


@pytest.fixture()
def t3_env(tmp_path: Path) -> tuple[TestClient, DatabaseRepository]:
    db_file = tmp_path / f"r4_t3_{uuid.uuid4().hex[:8]}.db"
    db_url = f"sqlite:///{db_file}"
    settings = ProofReturnSettings(mode="judge", database_url=db_url, demo_mode=True, enable_scheduler=False)
    repo = DatabaseRepository(database_url=db_url)
    app = create_app(repository=repo, settings=settings, demo_mode=True, mode="judge")
    return TestClient(app), repo


@pytest.mark.req("RV3-14", "FR-65")
def test_evidence_without_text_in_media_routes_to_standard_lane_with_reason_recorded(
    t3_env: tuple[TestClient, DatabaseRepository],
) -> None:
    """1. Evidence without text_in_media -> no FAST release, lane STANDARD, reason CHALLENGE_NOT_VERIFIED recorded."""
    client, repo = t3_env
    shopper_tok = mint_shopper_token("ord_demo_1", "shopper_1")

    r_ev = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {shopper_tok}", "Idempotency-Key": "ik-r4t3-ev-no-ocr"},
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": "raw/ret_demo_1/no_ocr_challenge.mp4",
            "sha256": "a" * 64,
            "challenge_step": 1,
            "faces_detected": 0,
            "client_blur_applied": False,
            "blur_latency_ms": 10.0,
            # text_in_media omitted
        },
    )
    assert r_ev.status_code == 200, r_ev.text
    ev_data = r_ev.json()
    assert ev_data["lane"] == "STANDARD"
    assert ev_data["r0_tranche_minor"] == 0
    assert ev_data["x_released_minor"] == 0
    assert ev_data.get("reason") == "CHALLENGE_NOT_VERIFIED"

    with repo.get_session() as s:
        ret = s.get(Return, "ret_demo_1")
        assert ret is not None
        assert ret.state == "ASSESSED"
        assert ret.lane == "STANDARD"
        assert ret.r0_tranche_minor == 0

        decisions = s.exec(select(Decision).where(Decision.return_id == "ret_demo_1")).all()
        assert len(decisions) == 1
        dec = decisions[0]
        assert dec.lane == "STANDARD"
        assert dec.x_minor == 0
        assert dec.explanation_json.get("reason") == "CHALLENGE_NOT_VERIFIED"
        assert "CHALLENGE_NOT_VERIFIED" in str(dec.explanation_json.get("explanation", ""))

        actions = s.exec(select(RefundAction).where(RefundAction.order_id == "ord_demo_1")).all()
        assert len(actions) == 0


@pytest.mark.req("RV3-14", "FR-65")
def test_evidence_with_mismatched_ocr_text_returns_409(
    t3_env: tuple[TestClient, DatabaseRepository],
) -> None:
    """2. Evidence with OCR text that does not contain the stored nonce -> 409 INVALID_STATE_TRANSITION."""
    client, repo = t3_env
    shopper_tok = mint_shopper_token("ord_demo_1", "shopper_1")

    r_ev = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {shopper_tok}", "Idempotency-Key": "ik-r4t3-ev-bad-ocr"},
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": "raw/ret_demo_1/wrong_nonce.mp4",
            "sha256": "b" * 64,
            "challenge_step": 1,
            "faces_detected": 0,
            "client_blur_applied": False,
            "blur_latency_ms": 10.0,
            "text_in_media": "WRONG-NONCE-0000",
        },
    )
    assert r_ev.status_code == 409, r_ev.text
    assert r_ev.json()["code"] == "INVALID_STATE_TRANSITION"

    with repo.get_session() as s:
        ret = s.get(Return, "ret_demo_1")
        assert ret is not None
        assert ret.state == "DECLARED"


@pytest.mark.req("RV3-03")
def test_dropoff_for_order_with_missing_merchant_row_returns_409_and_no_state_change(
    t3_env: tuple[TestClient, DatabaseRepository],
) -> None:
    """3. Dropoff for an order whose merchant row is missing -> 409 MERCHANT_NOT_FOUND, no state change."""
    client, repo = t3_env
    shopper_tok = mint_shopper_token("ord_demo_1", "shopper_1")

    with repo.get_session() as s:
        ret = s.get(Return, "ret_demo_1")
        assert ret is not None
        ret.state = "ASSESSED"
        ret.merchant_id = "merch_missing_ghost"
        s.add(ret)
        # Ensure merchant row does not exist
        ghost = s.get(Merchant, "merch_missing_ghost")
        if ghost:
            s.delete(ghost)
        s.commit()

    r_drop = client.post(
        "/v1/returns/ret_demo_1/dropoff",
        headers={"Authorization": f"Bearer {shopper_tok}"},
        json={
            "seal_nonce": "SEAL-NONCE-GHOST-1",
            "dropoff_photo_ref": "raw/ret_demo_1/dropoff.jpg",
            "carrier_tracking_number": "1Z999AA10123456784",
        },
    )
    assert r_drop.status_code == 409, r_drop.text
    assert r_drop.json()["code"] == "MERCHANT_NOT_FOUND"

    with repo.get_session() as s:
        ret_after = s.get(Return, "ret_demo_1")
        assert ret_after is not None
        assert ret_after.state == "ASSESSED"
        assert ret_after.seal_nonce_hash is None


@pytest.mark.req("RV3-07", "FR-63")
def test_passport_created_with_tier_full_for_low_value_item_uses_value_band_tier(
    t3_env: tuple[TestClient, DatabaseRepository],
) -> None:
    """4. Passport created with tier 'FULL' in the body for a low-value item -> stored tier follows the value band, not the body."""
    client, repo = t3_env
    packer_tok = mint_staff_token("merch_a", "PACKER", sub="pack_01")

    # Seed a low-value order ($45.00 = 4500 minor < $150.00 threshold -> value band LOW -> tier "NONE")
    with repo.get_session() as s:
        s.add(
            Order(
                order_id="ord_low_val_1",
                merchant_id="merch_a",
                account_id="shopper_1",
                policy_version="pol_electronics_us_v1",
                capture_id="CAP_LOW_VAL_1",
                capture_amount_minor=4500,
                currency="USD",
                status="CAPTURED",
            )
        )
        s.add(
            OrderItem(
                order_item_id="item_low_val_1",
                order_id="ord_low_val_1",
                sku="SKU-LOW-CABLE",
                price_minor=4500,
                currency="USD",
            )
        )
        s.commit()

    # Case A: POST /v1/passports with tier="FULL" for low-value SKU "SKU-LOW-CABLE"
    r_mint = client.post(
        "/v1/passports",
        headers={"Authorization": f"Bearer {packer_tok}", "Idempotency-Key": "ik-r4t3-mint-low-a"},
        json={
            "passport_id": "pass_low_val_01",
            "sku": "SKU-LOW-CABLE",
            "tier": "FULL",
            "origin_grade": "A",
            "weight_g": 80,
            "self_test_passed": True,
        },
    )
    assert r_mint.status_code == 201, r_mint.text
    mint_data = r_mint.json()
    assert mint_data["tier"] == "NONE"

    with repo.get_session() as s:
        stored_pass = s.get(Passport, "pass_low_val_01")
        assert stored_pass is not None
        assert stored_pass.tier == "NONE"

    # Case B: POST /v1/orders/{order_id}/passport with tier="FULL" in body for low-value order
    r_ord_pass = client.post(
        "/v1/orders/ord_low_val_1/passport",
        headers={"Authorization": f"Bearer {packer_tok}", "Idempotency-Key": "ik-r4t3-mint-low-b"},
        json={
            "passport_id": "pass_ord_low_val_01",
            "sku": "SKU-LOW-CABLE",
            "tier": "FULL",
            "origin_grade": "A",
            "weight_g": 80,
            "self_test_passed": True,
        },
    )
    assert r_ord_pass.status_code == 201, r_ord_pass.text
    ord_pass_data = r_ord_pass.json()
    assert ord_pass_data["tier"] == "NONE"

    with repo.get_session() as s:
        stored_ord_pass = s.get(Passport, "pass_ord_low_val_01")
        assert stored_ord_pass is not None
        assert stored_ord_pass.tier == "NONE"
