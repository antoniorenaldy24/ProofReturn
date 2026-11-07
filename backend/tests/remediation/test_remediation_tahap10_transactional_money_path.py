"""Tests for TASK T3: Transactional money path (RV2-04 HIGH, AUD-02 capture id).

Requirements:
1. Remove broad exception swallowing; Over-refund -> 409 REFUND_LIMIT_EXCEEDED.
2. Planning a refund is ONE database transaction with order row locking, recomputing
   remaining balance, inserting RefundAction, and incrementing pending_refunded_minor atomically.
3. The DB is the source of truth for INV-01; in-memory ledger is rebuilt from DB (orders AND actions) at startup.
4. Use Order.capture_id everywhere. Missing capture_id -> 409 CAPTURE_MISSING, nothing persisted. No f"CAP-{...}".
5. Review: InvalidStateTransitionError -> 409 INVALID_STATE_TRANSITION, with no side effects.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from pydantic import SecretStr
from starlette.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.config import ProofReturnSettings
from backend.db.models import Order, Return, OrderItem, Policy, ShopperAccount
from backend.db.repository import DatabaseRepository


VALID_BOOTSTRAP_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
VALID_WEBHOOK_SECRET = "webhooksecret0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture
def test_repo(tmp_path: Path) -> DatabaseRepository:
    db_file = tmp_path / "test_t3.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)
    repo.seed_demo_data()
    return repo


@pytest.fixture
def demo_settings() -> ProofReturnSettings:
    return ProofReturnSettings(
        demo_mode=True,
        demo_bootstrap_key=SecretStr(VALID_BOOTSTRAP_KEY),
        demo_webhook_secret=SecretStr(VALID_WEBHOOK_SECRET),
    )


def test_over_refund_via_evidence_endpoint_returns_409_and_persists_nothing(
    test_repo: DatabaseRepository, demo_settings: ProofReturnSettings
) -> None:
    """Over-refund during evidence processing returns 409 REFUND_LIMIT_EXCEEDED and rolls back everything."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    # ord_demo_1 has capture_amount_minor = 38000
    # Simulate order almost fully refunded: pending 37000, so remaining is only 1000 minor
    order = test_repo.get_order("ord_demo_1")
    assert order is not None
    order.pending_refunded_minor = 37000
    test_repo.save_order(order)

    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")

    # Fast lane R0 calculation for $380 item is 21249 minor, which exceeds remaining (1000 minor)
    resp = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "faces_detected": 0,
            "object_key": "raw_evidence/test_over_refund.mp4",
            "challenge_step": 1,
            "client_blur_applied": True,
            "blur_latency_ms": 12.5,
            "text_in_media": test_repo.get_return("ret_demo_1").challenge_nonce,
        },
    )

    assert resp.status_code == 409
    body = resp.json()
    assert body.get("code") == "REFUND_LIMIT_EXCEEDED"

    # Verify NOTHING was persisted
    assert len(test_repo.get_return_evidence("ret_demo_1")) == 0
    assert test_repo.get_latest_assessment("ret_demo_1") is None
    assert test_repo.get_latest_decision("ret_demo_1") is None
    assert len(test_repo.list_refund_actions_by_return("ret_demo_1")) == 0
    # Order pending_refunded_minor unchanged
    order_after = test_repo.get_order("ord_demo_1")
    assert order_after is not None
    assert order_after.pending_refunded_minor == 37000


