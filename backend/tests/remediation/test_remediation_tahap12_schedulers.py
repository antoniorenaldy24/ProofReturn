"""Tests for TASK T5: Run the schedulers from the application (RV2-02).

Required behavior:
1. Start both BackgroundAutomationScheduler and AlertScheduler in the FastAPI lifespan
   when settings.enable_scheduler is True (default True; tests set False unless testing).
   Stop them on shutdown.
2. Register jobs: SLA escalation, keep-offer expiry, CUSUM drift, alert evaluation,
   and the refund outbox executor from T4.
3. With more than one worker, only one instance runs jobs: Postgres pg_try_advisory_lock
   or a lease row. SQLite runs single-instance.
4. Each job run logs job name, duration, and result count.
"""

from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import time
from typing import Any
import pytest
from pydantic import SecretStr
from starlette.testclient import TestClient

from backend.api.app import create_app
from backend.config import ProofReturnSettings
from backend.db.models import KeepOffer, Order, RefundAction
from backend.db.repository import DatabaseRepository
from backend.jobs.automation import BackgroundAutomationScheduler
from backend.observability.metrics import AlertScheduler


VALID_BOOTSTRAP_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
VALID_WEBHOOK_SECRET = "webhooksecret0123456789abcdef0123456789abcdef0123456789abcdef"


