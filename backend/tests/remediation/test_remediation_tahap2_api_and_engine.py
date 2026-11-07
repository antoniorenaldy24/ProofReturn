"""Remediation Tahap 2 (Re-Audit Section J.1 & J.2): Real Policy Engine, DB Persistence,
Dynamic Guards, Keep-Offer Consistency, Route Templating & Auth Protection
(AUD-01, AUD-04, AUD-06, RV-03, RV-04, RV-11, AUD-14, AUD-22, AUD-25, AUD-29, FR-88)."""

from __future__ import annotations

import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import (
    mint_agent_token,
    mint_shopper_token,
    mint_staff_token,
)
from backend.db.models import Assessment, Order, OrderItem, Return, Review
from backend.db.repository import DatabaseRepository
from backend.domain.receipts import verify_signed_receipt


@pytest.fixture
def repo(tmp_path: Any) -> DatabaseRepository:
    """Provide a clean isolated DatabaseRepository with seeded demo data."""
    db_file = tmp_path / "tahap2_test.db"
    repository = DatabaseRepository(f"sqlite:///{db_file}", run_migrations_on_init=True)
    repository.seed_demo_data()
    return repository


def test_aud01_real_policy_engine_calculation_on_evidence(repo: DatabaseRepository) -> None:
    """AUD-01 & J-04: Submit evidence calculates exact tranche via decide_release() and saves Decision to DB."""
    app = create_app(repository=repo, demo_mode=True, mode="judge")
    client = TestClient(app)
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")

    # Submit declaration first
    r_decl = client.post(
        "/v1/returns/ret_demo_1/declaration",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "declared_grade": "B",
            "accessories": {"case": True, "cable": True},
            "reason_code": "CHANGED_MIND",
            "reason_text": "Need smaller size",
            "fast_lane_terms_accepted": True,
            "shopper_nonce": "nonce_shopper_real_01",
        },
    )
    assert r_decl.status_code == 200

    # Submit evidence
    r_ev = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "faces_detected": 0,
            "client_blur_applied": True,
            "text_in_media": repo.get_return("ret_demo_1").challenge_nonce,
        },
    )
    assert r_ev.status_code == 200
    ev_data = r_ev.json()
    assert ev_data["accepted"] is True
    # Real Policy Engine output for $380.00 order item with grade B: 21249 minor (NOT the legacy hardcoded mock 22157)
    assert ev_data["r0_tranche_minor"] == 21249
    assert ev_data["lane"] == "FAST"
    assert ev_data["timing"] == "R0"

    # Verify decision entity is persisted in the DatabaseRepository
    persisted_dec = repo.get_latest_decision("ret_demo_1")
    assert persisted_dec is not None
    assert persisted_dec.x_minor == 21249
    assert persisted_dec.signature != ""
    assert "explanation" in persisted_dec.explanation_json
    assert "$212.49" in persisted_dec.explanation_json["explanation"]


def test_aud04_pydantic_validation_and_rfc9457_error_contracts(repo: DatabaseRepository) -> None:
    """AUD-04 & J-08: Pydantic request models return RFC 9457 Problem Details on invalid input or malformed JSON."""
    app = create_app(repository=repo, demo_mode=True, mode="judge")
    client = TestClient(app)
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")

    # 1. Validation failure: missing required fast_lane_terms_accepted or invalid grade
    r_bad_decl = client.post(
        "/v1/returns/ret_demo_1/declaration",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "declared_grade": "Z_INVALID_GRADE",
            "fast_lane_terms_accepted": False,  # Non-permissive guard
        },
    )
    assert r_bad_decl.status_code in {400, 422}
    prob = r_bad_decl.json()
    assert "type" in prob
    assert "title" in prob
    assert "status" in prob
    assert "code" in prob

    # 2. Privacy failure: unblurred face in evidence submission
    r_bad_ev = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "faces_detected": 1,
            "client_blur_applied": False,  # Must be True when face detected
        },
    )
    assert r_bad_ev.status_code == 422
    prob_ev = r_bad_ev.json()
    assert prob_ev["code"] == "VALIDATION_FAILED"
    assert "Privacy face-blur verification failed" in prob_ev["detail"]

    # 3. Malformed JSON syntax
    r_malformed = client.post(
        "/v1/returns",
        headers={"Authorization": f"Bearer {shopper_token}", "Content-Type": "application/json"},
        content=b"{not valid json...",
    )
    assert r_malformed.status_code == 400
    prob_malformed = r_malformed.json()
    assert prob_malformed["code"] == "MALFORMED_JSON"


