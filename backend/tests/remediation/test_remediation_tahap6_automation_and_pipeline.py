"""Remediation Verification Test Suite for Tahap 6 / Option B (FR-97, FR-78, FR-62, FR-103, FR-52, FR-102).

Validates:
1. FR-97: SLAEscalationScanner auto-releases undisputed funds for ESCALATED returns exceeding 48h SLA to SETTLING (Section 26 T-SM34).
2. FR-78: KeepOfferExpirationScanner auto-expires unaccepted keep-offers after expiry timestamp.
3. FR-62 & FR-103: CusumAccountMonitorScanner detects repeated adjacent-grade mismatch drift, demotes trust tier by 1 step without fraud label, and resets score after review.
4. BackgroundAutomationScheduler: Lifecycle management (start, stop, run_once) and unified periodic job runner.
5. Section 25.1 & Section 27: Carrier events pipeline (POST /v1/carrier-events) transitions states (CARRIER_FIRST_SCAN -> IN_TRANSIT, CHECKIN_PASSED -> RECEIVED) and creates tamper-evident CustodyEvents.
6. FR-52 & FR-102: Direct settlement rule simulation pipeline (POST /v1/simulate) executing simulate_single_return_episode and policy evaluation.
"""

from __future__ import annotations

import datetime
from fractions import Fraction
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.db.models import CustodyEvent, KeepOffer, Order, OrderItem, Return, ShopperAccount
from backend.db.repository import DatabaseRepository
from backend.jobs.automation import (
    BackgroundAutomationScheduler,
    record_shopper_cusum_observation,
    run_all_automation_jobs,
    scan_and_evaluate_cusum_drift,
    scan_and_process_expired_keep_offers,
    scan_and_process_sla_escalations,
)


@pytest.fixture
def repo(tmp_path: Any) -> DatabaseRepository:
    """Provide a clean isolated DatabaseRepository with seeded demo data."""
    db_file = tmp_path / "tahap6_test.db"
    repository = DatabaseRepository(f"sqlite:///{db_file}", run_migrations_on_init=True)
    repository.seed_demo_data()
    return repository


def test_sla_escalation_auto_release_worker(repo: DatabaseRepository) -> None:
    """Verify SLAEscalationScanner auto-releases ESCALATED returns exceeding 48h SLA (FR-97, T-SM34)."""
    now = datetime.datetime.now(datetime.timezone.utc)

    # Create distinct order items for new returns
    repo.save_order_item(
        OrderItem(
            order_item_id="item_sla_exp_01",
            order_id="ord_demo_1",
            sku="PR-HP-XM5",
            price_minor=38000,
            currency="USD",
        )
    )
    repo.save_order_item(
        OrderItem(
            order_item_id="item_sla_act_01",
            order_id="ord_demo_1",
            sku="PR-HP-XM5",
            price_minor=38000,
            currency="USD",
        )
    )

    # 1. Return exceeding 48h SLA (e.g. 50 hours old)
    ret_expired = Return(
        return_id="ret_sla_expired_01",
        order_id="ord_demo_1",
        order_item_id="item_sla_exp_01",
        merchant_id="merch_demo_1",
        shopper_id="shopper_1",
        state="ESCALATED",
        lane="STANDARD",
        timing="ESC",
        declared_grade="B",
        disputed=False,
        currency="USD",
        created_at=now - datetime.timedelta(hours=50),
    )
    repo.save_return(ret_expired)

    # 2. Return within 48h SLA (e.g. 10 hours old)
    ret_active = Return(
        return_id="ret_sla_active_01",
        order_id="ord_demo_1",
        order_item_id="item_sla_act_01",
        merchant_id="merch_demo_1",
        shopper_id="shopper_1",
        state="ESCALATED",
        lane="STANDARD",
        timing="ESC",
        declared_grade="B",
        disputed=False,
        currency="USD",
        created_at=now - datetime.timedelta(hours=10),
    )
    repo.save_return(ret_active)

    # Scan and process SLA escalations
    processed = scan_and_process_sla_escalations(repo, current_time=now, sla_hours=48.0)

    assert len(processed) == 1
    assert processed[0]["return_id"] == "ret_sla_expired_01"
    assert processed[0]["previous_state"] == "ESCALATED"
    assert processed[0]["new_state"] == "SETTLING"
    assert processed[0]["action"] == "AUTO_RELEASE_UNDISPUTED_SLA"
    assert processed[0]["elapsed_hours"] >= 50.0

    # Verify database state
    db_expired = repo.get_return("ret_sla_expired_01")
    assert db_expired is not None
    assert db_expired.state == "SETTLING"

    db_active = repo.get_return("ret_sla_active_01")
    assert db_active is not None
    assert db_active.state == "ESCALATED"


