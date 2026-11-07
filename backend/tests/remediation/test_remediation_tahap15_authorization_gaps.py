"""Remediation tests for Task T9: Remaining authorization gaps (AUD-22, AUD-25, AUD-29, etc.).

Tests to write FIRST (TDD Red Phase):
1. Resale order: only shopper may buy, ownership transfers only after successful PayPal capture, body new_owner_ref ignored.
2. Privacy deletion: auth required, shopper may delete only own subject, MERCHANT_ADMIN only within their merchant.
3. Appeals: original_reviewer_id comes ONLY from stored review record; body value is ignored.
4. Service principals: carry merchant_id, limited to needed endpoints (carrier-events), cross-tenant rejected.
5. Token revocation persistence: registered at startup so revoked tokens survive restart.
6. Idempotency cache key: includes principal subject and tenant so another user with same key gets own response.
"""

from __future__ import annotations

import time
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import (
    _REVOKED_SIGNATURES,
    mint_service_token,
    mint_shopper_token,
    mint_staff_token,
    revoke_token,
)
from backend.db.models import Order, ResaleListing, Review, Return
from backend.db.repository import DatabaseRepository


@pytest.mark.req("AUD-22", "FR-40", "FR-41")
def test_resale_order_authorization_and_ownership_transfer() -> None:
    """Item 1: Resale order requires shopper role, successful capture, ignores body new_owner_ref."""
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)
    repo = app.state.repository

    admin_tok = mint_staff_token("merch_a", "MERCHANT_ADMIN", sub="admin_01")
    packer_tok = mint_staff_token("merch_a", "PACKER", sub="pack_01")
    shopper_tok = mint_shopper_token("ord_resale_1", "shopper_2")

    # 1. Admin creates active resale listing
    r_list = client.post(
        "/v1/resale/listings",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"passport_id": "pass_demo_1", "verified_grade": "A", "price_minor": 29900},
    )
    assert r_list.status_code == 201
    listing_id = r_list.json()["listing_id"]

    # Negative A: Non-shopper (e.g. PACKER) forbidden from purchasing
    r_packer_buy = client.post(
        f"/v1/resale/listings/{listing_id}/order",
        headers={"Authorization": f"Bearer {packer_tok}"},
        json={"new_owner_ref": "rogue_owner"},
    )
    assert r_packer_buy.status_code == 403

    # Negative B: Shopper whose order lacks successful PayPal capture cannot transfer ownership
    # Create uncaptured order for shopper_nocap
    uncaptured_order_id = f"ord_nocap_{uuid.uuid4().hex[:6]}"
    with repo.get_session() as session:
        session.add(
            Order(
                order_id=uncaptured_order_id,
                merchant_id="merch_a",
                account_id="shopper_1",
                policy_version="pol_v1_us_ca",
                paypal_order_id="PP-NOCAP-01",
                capture_id="",  # NOT captured
                capture_amount_minor=29900,
            )
        )
        session.commit()

    nocap_shopper_tok = mint_shopper_token(uncaptured_order_id, "shopper_1")
    r_nocap_buy = client.post(
        f"/v1/resale/listings/{listing_id}/order",
        headers={"Authorization": f"Bearer {nocap_shopper_tok}"},
        json={"new_owner_ref": "rogue_owner"},
    )
    assert r_nocap_buy.status_code in {402, 409}

    # Positive: Valid shopper with captured order succeeds, but body new_owner_ref is ignored
    r_valid_buy = client.post(
        f"/v1/resale/listings/{listing_id}/order",
        headers={"Authorization": f"Bearer {shopper_tok}"},
        json={"new_owner_ref": "spoofed_body_owner_ref"},
    )
    assert r_valid_buy.status_code == 200
    assert r_valid_buy.json()["status"] == "SOLD_TRANSFERRED"

    # Verify passport ownership belongs to authenticated shopper ('shopper_2'), NOT 'spoofed_body_owner_ref'
    passport = repo.get_passport("pass_demo_1")
    assert passport is not None
    assert passport.current_owner_ref == "shopper_2"
    assert passport.current_owner_ref != "spoofed_body_owner_ref"