def test_aud06_zero_in_memory_state_persistence(repo: DatabaseRepository) -> None:
    """AUD-06 & J-04: All entities persist in DatabaseRepository and survive cross-app reinitialization."""
    app1 = create_app(repository=repo, demo_mode=True, mode="judge")
    client1 = TestClient(app1)
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")

    # 1. Create return through API
    r_create = client1.post(
        "/v1/returns",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={"order_id": "ord_demo_1", "reason_code": "SIZE_FIT"},
    )
    assert r_create.status_code in {200, 201}
    ret_id = r_create.json()["return_id"]

    # 2. Verify directly from DatabaseRepository
    db_ret = repo.get_return(ret_id)
    assert db_ret is not None
    assert db_ret.return_id == ret_id
    assert db_ret.state == "REQUESTED"
    assert db_ret.audit_seed_hex != ""
    assert db_ret.audit_commitment != ""

    # 3. Create a second app instance with the same database repository (simulating server restart)
    app2 = create_app(repository=repo, demo_mode=False, mode="judge")
    client2 = TestClient(app2)

    # 4. Fetch the return from app2
    r_get = client2.get(
        f"/v1/returns/{ret_id}",
        headers={"Authorization": f"Bearer {shopper_token}"},
    )
    assert r_get.status_code == 200
    assert r_get.json()["return_id"] == ret_id
    assert r_get.json()["state"] == "REQUESTED"


def test_rv03_dynamic_state_machine_guards(repo: DatabaseRepository) -> None:
    """RV-03 & J-04: Guards (within_window, exposure_cap, agent evidence bypass) computed from live database data."""
    app = create_app(repository=repo, demo_mode=True, mode="judge")
    client = TestClient(app)

    # 1. Dynamic return window check (within_window guard)
    # Create an expired order (60 days old, while window is 30 days)
    old_order_id = "ord_expired_test"
    repo.save_order(
        Order(
            order_id=old_order_id,
            merchant_id="merch_a",
            account_id="shopper_old",
            capture_amount_minor=10000,
            currency="USD",
            policy_version="pol_v1",
            created_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=60),
        )
    )
    repo.save_order_item(
        OrderItem(
            order_item_id="item_expired_test",
            order_id=old_order_id,
            sku="PR-EXP-01",
            price_minor=10000,
            currency="USD",
        )
    )
    old_ret_id = "ret_expired_test"
    repo.save_return(
        Return(
            return_id=old_ret_id,
            order_id=old_order_id,
            order_item_id="item_expired_test",
            merchant_id="merch_a",
            shopper_id="shopper_old",
            state="REQUESTED",
            lane="FAST",
            timing="R0",
            declared_grade="A",
            currency="USD",
        )
    )
    old_shopper_token = mint_shopper_token(order_id=old_order_id, shopper_id="shopper_old")
    r_expired_decl = client.post(
        f"/v1/returns/{old_ret_id}/declaration",
        headers={"Authorization": f"Bearer {old_shopper_token}"},
        json={
            "declared_grade": "A",
            "fast_lane_terms_accepted": True,
            "shopper_nonce": "nonce_expired",
        },
    )
    # Must fail with 409 INVALID_STATE_TRANSITION because within_window evaluated to False
    assert r_expired_decl.status_code == 409
    assert r_expired_decl.json()["code"] == "INVALID_STATE_TRANSITION"

    # 2. Dynamic exposure cap check (exposure_cap_ok guard)
    # Set merchant exposure to max
    merchant = repo.get_merchant("merch_a")
    assert merchant is not None
    merchant.outstanding_instant_exposure_minor = merchant.instant_exposure_cap_minor
    repo.save_merchant(merchant)

    # Set ret_demo_1 to ASSESSED with r0_tranche_minor > 0
    ret_demo = repo.get_return("ret_demo_1")
    assert ret_demo is not None
    ret_demo.state = "ASSESSED"
    ret_demo.r0_tranche_minor = 15000
    repo.save_return(ret_demo)

    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")
    r_dropoff = client.post(
        "/v1/returns/ret_demo_1/dropoff",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "seal_nonce": "SEAL-NONCE-01",
            "dropoff_photo_ref": "raw/ret_demo_1/dropoff.jpg",
            "carrier_tracking_number": "1Z999AA10123456784",
        },
    )
    # Must fail with 409 INVALID_STATE_TRANSITION because exposure cap is exceeded
    assert r_dropoff.status_code == 409
    assert r_dropoff.json()["code"] == "INVALID_STATE_TRANSITION"

    # 3. Agent token cannot bypass physical evidence inspection (INV-12, RV-03)
    tok_agent = mint_agent_token(
        agent_id="bot_assistant",
        order_id="ord_demo_1",
        merchant_id="merch_a",
        scopes=["read_policy", "declare", "keep_offer"],
    )
    ret_demo.state = "DECLARED"
    repo.save_return(ret_demo)

    r_agent_respond = client.post(
        "/v1/returns/ret_demo_1/keep-offer/respond",
        headers={"Authorization": f"Bearer {tok_agent}"},
        json={"action": "DECLINE"},
    )
    # Must be forbidden with 403 FORBIDDEN_ACTION
    assert r_agent_respond.status_code == 403
    assert r_agent_respond.json()["code"] == "FORBIDDEN_ACTION"