def test_keep_offer_expiration_worker(repo: DatabaseRepository) -> None:
    """Verify KeepOfferExpirationScanner marks unaccepted offers EXPIRED past expires_at (FR-78)."""
    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Offer past expiration timestamp
    offer_expired = KeepOffer(
        offer_id="koff_expired_01",
        return_id="ret_koff_exp_01",
        amount_minor=5000,
        currency="USD",
        status="OFFERED",
        expires_at=now - datetime.timedelta(minutes=10),
    )
    repo.save_keep_offer(offer_expired)

    # 2. Offer still valid in the future
    offer_valid = KeepOffer(
        offer_id="koff_valid_01",
        return_id="ret_koff_val_01",
        amount_minor=5000,
        currency="USD",
        status="OFFERED",
        expires_at=now + datetime.timedelta(hours=2),
    )
    repo.save_keep_offer(offer_valid)

    expired_list = scan_and_process_expired_keep_offers(repo, current_time=now)

    assert len(expired_list) == 1
    assert expired_list[0]["offer_id"] == "koff_expired_01"
    assert expired_list[0]["status"] == "EXPIRED"

    # Verify DB records
    db_exp = repo.get_keep_offer("koff_expired_01")
    assert db_exp is not None
    assert db_exp.status == "EXPIRED"

    db_val = repo.get_keep_offer("koff_valid_01")
    assert db_val is not None
    assert db_val.status == "OFFERED"


def test_cusum_drift_account_demotion_worker(repo: DatabaseRepository) -> None:
    """Verify CusumAccountMonitorScanner demotes 1 tier and resets score without accusing fraud (FR-62, FR-103)."""
    # Shopper with score crossing threshold 4.0
    shopper_breached = ShopperAccount(
        account_id="shopper_breached_01",
        identity_group_id="id_grp_1",
        trust_tier="TRUSTED",
        cusum_score=4.25,
    )
    repo.save_shopper(shopper_breached)

    # Shopper with normal score
    shopper_ok = ShopperAccount(
        account_id="shopper_ok_01",
        identity_group_id="id_grp_2",
        trust_tier="ESTABLISHED",
        cusum_score=1.20,
    )
    repo.save_shopper(shopper_ok)

    downgrades = scan_and_evaluate_cusum_drift(repo, threshold_h=4.0)

    assert len(downgrades) == 1
    assert downgrades[0]["account_id"] == "shopper_breached_01"
    assert downgrades[0]["old_tier"] == "TRUSTED"
    assert downgrades[0]["new_tier"] == "ESTABLISHED"
    assert "No penalty fees applied" in downgrades[0]["explanation"]

    # Verify DB state: tier demoted by 1 step, score reset to 0.0 per FR-103
    db_breached = repo.get_shopper("shopper_breached_01")
    assert db_breached is not None
    assert db_breached.trust_tier == "ESTABLISHED"
    assert db_breached.cusum_score == 0.0

    db_ok = repo.get_shopper("shopper_ok_01")
    assert db_ok is not None
    assert db_ok.trust_tier == "ESTABLISHED"
    assert db_ok.cusum_score == 1.20

    # Test sequential demotion: ESTABLISHED -> NEW
    db_breached.cusum_score = 4.10
    repo.save_shopper(db_breached)
    downgrades_2 = scan_and_evaluate_cusum_drift(repo, threshold_h=4.0)
    assert len(downgrades_2) == 1
    assert downgrades_2[0]["old_tier"] == "ESTABLISHED"
    assert downgrades_2[0]["new_tier"] == "NEW"

    db_breached_new = repo.get_shopper("shopper_breached_01")
    assert db_breached_new is not None
    assert db_breached_new.trust_tier == "NEW"


def test_cusum_observation_recording(repo: DatabaseRepository) -> None:
    """Verify record_shopper_cusum_observation increases score for adjacent-grade mismatches."""
    shopper = ShopperAccount(
        account_id="shopper_obs_01",
        identity_group_id="id_grp_obs",
        trust_tier="TRUSTED",
        cusum_score=0.0,
    )
    repo.save_shopper(shopper)

    # Record first mismatch: should increase score
    score1, alarm1 = record_shopper_cusum_observation(
        repo, "shopper_obs_01", is_adjacent_below=True, theta0=Fraction(10, 100)
    )
    assert score1 > 0.0
    assert alarm1 is False

    # Record second mismatch
    score2, alarm2 = record_shopper_cusum_observation(
        repo, "shopper_obs_01", is_adjacent_below=True, theta0=Fraction(10, 100)
    )
    assert score2 > score1

    # Record honest match (not adjacent below): should decrease or floor at 0
    score3, alarm3 = record_shopper_cusum_observation(
        repo, "shopper_obs_01", is_adjacent_below=False, theta0=Fraction(10, 100)
    )
    assert score3 < score2


def test_background_automation_scheduler_lifecycle(repo: DatabaseRepository) -> None:
    """Verify BackgroundAutomationScheduler runs all jobs and manages lifecycle threads."""
    scheduler = BackgroundAutomationScheduler(repo, interval_seconds=0.2)

    # 1. Synchronous single run
    results = scheduler.run_once()
    assert "executed_at" in results
    assert "sla_escalations_processed" in results
    assert "keep_offers_expired" in results
    assert "cusum_drift_downgrades" in results

    # 2. Unified top-level runner
    unified_res = run_all_automation_jobs(repo)
    assert "executed_at" in unified_res

    # 3. Thread start and stop
    scheduler.start()
    assert scheduler._thread is not None
    assert scheduler._thread.is_alive()
    scheduler.stop()
    assert not scheduler._thread.is_alive()