@pytest.mark.req("AUD-25", "FR-87", "NFR-11")
def test_privacy_deletion_authorization_and_cross_tenant_guards() -> None:
    """Item 2: Privacy deletion requires auth; shoppers delete only own subject; MERCHANT_ADMIN only within merchant."""
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    # Negative A: Unauthenticated request rejected
    r_unauth = client.post(
        "/v1/privacy/deletion-requests",
        json={"subject_id": "shopper_1"},
    )
    assert r_unauth.status_code == 401

    # Negative B: Shopper A attempting to delete Shopper B's subject
    shopper_tok_a = mint_shopper_token("ord_demo_1", "shopper_1")
    r_shopper_cross = client.post(
        "/v1/privacy/deletion-requests",
        headers={"Authorization": f"Bearer {shopper_tok_a}"},
        json={"subject_id": "shopper_2"},
    )
    assert r_shopper_cross.status_code == 403

    # Negative C: Non-admin staff (e.g. PACKER) rejected
    packer_tok = mint_staff_token("merch_a", "PACKER", sub="pack_01")
    r_packer = client.post(
        "/v1/privacy/deletion-requests",
        headers={"Authorization": f"Bearer {packer_tok}"},
        json={"subject_id": "shopper_1"},
    )
    assert r_packer.status_code == 403

    # Negative D: MERCHANT_ADMIN of merch_a attempting to delete subject belonging exclusively to merch_b
    admin_a_tok = mint_staff_token("merch_a", "MERCHANT_ADMIN", sub="admin_a_01")
    r_admin_cross = client.post(
        "/v1/privacy/deletion-requests",
        headers={"Authorization": f"Bearer {admin_a_tok}"},
        json={"subject_id": "shopper_b"},  # shopper_b belongs to merch_b
    )
    assert r_admin_cross.status_code == 403

    # Positive: Shopper deletes their own subject
    r_shopper_ok = client.post(
        "/v1/privacy/deletion-requests",
        headers={"Authorization": f"Bearer {shopper_tok_a}"},
        json={"subject_id": "shopper_1"},
    )
    assert r_shopper_ok.status_code == 200
    assert r_shopper_ok.json()["status"] == "COMPLETED"

    # Positive: Merchant Admin deletes subject within their own merchant
    r_admin_ok = client.post(
        "/v1/privacy/deletion-requests",
        headers={"Authorization": f"Bearer {admin_a_tok}"},
        json={"subject_id": "shopper_1"},  # shopper_1 has order on merch_a
    )
    assert r_admin_ok.status_code == 200
    assert r_admin_ok.json()["status"] == "COMPLETED"


@pytest.mark.req("AUD-29", "FR-69", "F-15")
def test_appeals_original_reviewer_id_strictly_from_db() -> None:
    """Item 3: Appeals original_reviewer_id comes ONLY from stored review record; body value is ignored."""
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)
    repo = app.state.repository

    shopper_tok = mint_shopper_token("ord_demo_1", "shopper_1")
    reviewer_1_tok = mint_staff_token("merch_a", "REVIEWER", sub="rev_01")
    reviewer_2_tok = mint_staff_token("merch_a", "REVIEWER", sub="rev_02")

    # Ensure ret_demo_1 has a review with reviewer_id='rev_01'
    with repo.get_session() as session:
        rev = session.get(Review, "rev_rec_demo_1")
        assert rev is not None
        rev.reviewer_id = "rev_01"
        session.add(rev)
        session.commit()

    # Shopper files appeal, explicitly sending a spoofed original_reviewer_id in the request body
    r_appeal = client.post(
        "/v1/appeals",
        headers={"Authorization": f"Bearer {shopper_tok}"},
        json={
            "return_id": "ret_demo_1",
            "original_reviewer_id": "spoofed_reviewer_99",
            "subject": "Appeal on grade downgrade",
            "disputed_delta_minor": 3800,
        },
    )
    assert r_appeal.status_code == 201
    appeal_data = r_appeal.json()
    appeal_id = appeal_data["appeal_id"]

    # Body value 'spoofed_reviewer_99' MUST be ignored; record must have stored 'rev_01'
    assert appeal_data["original_reviewer_id"] == "rev_01"
    assert appeal_data["original_reviewer_id"] != "spoofed_reviewer_99"

    # Confirm in DB
    db_appeal = repo.get_appeal(appeal_id)
    assert db_appeal is not None
    assert db_appeal.original_reviewer_id == "rev_01"

    # Enforce independent reviewer constraint: rev_01 must be blocked from deciding the appeal
    r_same_decide = client.post(
        f"/v1/review/appeals/{appeal_id}/decision",
        headers={"Authorization": f"Bearer {reviewer_1_tok}"},
        json={"appeal_reviewer_id": "rev_01", "outcome": "OVERTURNED"},
    )
    assert r_same_decide.status_code == 409
    assert r_same_decide.json()["code"] == "SAME_REVIEWER_CONFLICT"

    # Independent rev_02 succeeds
    r_diff_decide = client.post(
        f"/v1/review/appeals/{appeal_id}/decision",
        headers={"Authorization": f"Bearer {reviewer_2_tok}"},
        json={"appeal_reviewer_id": "rev_02", "outcome": "OVERTURNED"},
    )
    assert r_diff_decide.status_code == 200


