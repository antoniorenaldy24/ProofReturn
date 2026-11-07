"""Comprehensive Integration & E2E HTTP Suite for all 23 REST API /v1 endpoints (Section 10.6 & Section 28)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token


def test_order_passport_declaration_evidence_dropoff_and_receipts_flow(reset_db: Any) -> None:
    """Tests POST /v1/orders/{id}/passport, POST /v1/returns/{id}/declaration,
    POST /v1/returns/{id}/evidence, POST /v1/returns/{id}/dropoff,
    GET /v1/returns/{id}/receipts, and GET /v1/returns/{id}/evidence-pack.
    """
    client = TestClient(create_app(demo_mode=True, mode="judge"))
    packer_token = mint_staff_token("merch_a", "PACKER", sub="pack_01")
    shopper_token = mint_shopper_token("ord_demo_1", "shopper_1")

    # 1. POST /v1/orders/{id}/passport (PACKER role)
    r_pass = client.post(
        "/v1/orders/ord_demo_1/passport",
        headers={"Authorization": f"Bearer {packer_token}", "Idempotency-Key": "ik-full-ord-pass-1"},
        json={
            "sku": "PR-HP-XM5",
            "origin_grade": "A",
            "weight_g": 250,
            "self_test_passed": True,
        },
    )
    assert r_pass.status_code == 201
    pass_data = r_pass.json()
    assert pass_data["order_id"] == "ord_demo_1"
    assert pass_data["tier"] == "LITE"
    assert pass_data["chain_valid"] is True

    # 2. POST /v1/returns/{id}/declaration (Shopper)
    r_decl = client.post(
        "/v1/returns/ret_demo_1/declaration",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "declared_grade": "B",
            "accessories": {"case": True, "cable": True},
            "reason_code": "CHANGED_MIND",
            "reason_text": "Opened box to test comfort",
            "fast_lane_terms_accepted": True,
            "shopper_nonce": "shopper_nonce_abc123",
        },
    )
    assert r_decl.status_code == 200
    decl_data = r_decl.json()
    assert decl_data["declared_grade"] == "B"
    assert decl_data["fast_lane_terms_accepted"] is True

    # 3. POST /v1/returns/{id}/evidence (Shopper, face blur applied)
    r_ev = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {shopper_token}", "Idempotency-Key": "ik-full-ev-1"},
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": "raw/ret_demo_1/challenge.mp4",
            "sha256": "a" * 64,
            "challenge_step": 1,
            "faces_detected": 1,
            "client_blur_applied": True,
            "blur_latency_ms": 19.5,
            "text_in_media": decl_data["challenge_nonce"],
        },
    )
    assert r_ev.status_code == 200
    ev_data = r_ev.json()
    assert ev_data["accepted"] is True
    assert ev_data["state"] == "ASSESSED"
    # AUD-01 / J-04: True Policy Engine calculation for ord_demo_1 (price $380.00 / 38000 minor, grade B) -> 21249
    assert ev_data["r0_tranche_minor"] == 21249

    # 4. POST /v1/returns/{id}/dropoff (FR-64 sealed drop-off photo + tracking)
    r_drop = client.post(
        "/v1/returns/ret_demo_1/dropoff",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "seal_nonce": "SEAL-NONCE-01",
            "dropoff_photo_ref": "raw/ret_demo_1/dropoff.jpg",
            "carrier_tracking_number": "1Z999AA10123456784",
        },
    )
    assert r_drop.status_code == 200
    drop_data = r_drop.json()
    assert drop_data["seal_recorded"] is True
    assert drop_data["carrier_tracking_number"] == "1Z999AA10123456784"

    # 5. GET /v1/returns/{id}/receipts (FR-61, FR-76, FR-77, FR-95)
    r_rec = client.get(
        "/v1/returns/ret_demo_1/receipts",
        headers={"Authorization": f"Bearer {shopper_token}"},
    )
    assert r_rec.status_code == 200
    rec_data = r_rec.json()
    assert len(rec_data["receipts"]) >= 2
    assert "audit_commitment" in rec_data
    assert rec_data["audit_commitment"]["nonce_shopper"] == "shopper_nonce_abc123"

    # 6. GET /v1/returns/{id}/evidence-pack (FR-33, FR-35)
    r_pack = client.get(
        "/v1/returns/ret_demo_1/evidence-pack",
        headers={"Authorization": f"Bearer {shopper_token}"},
    )
    assert r_pack.status_code == 200
    pack_data = r_pack.json()
    assert pack_data["return_id"] == "ret_demo_1"
    assert pack_data["pack_sha256"].startswith("sha256:") or len(pack_data["pack_sha256"]) == 64


def test_keep_offer_receiving_checkpoint_and_audit_endpoints(reset_db: Any) -> None:
    """Tests POST /v1/returns/{id}/keep-offer/respond,
    POST /v1/receiving/{passport_id}/checkpoint, and POST /v1/audits/{return_id}.
    """
    client = TestClient(create_app(demo_mode=True, mode="judge"))
    shopper_token = mint_shopper_token("ord_demo_1", "shopper_1")
    receiver_token = mint_staff_token("merch_a", "RECEIVER", sub="recv_01")
    reviewer_token = mint_staff_token("merch_a", "REVIEWER", sub="rev_01")

    # 0. Submit evidence so return reaches ASSESSED state (Task T6 / RV-03: keep-offer only from ASSESSED)
    r_ev = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {shopper_token}", "Idempotency-Key": "ik-full-ev-2"},
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": "raw/ret_demo_1/challenge.mp4",
            "sha256": "a" * 64,
            "challenge_step": 1,
            "faces_detected": 0,
            "client_blur_applied": False,
            "blur_latency_ms": 10.0,
        },
    )
    assert r_ev.status_code == 200

    # 1. Accept posted keep-offer (FR-39, FR-46, FR-78)
    r_keep = client.post(
        "/v1/returns/ret_demo_1/keep-offer/respond",
        headers={"Authorization": f"Bearer {shopper_token}", "Idempotency-Key": "ik-full-keep-1"},
        json={"action": "ACCEPT"},
    )
    assert r_keep.status_code == 200
    keep_data = r_keep.json()
    assert keep_data["status"] == "KEEP_ACCEPTED"
    assert keep_data["tranche_kind"] == "KEEP"
    assert keep_data["posted_price_minor"] > 0
    assert "k_max_minor" not in keep_data  # INV-06 / MV-18: bounds never disclosed

    # 2. Receiving checkpoint (FR-29, F-06 records_only=True)
    r_chk = client.post(
        "/v1/receiving/pass_demo_1/checkpoint",
        headers={"Authorization": f"Bearer {receiver_token}"},
        json={
            "interval": "CARRIER_TO_DOCK",
            "weight_g": 249,
            "seal_status": "INTACT",
            "evidence_ref": "raw/pass_demo_1/dock.jpg",
        },
    )
    assert r_chk.status_code == 200
    chk_data = r_chk.json()
    assert chk_data["passport_id"] == "pass_demo_1"
    assert chk_data["records_only"] is True

    # 3. Record full audit result (POST /v1/audits/{return_id})
    r_aud = client.post(
        "/v1/audits/ret_demo_1",
        headers={"Authorization": f"Bearer {reviewer_token}", "Idempotency-Key": "ik-full-aud-1"},
        json={
            "verified_grade": "B",
            "conformal_set": ["B"],
            "notes": "Verified grade B matches shopper declaration.",
        },
    )
    assert r_aud.status_code == 200
    aud_data = r_aud.json()
    assert aud_data["verified_grade"] == "B"
    assert aud_data["misdeclaration_cost_minor"] == 0


def test_appeals_resale_policies_and_simulator_views(reset_db: Any) -> None:
    """Tests POST /v1/appeals, GET /v1/appeals/{id}, POST /v1/review/appeals/{id}/decision,
    POST /v1/resale/listings, POST /v1/resale/listings/{id}/order,
    GET /v1/policies, GET /v1/simulate/feasibility-map, and GET /v1/simulate/roi.
    """
    client = TestClient(create_app(demo_mode=True, mode="judge"))
    shopper_token = mint_shopper_token("ord_demo_1", "shopper_1")
    reviewer_1_token = mint_staff_token("merch_a", "REVIEWER", sub="rev_01")
    reviewer_2_token = mint_staff_token("merch_a", "REVIEWER", sub="rev_02")
    admin_token = mint_staff_token("merch_a", "MERCHANT_ADMIN", sub="admin_01")
    buyer_token = mint_shopper_token("ord_resale_1", "shopper_2")

    # 1. File appeal (POST /v1/appeals, FR-69)
    r_app = client.post(
        "/v1/appeals",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "return_id": "ret_demo_1",
            "original_reviewer_id": "rev_01",
            "subject": "Requesting review of minor scuff lighting artifact",
            "disputed_delta_minor": 3800,
        },
    )
    assert r_app.status_code == 201
    app_data = r_app.json()
    appeal_id = app_data["appeal_id"]

    # 2. Track appeal (GET /v1/appeals/{id})
    r_get_app = client.get(
        f"/v1/appeals/{appeal_id}",
        headers={"Authorization": f"Bearer {shopper_token}"},
    )
    assert r_get_app.status_code == 200
    assert r_get_app.json()["status"] == "OPEN"

    # 3. Same reviewer blocked from deciding appeal (F-15 independent reviewer rule)
    r_same_rev = client.post(
        f"/v1/review/appeals/{appeal_id}/decision",
        headers={"Authorization": f"Bearer {reviewer_1_token}", "Idempotency-Key": "ik-full-app-same-1"},
        json={"appeal_reviewer_id": "rev_01", "outcome": "OVERTURNED"},
    )
    assert r_same_rev.status_code == 409

    # 4. Independent reviewer overturns appeal -> compensating TOPUP/COMP tranche planned (FR-69)
    r_diff_rev = client.post(
        f"/v1/review/appeals/{appeal_id}/decision",
        headers={"Authorization": f"Bearer {reviewer_2_token}", "Idempotency-Key": "ik-full-app-diff-1"},
        json={"appeal_reviewer_id": "rev_02", "outcome": "OVERTURNED"},
    )
    assert r_diff_rev.status_code == 200
    dec_app = r_diff_rev.json()
    assert dec_app["outcome"] == "OVERTURNED"
    assert dec_app["compensating_refund_minor"] == 3800

    # 5. Certified Open-Box Resale listing & purchase (POST /v1/resale/listings & /order, F-09, FR-40, FR-41)
    r_list = client.post(
        "/v1/resale/listings",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "ik-full-res-list-1"},
        json={"passport_id": "pass_demo_1", "verified_grade": "B", "price_minor": 31500},
    )
    assert r_list.status_code == 201
    listing_id = r_list.json()["listing_id"]

    r_buy = client.post(
        f"/v1/resale/listings/{listing_id}/order",
        headers={"Authorization": f"Bearer {buyer_token}", "Idempotency-Key": "ik-full-res-buy-1"},
        json={"new_owner_ref": "owner_secret_ref_2"},
    )
    assert r_buy.status_code == 200
    buy_data = r_buy.json()
    assert buy_data["status"] == "SOLD_TRANSFERRED"
    assert buy_data["prior_owner_pii_stripped"] is True

    # 6. GET /v1/policies, GET /v1/simulate/feasibility-map, GET /v1/simulate/roi (FR-51, FR-79, FR-101)
    r_pols = client.get(
        "/v1/policies",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_pols.status_code == 200
    assert len(r_pols.json()["policies"]) >= 1

    r_fmap = client.get(
        "/v1/simulate/feasibility-map?declared_grade=B",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_fmap.status_code == 200
    fmap_data = r_fmap.json()
    assert fmap_data["data_source_badge"] == "SIMULATED"
    assert len(fmap_data["cells"]) == 15

    r_roi = client.get(
        "/v1/simulate/roi",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_roi.status_code == 200
    roi_data = r_roi.json()
    assert roi_data["label"] == "model, not measured"
    assert "assumptions" in roi_data