def test_carrier_events_pipeline_state_and_custody(repo: DatabaseRepository) -> None:
    """Verify POST /v1/carrier-events executes real transitions and records CustodyEvents (Section 25.1, Section 27)."""
    app = create_app(repository=repo, demo_mode=True)
    client = TestClient(app)

    # Seed return in AWAITING_SHIPMENT
    ret = repo.get_return("ret_demo_1")
    assert ret is not None
    ret.state = "AWAITING_SHIPMENT"
    repo.save_return(ret)

    receiver_token = mint_staff_token(
        merchant_id="merch_demo_1",
        staff_id="staff_receiver_1",
        role="RECEIVER",
    )

    # 1. CARRIER_FIRST_SCAN -> advances to IN_TRANSIT
    resp1 = client.post(
        "/v1/carrier-events",
        headers={"Authorization": f"Bearer {receiver_token}"},
        json={"return_id": "ret_demo_1", "type": "CARRIER_FIRST_SCAN"},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["recorded"] is True
    assert data1["new_state"] == "IN_TRANSIT"
    assert "custody_event_id" in data1

    ce1 = repo.get_custody_event(data1["custody_event_id"])
    assert ce1 is not None
    assert ce1.interval_name == "CARRIER_FIRST_SCAN"
    assert ce1.seal_intact is True

    # 2. CHECKIN_PASSED -> advances from IN_TRANSIT to RECEIVED
    resp2 = client.post(
        "/v1/carrier-events",
        headers={"Authorization": f"Bearer {receiver_token}"},
        json={"return_id": "ret_demo_1", "type": "CHECKIN_PASSED"},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["recorded"] is True
    assert data2["new_state"] == "RECEIVED"
    assert "custody_event_id" in data2

    ce2 = repo.get_custody_event(data2["custody_event_id"])
    assert ce2 is not None
    assert ce2.interval_name == "CHECKIN_PASSED"

    # Verify return record state in DB
    db_ret = repo.get_return("ret_demo_1")
    assert db_ret is not None
    assert db_ret.state == "RECEIVED"


def test_carrier_events_auth_and_validation(repo: DatabaseRepository) -> None:
    """Verify POST /v1/carrier-events role and non-demo protections."""
    # Demo app: non-staff/non-receiver is forbidden
    app_demo = create_app(repository=repo, demo_mode=True)
    client_demo = TestClient(app_demo)

    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")
    resp_forbidden = client_demo.post(
        "/v1/carrier-events",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={"return_id": "ret_demo_1", "type": "CARRIER_FIRST_SCAN"},
    )
    assert resp_forbidden.status_code == 403

    # Non-demo app: manual injection is disabled (404 per TM-24)
    app_prod = create_app(repository=repo, demo_mode=False)
    client_prod = TestClient(app_prod)
    receiver_token = mint_staff_token(
        merchant_id="merch_demo_1",
        staff_id="staff_receiver_1",
        role="RECEIVER",
    )
    resp_prod = client_prod.post(
        "/v1/carrier-events",
        headers={"Authorization": f"Bearer {receiver_token}"},
        json={"return_id": "ret_demo_1", "type": "CARRIER_FIRST_SCAN"},
    )
    assert resp_prod.status_code == 404


def test_simulate_endpoint_with_policy_and_episode(repo: DatabaseRepository) -> None:
    """Verify POST /v1/simulate runs policy engine and simulation episode (FR-52, FR-102)."""
    app = create_app(repository=repo, demo_mode=True)
    client = TestClient(app)

    staff_token = mint_staff_token(
        merchant_id="merch_demo_1",
        staff_id="staff_admin_1",
        role="MERCHANT_ADMIN",
    )

    resp = client.post(
        "/v1/simulate",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={
            "price_minor": 45000,
            "declared_grade": "B",
            "tier": "TRUSTED",
            "has_origin_passport": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    # Core Policy Engine release outputs
    assert data["lane"] in {"FAST", "STANDARD", "REVIEW"}
    assert data["timing"] in {"R0", "R1", "ESC"}
    assert isinstance(data["x_released_minor"], int)
    assert isinstance(data["holdback_minor"], int)
    assert 0.0 <= data["audit_probability"] <= 1.0
    assert "binding_constraint" in data

    # Direct simulator episode result (FR-52, FR-102)
    assert "simulated_gain_minor" in data
    assert isinstance(data["simulated_gain_minor"], int)

    # Feasibility map & ROI view
    assert "feasibility_map" in data
    assert len(data["feasibility_map"]) > 0
    assert "roi" in data
    assert "annual_savings_usd" in data["roi"]
    assert "roi_multiple" in data["roi"]