@pytest.mark.req("AUD-21", "FR-96", "TM-24")
def test_service_principals_scoped_and_cross_tenant_blocked() -> None:
    """Item 4: Service principals carry merchant_id, limited to needed endpoints, cross-tenant rejected."""
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)
    repo = app.state.repository

    service_a_tok = mint_service_token(service_id="carrier_svc_01", merchant_id="merch_a")

    # Negative A: Service principal calling shopper endpoint (POST /v1/returns) rejected
    r_returns = client.post(
        "/v1/returns",
        headers={"Authorization": f"Bearer {service_a_tok}"},
        json={"order_id": "ord_demo_1", "item_id": "item_1", "declared_grade": "A", "reason": "UNWANTED"},
    )
    assert r_returns.status_code == 403

    # Negative B: Service principal calling staff policy endpoint rejected
    r_pols = client.get(
        "/v1/policies",
        headers={"Authorization": f"Bearer {service_a_tok}"},
    )
    assert r_pols.status_code == 403

    # Negative C: Service principal of merch_a posting carrier event for merch_b return rejected (403/404)
    # Seed return belonging to merch_b
    ret_b_id = f"ret_b_{uuid.uuid4().hex[:6]}"
    with repo.get_session() as session:
        session.add(
            Return(
                return_id=ret_b_id,
                order_id="ord_merch_b_1",
                merchant_id="merch_b",
                state="AWAITING_SHIPMENT",
                order_item_id="item_b_01",
                declared_grade="A",
                reason_code="UNWANTED",
            )
        )
        session.commit()

    r_cross_carrier = client.post(
        "/v1/carrier-events",
        headers={"Authorization": f"Bearer {service_a_tok}"},
        json={
            "return_id": ret_b_id,
            "type": "CARRIER_FIRST_SCAN",
            "event_type": "CARRIER_FIRST_SCAN",
        },
    )
    assert r_cross_carrier.status_code in {403, 404}

    # Positive: Service principal with matching tenant (merch_b) succeeds
    service_b_tok = mint_service_token(service_id="carrier_svc_02", merchant_id="merch_b")
    r_tenant_ok = client.post(
        "/v1/carrier-events",
        headers={"Authorization": f"Bearer {service_b_tok}"},
        json={
            "return_id": ret_b_id,
            "type": "CARRIER_FIRST_SCAN",
            "event_type": "CARRIER_FIRST_SCAN",
        },
    )
    assert r_tenant_ok.status_code == 200


@pytest.mark.req("RV-12", "AUD-21")
def test_token_revocation_survives_restart() -> None:
    """Item 5: Register revocation persistence at startup so revocations survive restarts."""
    repo = DatabaseRepository()
    app1 = create_app(repository=repo, demo_mode=True, mode="judge")
    client1 = TestClient(app1)

    staff_tok = mint_staff_token("merch_a", "MERCHANT_ADMIN", sub="admin_survive_01")

    # Initial check: Token works
    r_init = client1.get("/v1/policies", headers={"Authorization": f"Bearer {staff_tok}"})
    assert r_init.status_code == 200

    # Revoke the token
    revoke_token(staff_tok)

    # Simulate full process restart: clear in-memory set
    _REVOKED_SIGNATURES.clear()

    # Re-initialize app from same repository/database
    app2 = create_app(repository=repo, demo_mode=True, mode="judge")
    client2 = TestClient(app2)

    # Calling with revoked token after restart MUST be rejected
    r_after_restart = client2.get("/v1/policies", headers={"Authorization": f"Bearer {staff_tok}"})
    assert r_after_restart.status_code == 401
    assert "revoked" in r_after_restart.json()["detail"].lower()


@pytest.mark.req("AUD-16", "FR-16", "FR-47")
def test_idempotency_cache_key_scoped_by_subject_and_tenant() -> None:
    """Item 6: Idempotency cache key includes principal subject and tenant; same key from another user doesn't collide."""
    app = create_app(demo_mode=True, mode="judge")
    client = TestClient(app)

    shared_idem_key = f"idem_shared_{uuid.uuid4().hex[:8]}"

    shopper_1_tok = mint_shopper_token("ord_demo_1", "shopper_1")
    shopper_2_tok = mint_shopper_token("ord_resale_1", "shopper_2")

    # User 1 submits return declaration with shared_idem_key
    r_user_1 = client.post(
        "/v1/returns",
        headers={"Authorization": f"Bearer {shopper_1_tok}", "Idempotency-Key": shared_idem_key},
        json={
            "order_id": "ord_demo_1",
            "order_item_id": "item_demo_1",
            "declared_grade": "A",
            "reason": "COLOR_UNSATISFIED",
            "reason_code": "COLOR_UNSATISFIED",
        },
    )
    assert r_user_1.status_code == 200
    ret_1_id = r_user_1.json()["return_id"]

    # User 2 submits return declaration with the exact same shared_idem_key
    r_user_2 = client.post(
        "/v1/returns",
        headers={"Authorization": f"Bearer {shopper_2_tok}", "Idempotency-Key": shared_idem_key},
        json={
            "order_id": "ord_resale_1",
            "order_item_id": "item_resale_1",
            "declared_grade": "A",
            "reason": "COLOR_UNSATISFIED",
            "reason_code": "COLOR_UNSATISFIED",
        },
    )
    assert r_user_2.status_code == 200
    ret_2_id = r_user_2.json()["return_id"]

    # User 2 MUST get their own return, NOT User 1's return
    assert ret_2_id != ret_1_id
    assert r_user_2.json()["order_id"] == "ord_resale_1"