def test_over_refund_via_review_endpoint_returns_409(
    test_repo: DatabaseRepository, demo_settings: ProofReturnSettings
) -> None:
    """Over-refund during warehouse review settlement returns 409 REFUND_LIMIT_EXCEEDED."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    order = test_repo.get_order("ord_demo_1")
    assert order is not None
    # Set pending close to capture so additional settlement refund cannot fit
    order.pending_refunded_minor = 37500
    test_repo.save_order(order)

    reviewer_token = mint_staff_token(merchant_id="merch_a", role="REVIEWER", sub="rev_01")

    resp = client.post(
        "/v1/review/ret_demo_1/decision",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={
            "verified_grade": "B",
            "outcome": "CONFIRMED",
            "notes": "Grade confirmed new review notes",
        },
    )

    assert resp.status_code == 409
    body = resp.json()
    assert body.get("code") == "REFUND_LIMIT_EXCEEDED"

    # Verify NO new review and NO refund action persisted
    latest_review = test_repo.get_latest_review_by_return("ret_demo_1")
    assert latest_review is None or latest_review.notes != "Grade confirmed new review notes"
    actions = [a for a in test_repo.list_refund_actions_by_return("ret_demo_1") if a.tranche == "SETTLEMENT"]
    assert len(actions) == 0


def test_remaining_refundable_survives_app_restart(
    test_repo: DatabaseRepository, demo_settings: ProofReturnSettings
) -> None:
    """Rebuilding ledger from DB rehydrates orders AND actions across app restarts."""
    app1 = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client1 = TestClient(app1)

    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")

    # Plan R0 refund via app1
    resp = client1.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "faces_detected": 0,
            "object_key": "raw_evidence/test_restart.mp4",
            "challenge_step": 1,
            "client_blur_applied": True,
            "blur_latency_ms": 12.5,
            "text_in_media": test_repo.get_return("ret_demo_1").challenge_nonce,
        },
    )
    assert resp.status_code == 200
    r0_amt = resp.json()["r0_tranche_minor"]
    assert r0_amt > 0

    # Restart: instantiate app2 with the exact same DB
    app2 = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client2 = TestClient(app2)

    # In app2, order.pending_refunded_minor and existing actions are rehydrated
    order = test_repo.get_order("ord_demo_1")
    assert order is not None
    assert order.pending_refunded_minor == r0_amt

    # Review in app2: attempting to refund more than remaining must fail with 409
    reviewer_token = mint_staff_token(merchant_id="merch_a", role="REVIEWER", sub="rev_01")
    # Artificially bump confirmed refunds so total would exceed capture
    order.confirmed_refunded_minor = 38000 - r0_amt
    test_repo.save_order(order)

    # Now remaining = 38000 - (38000 - r0_amt) - r0_amt = 0
    resp_over = client2.post(
        "/v1/review/ret_demo_1/decision",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={
            "verified_grade": "B",
            "outcome": "CONFIRMED",
            "notes": "Attempt refund with 0 remaining",
        },
    )
    assert resp_over.status_code == 409
    assert resp_over.json().get("code") == "REFUND_LIMIT_EXCEEDED"


def test_pending_refunded_minor_updated_atomically(
    test_repo: DatabaseRepository, demo_settings: ProofReturnSettings
) -> None:
    """Planning a refund increments order.pending_refunded_minor atomically."""
    order_before = test_repo.get_order("ord_demo_1")
    assert order_before is not None
    assert order_before.pending_refunded_minor == 0

    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")

    resp = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "faces_detected": 0,
            "object_key": "raw_evidence/test_atomic.mp4",
            "challenge_step": 1,
            "client_blur_applied": True,
            "blur_latency_ms": 12.5,
            "text_in_media": test_repo.get_return("ret_demo_1").challenge_nonce,
        },
    )
    assert resp.status_code == 200
    r0_amt = resp.json()["r0_tranche_minor"]
    assert r0_amt > 0

    order_after = test_repo.get_order("ord_demo_1")
    assert order_after is not None
    assert order_after.pending_refunded_minor == r0_amt


def test_refund_uses_order_capture_id(
    test_repo: DatabaseRepository, demo_settings: ProofReturnSettings
) -> None:
    """RefundAction uses the genuine Order.capture_id from the database."""
    order = test_repo.get_order("ord_demo_1")
    assert order is not None
    order.capture_id = "REAL_PAYPAL_CAPTURE_123456"
    test_repo.save_order(order)

    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")

    resp = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "faces_detected": 0,
            "object_key": "raw_evidence/test_cap_id.mp4",
            "challenge_step": 1,
            "client_blur_applied": True,
            "blur_latency_ms": 12.5,
            "text_in_media": test_repo.get_return("ret_demo_1").challenge_nonce,
        },
    )
    assert resp.status_code == 200

    actions = test_repo.list_refund_actions_by_return("ret_demo_1")
    assert len(actions) >= 1
    assert actions[0].capture_id == "REAL_PAYPAL_CAPTURE_123456"


def test_missing_capture_id_blocks_planning(
    test_repo: DatabaseRepository, demo_settings: ProofReturnSettings
) -> None:
    """Missing or empty capture_id blocks refund planning with 409 CAPTURE_MISSING."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    order = test_repo.get_order("ord_demo_1")
    assert order is not None
    order.capture_id = ""
    test_repo.save_order(order)

    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")

    resp = client.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "faces_detected": 0,
            "object_key": "raw_evidence/test_missing_cap.mp4",
            "challenge_step": 1,
            "client_blur_applied": True,
            "blur_latency_ms": 12.5,
            "text_in_media": test_repo.get_return("ret_demo_1").challenge_nonce,
        },
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body.get("code") == "CAPTURE_MISSING"

    # Persists nothing
    assert len(test_repo.get_return_evidence("ret_demo_1")) == 0
    assert len(test_repo.list_refund_actions_by_return("ret_demo_1")) == 0