class FakePayPalClient:
    """Fake PayPal Sandbox client for testing outbox executor inside the scheduler."""

    def __init__(self, mode: str = "success") -> None:
        self.mode = mode
        self.call_count = 0
        self.has_credentials = True

    def refund_capture_live(
        self,
        *,
        capture_id: str,
        request_id: str,
        amount_minor: int,
        currency: str = "USD",
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.call_count += 1
        return {
            "id": f"PP-REF-{request_id[:8]}",
            "capture_id": capture_id,
            "request_id": request_id,
            "status": "COMPLETED",
            "amount_minor": amount_minor,
            "currency": currency,
            "paypal_debug_id": f"dbg_sched_{request_id[:8]}",
        }


def test_lifespan_starts_and_stops_schedulers(tmp_path: Path) -> None:
    """FastAPI lifespan starts BackgroundAutomationScheduler and AlertScheduler when enable_scheduler=True and stops them on shutdown."""
    db_file = tmp_path / "test_sched_lifespan.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)
    repo.seed_demo_data()

    settings = ProofReturnSettings(
        enable_scheduler=True,
        scheduler_interval_seconds=60.0,
        demo_mode=True,
        demo_bootstrap_key=SecretStr(VALID_BOOTSTRAP_KEY),
        demo_webhook_secret=SecretStr(VALID_WEBHOOK_SECRET),
    )
    app = create_app(repository=repo, settings=settings)

    # Before entering lifespan context manager
    assert hasattr(app.state, "automation_scheduler")
    assert hasattr(app.state, "alert_scheduler")
    assert not app.state.automation_scheduler.is_running
    assert not app.state.alert_scheduler.is_running

    # Inside lifespan context manager
    with TestClient(app) as client:
        assert app.state.automation_scheduler.is_running is True
        assert app.state.alert_scheduler.is_running is True

    # After lifespan shutdown
    assert app.state.automation_scheduler.is_running is False
    assert app.state.alert_scheduler.is_running is False


def test_registered_jobs_include_sla_keep_offer_cusum_alerts_outbox(tmp_path: Path) -> None:
    """Registered jobs in the automation scheduler must include SLA escalation, keep-offer expiry, CUSUM drift, alert evaluation, and refund outbox executor."""
    db_file = tmp_path / "test_sched_jobs.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)
    settings = ProofReturnSettings(
        enable_scheduler=True,
        demo_mode=True,
        demo_bootstrap_key=SecretStr(VALID_BOOTSTRAP_KEY),
        demo_webhook_secret=SecretStr(VALID_WEBHOOK_SECRET),
    )
    app = create_app(repository=repo, settings=settings)
    scheduler = app.state.automation_scheduler

    assert hasattr(scheduler, "registered_jobs"), "Scheduler must expose registered_jobs"
    registered = scheduler.registered_jobs
    job_keys = [k.lower() for k in registered.keys()] if isinstance(registered, dict) else [str(j).lower() for j in registered]

    assert any("sla" in k for k in job_keys), f"SLA escalation job not found in {job_keys}"
    assert any("keep_offer" in k or "expiry" in k for k in job_keys), f"Keep-offer expiry job not found in {job_keys}"
    assert any("cusum" in k for k in job_keys), f"CUSUM drift job not found in {job_keys}"
    assert any("alert" in k for k in job_keys), f"Alert evaluation job not found in {job_keys}"
    assert any("outbox" in k or "refund" in k for k in job_keys), f"Refund outbox job not found in {job_keys}"


def test_only_one_scheduler_holds_the_lease(tmp_path: Path) -> None:
    """When multiple worker schedulers target the same database, only one instance holds the execution lease (RV2-02)."""
    db_file = tmp_path / "test_sched_lease.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)

    sched1 = BackgroundAutomationScheduler(repo=repo, holder_id="worker_alpha", interval_seconds=10.0)
    sched2 = BackgroundAutomationScheduler(repo=repo, holder_id="worker_beta", interval_seconds=10.0)

    assert hasattr(sched1, "lease_coordinator"), "BackgroundAutomationScheduler must have lease_coordinator"
    assert hasattr(sched2, "lease_coordinator"), "BackgroundAutomationScheduler must have lease_coordinator"

    # Worker alpha acquires lease
    assert sched1.lease_coordinator.acquire_lease() is True
    assert sched1.lease_coordinator.is_leader is True

    # Worker beta attempts to acquire same lease -> rejected
    assert sched2.lease_coordinator.acquire_lease() is False
    assert sched2.lease_coordinator.is_leader is False

    # Worker alpha releases lease
    sched1.lease_coordinator.release_lease()
    assert sched1.lease_coordinator.is_leader is False

    # Worker beta can now acquire lease
    assert sched2.lease_coordinator.acquire_lease() is True
    assert sched2.lease_coordinator.is_leader is True


def test_expired_keep_offer_is_expired_by_running_app(tmp_path: Path) -> None:
    """Starting the app without calling run_once directly expires an expired keep-offer and executes a PLANNED refund via the background scheduler (RV2-02)."""
    db_file = tmp_path / "test_sched_integration.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)
    repo.seed_demo_data()

    # 1. Setup expired keep-offer in DB
    now = datetime.now(UTC)
    past_expiry = now - timedelta(hours=2)
    offer = KeepOffer(
        offer_id="ko_t5_expired_test",
        return_id="ret_demo_1",
        amount_minor=5000,
        currency="USD",
        status="OFFERED",
        expires_at=past_expiry,
    )
    repo.save_keep_offer(offer)

    # 2. Setup PLANNED refund action in DB
    order = Order(
        order_id="ord_t5_sched",
        merchant_id="merch_a",
        account_id="shopper_1",
        policy_version="pol_electronics_us_v1",
        paypal_order_id="PP-ORD-T5",
        capture_id="CAP_T5_REAL",
        capture_amount_minor=38000,
        confirmed_refunded_minor=0,
        pending_refunded_minor=15000,
        currency="USD",
    )
    repo.save_order(order)
    action = RefundAction(
        request_id="req_t5_auto_refund",
        merchant_id="merch_a",
        order_id="ord_t5_sched",
        return_id="ret_demo_1",
        decision_id="dec_t5_auto",
        capture_id="CAP_T5_REAL",
        tranche="R0",
        amount_minor=15000,
        currency="USD",
        status="PLANNED",
        attempt_count=0,
    )
    repo.save_refund_action(action)

    # 3. Setup fake PayPal client that reports success
    fake_paypal = FakePayPalClient(mode="success")

    # 4. Start app with fast scheduler interval
    settings = ProofReturnSettings(
        enable_scheduler=True,
        scheduler_interval_seconds=0.05,
        demo_mode=True,
        demo_bootstrap_key=SecretStr(VALID_BOOTSTRAP_KEY),
        demo_webhook_secret=SecretStr(VALID_WEBHOOK_SECRET),
    )
    app = create_app(repository=repo, settings=settings, paypal_client=fake_paypal)

    # DO NOT call run_once directly! Only start the app via TestClient context manager
    with TestClient(app) as client:
        # Wait up to 3s for background thread to execute the jobs
        for _ in range(30):
            time.sleep(0.1)
            updated_offer = repo.get_keep_offer("ko_t5_expired_test")
            updated_act = repo.get_refund_action("req_t5_auto_refund")
            if (
                updated_offer
                and updated_offer.status == "EXPIRED"
                and updated_act
                and updated_act.status == "CONFIRMED"
            ):
                break

    # 5. Verify results through the DB
    final_offer = repo.get_keep_offer("ko_t5_expired_test")
    assert final_offer is not None
    assert final_offer.status == "EXPIRED"

    final_act = repo.get_refund_action("req_t5_auto_refund")
    assert final_act is not None
    assert final_act.status == "CONFIRMED"

    final_order = repo.get_order("ord_t5_sched")
    assert final_order is not None
    assert final_order.pending_refunded_minor == 0
    assert final_order.confirmed_refunded_minor == 15000