def test_rv04_keep_offer_price_consistency(repo: DatabaseRepository) -> None:
    """RV-04 & J-04: GET and POST respond return identical posted price computed from compute_posted_keep_offer()."""
    app = create_app(repository=repo, demo_mode=True, mode="judge")
    client = TestClient(app)
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")

    # Set ret_demo_1 to ASSESSED with assessment (Task T6 / RV-03: keep-offer ACCEPT only from ASSESSED)
    ret = repo.get_return("ret_demo_1")
    assert ret is not None
    ret.state = "ASSESSED"
    repo.save_return(ret)
    repo.save_assessment(Assessment(assessment_id="ass_demo_1", return_id="ret_demo_1", predicted_grade="B"))

    # 1. GET keep-offer
    r_get = client.get(
        "/v1/returns/ret_demo_1/keep-offer",
        headers={"Authorization": f"Bearer {shopper_token}"},
    )
    assert r_get.status_code == 200
    get_data = r_get.json()
    get_amount = get_data["posted_price"]["amount_minor"]
    assert get_amount > 0
    assert "k_max_minor" not in get_data  # Bounds never exposed (INV-06)

    # 2. POST respond
    r_post = client.post(
        "/v1/returns/ret_demo_1/keep-offer/respond",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={"action": "ACCEPT"},
    )
    assert r_post.status_code == 200
    post_data = r_post.json()
    post_amount = post_data["posted_price_minor"]

    # 3. Strict consistency check (GET amount == POST amount == DB record)
    assert get_amount == post_amount
    db_offer = repo.get_keep_offer_by_return("ret_demo_1")
    assert db_offer is not None
    assert db_offer.amount_minor == post_amount
    assert db_offer.status == "ACCEPTED"