def test_review_invalid_transition_returns_409(
    test_repo: DatabaseRepository, demo_settings: ProofReturnSettings
) -> None:
    """Review decision on a return in an unreviewable state returns 409 INVALID_STATE_TRANSITION with no side effects."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    ret = test_repo.get_return("ret_demo_1")
    assert ret is not None
    ret.state = "REJECTED"  # terminal state, cannot transition
    test_repo.save_return(ret)

    reviewer_token = mint_staff_token(merchant_id="merch_a", role="REVIEWER", sub="rev_01")

    resp = client.post(
        "/v1/review/ret_demo_1/decision",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={
            "verified_grade": "B",
            "outcome": "CONFIRMED",
            "notes": "Attempt review on terminal state",
        },
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body.get("code") == "INVALID_STATE_TRANSITION"

    # Zero side effects: no review record with this note, no settlement refund actions, state remains REJECTED
    latest_review = test_repo.get_latest_review_by_return("ret_demo_1")
    assert latest_review is None or latest_review.notes != "Attempt review on terminal state"
    actions = [a for a in test_repo.list_refund_actions_by_return("ret_demo_1") if a.tranche == "SETTLEMENT"]
    assert len(actions) == 0
    assert test_repo.get_return("ret_demo_1").state == "REJECTED"


def test_concurrent_planning_never_exceeds_capture(
    test_repo: DatabaseRepository, demo_settings: ProofReturnSettings
) -> None:
    """Concurrent threads against the API never exceed capture_amount_minor."""
    # Create an order with exactly 30000 minor capture
    order_id = "ord_concurrent_1"
    test_repo.save_order(
        Order(
            order_id=order_id,
            merchant_id="merch_a",
            account_id="shopper_1",
            policy_version="pol_electronics_us_v1",
            paypal_order_id="PP-CONCURRENT",
            capture_id="CAP_CONCURRENT_01",
            capture_amount_minor=30000,
            confirmed_refunded_minor=0,
            pending_refunded_minor=0,
            currency="USD",
        )
    )

    # Create 5 returns for items on this order
    returns = []
    for i in range(5):
        item_id = f"item_conc_{i}"
        ret_id = f"ret_conc_{i}"
        test_repo.save_order_item(
            OrderItem(
                order_item_id=item_id,
                order_id=order_id,
                passport_id=None,
                sku="PR-CONC",
                price_minor=30000,
                currency="USD",
            )
        )
        test_repo.save_return(
            Return(
                return_id=ret_id,
                order_id=order_id,
                order_item_id=item_id,
                merchant_id="merch_a",
                shopper_id="shopper_1",
                state="DECLARED",
                lane="FAST",
                timing="R0",
                declared_grade="B",
                consent_recorded=True,
                challenge_nonce="NONCE-DEMO-9876",
                r0_tranche_minor=0,
                currency="USD",
            )
        )
        returns.append(ret_id)

    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    shopper_token = mint_shopper_token(order_id=order_id, shopper_id="shopper_1")

    def submit_ev(ret_id: str) -> int:
        resp = client.post(
            f"/v1/returns/{ret_id}/evidence",
            headers={"Authorization": f"Bearer {shopper_token}"},
            json={
                "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef",
                "faces_detected": 0,
                "object_key": f"raw_evidence/{ret_id}.mp4",
                "challenge_step": 1,
                "client_blur_applied": True,
                "blur_latency_ms": 10.0,
                "text_in_media": "NONCE-DEMO-9876",
            },
        )
        return resp.status_code

    with ThreadPoolExecutor(max_workers=5) as executor:
        status_codes = list(executor.map(submit_ev, returns))

    # At least one will succeed (200), and any that exceed 30000 must fail with 409
    assert 200 in status_codes
    order_final = test_repo.get_order(order_id)
    assert order_final is not None
    assert order_final.pending_refunded_minor <= 30000
    assert order_final.confirmed_refunded_minor + order_final.pending_refunded_minor <= order_final.capture_amount_minor