def test_rv11_metrics_and_alerts_protection_and_route_templating(repo: DatabaseRepository) -> None:
    """RV-11 & TM-15: Protected /v1/metrics and /v1/ops/alerts endpoints and templated route path labels."""
    app = create_app(repository=repo, demo_mode=True, mode="judge")
    staff_token = mint_staff_token(merchant_id="merch_a", role="MERCHANT_ADMIN", sub="admin_01")
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")

    # A remote client from outside loopback
    remote_client = TestClient(app, client=("198.51.100.1", 54321))

    # 1. Remote unauthenticated request to /v1/metrics -> 401
    r_remote_unauth = remote_client.get("/v1/metrics")
    assert r_remote_unauth.status_code == 401

    # 2. Remote shopper request to /v1/metrics -> 403
    r_remote_shopper = remote_client.get("/v1/metrics", headers={"Authorization": f"Bearer {shopper_token}"})
    assert r_remote_shopper.status_code == 403

    # 3. Remote staff request to /v1/metrics -> 200
    r_remote_staff = remote_client.get("/v1/metrics", headers={"Authorization": f"Bearer {staff_token}"})
    assert r_remote_staff.status_code == 200
    assert "text/plain" in r_remote_staff.headers["Content-Type"]

    # 4. Remote unauthenticated request to /v1/ops/alerts -> 401
    r_alerts_unauth = remote_client.get("/v1/ops/alerts")
    assert r_alerts_unauth.status_code == 401

    # 5. Remote staff request to /v1/ops/alerts -> 200
    r_alerts_staff = remote_client.get("/v1/ops/alerts", headers={"Authorization": f"Bearer {staff_token}"})
    assert r_alerts_staff.status_code == 200
    assert "alerts" in r_alerts_staff.json()

    # 6. Loopback client access without auth -> 200
    loopback_client = TestClient(app, client=("127.0.0.1", 54321))
    r_loopback = loopback_client.get("/v1/metrics")
    assert r_loopback.status_code == 200

    # 7. Route templating check (TM-15): execute a request with dynamic ID
    loopback_client.get(
        "/v1/returns/ret_demo_1/challenge",
        headers={"Authorization": f"Bearer {shopper_token}"},
    )
    metrics_text = loopback_client.get("/v1/metrics").text
    # Metric labels must use templated route path, NOT raw return ID
    assert 'path="/v1/returns/{return_id}/challenge"' in metrics_text
    assert 'path="/v1/returns/ret_demo_1/challenge"' not in metrics_text


def test_aud29_reviewer_independence_on_appeals(repo: DatabaseRepository) -> None:
    """AUD-29 & FR-69: Same reviewer cannot decide an appeal; independent reviewer required."""
    app = create_app(repository=repo, demo_mode=True, mode="judge")
    client = TestClient(app)
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")
    rev1_token = mint_staff_token(merchant_id="merch_a", role="REVIEWER", sub="rev_alice")
    rev2_token = mint_staff_token(merchant_id="merch_a", role="REVIEWER", sub="rev_bob")

    # 1. File appeal indicating rev_alice as original reviewer
    with repo.get_session() as session:
        rev = session.get(Review, "rev_rec_demo_1")
        if rev:
            rev.reviewer_id = "rev_alice"
            session.add(rev)
            session.commit()

    r_appeal = client.post(
        "/v1/appeals",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "return_id": "ret_demo_1",
            "original_reviewer_id": "rev_alice",
            "subject": "Contesting minor wear classification",
            "disputed_delta_minor": 2000,
        },
    )
    assert r_appeal.status_code == 201
    appeal_id = r_appeal.json()["appeal_id"]

    # 2. rev_alice attempts to decide the appeal -> 409 SAME_REVIEWER_CONFLICT
    r_conflict = client.post(
        f"/v1/review/appeals/{appeal_id}/decision",
        headers={"Authorization": f"Bearer {rev1_token}"},
        json={"appeal_reviewer_id": "rev_alice", "outcome": "OVERTURNED"},
    )
    assert r_conflict.status_code == 409
    assert r_conflict.json()["code"] == "SAME_REVIEWER_CONFLICT"

    # 3. Independent rev_bob decides the appeal -> 200 OK
    r_success = client.post(
        f"/v1/review/appeals/{appeal_id}/decision",
        headers={"Authorization": f"Bearer {rev2_token}"},
        json={"appeal_reviewer_id": "rev_bob", "outcome": "OVERTURNED"},
    )
    assert r_success.status_code == 200
    assert r_success.json()["outcome"] == "OVERTURNED"
    assert r_success.json()["appeal_reviewer_id"] == "rev_bob"


def test_fr88_return_cancellation_endpoint(repo: DatabaseRepository) -> None:
    """FR-88: POST /v1/returns/{id}/cancel applies CANCEL_RETURN transition and blocks further actions."""
    app = create_app(repository=repo, demo_mode=True, mode="judge")
    client = TestClient(app)
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")

    # 1. Create a fresh return in REQUESTED state
    r_create = client.post(
        "/v1/returns",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={"order_id": "ord_demo_1", "reason_code": "ORDERED_ACCIDENT"},
    )
    assert r_create.status_code in {200, 201}
    ret_id = r_create.json()["return_id"]

    # 2. Cancel the return
    r_cancel = client.post(
        f"/v1/returns/{ret_id}/cancel",
        headers={"Authorization": f"Bearer {shopper_token}"},
    )
    assert r_cancel.status_code == 200
    assert r_cancel.json()["state"] == "CANCELLED"

    # 3. Verify state in DatabaseRepository
    db_ret = repo.get_return(ret_id)
    assert db_ret is not None
    assert db_ret.state == "CANCELLED"

    # 4. Attempting to submit declaration on cancelled return fails with 409
    r_decl = client.post(
        f"/v1/returns/{ret_id}/declaration",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "declared_grade": "A",
            "fast_lane_terms_accepted": True,
            "shopper_nonce": "nonce_after_cancel",
        },
    )
    assert r_decl.status_code == 409
    assert r_decl.json()["code"] == "INVALID_STATE_TRANSITION"


def test_aud14_signed_receipts_and_csprng_seed(repo: DatabaseRepository) -> None:
    """AUD-14, RV-02 & AUD-28: Signed receipts verified with platform Ed25519 key and persistent CSPRNG audit seed."""
    app = create_app(repository=repo, demo_mode=True, mode="judge")
    client = TestClient(app)
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")

    # Fetch receipt
    r_rcpt = client.get(
        "/v1/returns/ret_demo_1/receipts",
        headers={"Authorization": f"Bearer {shopper_token}"},
    )
    assert r_rcpt.status_code == 200
    receipt_data = r_rcpt.json()
    assert receipt_data["return_id"] == "ret_demo_1"
    receipts = receipt_data["receipts"]
    assert len(receipts) >= 1
    assert "signature" in receipts[0]
    assert "audit_commitment" in receipt_data

    # Verify cryptographic signature on receipt using platform Ed25519 public key
    from backend.domain.signing import get_platform_keypair, verify_message_ed25519

    _, plat_pub, _ = get_platform_keypair()
    assert verify_message_ed25519(plat_pub, receipts[0]["payload_hash"], receipts[0]["signature"]) is True
    assert receipts[0]["verified"] is True


def test_aud22_resale_order_authentication(repo: DatabaseRepository) -> None:
    """AUD-22: Unauthenticated resale order requests are rejected with 401."""
    app = create_app(repository=repo, demo_mode=True, mode="judge")
    client = TestClient(app)
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")
    admin_token = mint_staff_token(merchant_id="merch_a", role="MERCHANT_ADMIN", sub="admin_01")

    # 1. Admin lists resale item
    r_list = client.post(
        "/v1/resale/listings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"passport_id": "pass_demo_1", "verified_grade": "A", "price_minor": 29900},
    )
    assert r_list.status_code == 201
    listing_id = r_list.json()["listing_id"]

    # 2. Unauthenticated order request rejected
    r_unauth = client.post(f"/v1/resale/listings/{listing_id}/order")
    assert r_unauth.status_code == 401

    # 3. Authenticated order request succeeds
    r_order = client.post(
        f"/v1/resale/listings/{listing_id}/order",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={"new_owner_ref": "owner_secret_ref_2"},
    )
    assert r_order.status_code in {200, 201}
    assert r_order.json()["status"] == "SOLD_TRANSFERRED"
    assert r_order.json()["prior_owner_pii_stripped"] is True


def test_aud25_privacy_deletion_lifecycle(repo: DatabaseRepository) -> None:
    """AUD-25: Authenticated privacy deletion request triggers crypto-shredding key erasure."""
    app = create_app(repository=repo, demo_mode=True, mode="judge")
    client = TestClient(app)
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")

    r_del = client.post(
        "/v1/privacy/deletion-requests",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={"subject_id": "shopper_1", "requested_by": "shopper_1"},
    )
    assert r_del.status_code in {200, 202}
    del_data = r_del.json()
    assert del_data["status"] == "COMPLETED"
    assert del_data["dc3_subject_key_shredded"] is True
