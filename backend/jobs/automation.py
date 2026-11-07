"""Background Automation Workers and Periodic Timers (Section 8.4, Section 8.7, Section 27, FR-62, FR-78, FR-97, FR-103).

Provides automated background processes:
1. SLAEscalationScanner: Auto-releases undisputed funds for ESCALATED returns exceeding 48h SLA (FR-97).
2. KeepOfferExpirationScanner: Auto-expires unaccepted keep-offers after expiry timestamp (FR-78).
3. CusumAccountMonitorScanner: Detects repeated adjacent-grade mismatch drift and applies single-step tier demotion without accusing fraud (FR-62, FR-103).
4. BackgroundAutomationScheduler: Daemon scheduler executing automation jobs periodically.
"""

from __future__ import annotations

from collections.abc import Callable
import logging
import secrets
import threading
import time
from datetime import UTC, datetime
from fractions import Fraction
from typing import Any

from backend.db.models import KeepOffer, Return, ShopperAccount
from backend.db.repository import DatabaseRepository
from backend.domain.account_monitor import CusumConfig, CusumMonitor
from backend.observability.metrics import evaluate_alerts

logger = logging.getLogger("proofreturn.automation")


def scan_and_process_sla_escalations(
    repo: DatabaseRepository,
    current_time: datetime | None = None,
    sla_hours: float = 48.0,
) -> list[dict[str, Any]]:
    """Scan ESCALATED returns and automatically release undisputed funds when SLA expires (FR-97)."""
    now = current_time or datetime.now(UTC)
    escalated_returns = repo.list_returns(state="ESCALATED")
    processed: list[dict[str, Any]] = []

    for ret in escalated_returns:
        created_at = ret.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        elapsed_seconds = (now - created_at).total_seconds()
        sla_exceeded = elapsed_seconds >= sla_hours * 3600.0
        if sla_exceeded:
            # Section 26 Transition #34 (T-SM34): JURISDICTION_DEADLINE_REACHED with sla_exceeded computed from data
            updated_ret = repo.apply_return_transition(
                ret.return_id,
                "JURISDICTION_DEADLINE_REACHED",
                sla_exceeded=sla_exceeded,
            )
            processed.append({
                "return_id": ret.return_id,
                "previous_state": "ESCALATED",
                "new_state": updated_ret.state,
                "elapsed_hours": elapsed_seconds / 3600.0,
                "action": "AUTO_RELEASE_UNDISPUTED_SLA",
            })
            logger.info(
                f"[SLA-AUTO-RELEASE] Return {ret.return_id} exceeded {sla_hours}h SLA ({elapsed_seconds / 3600:.1f}h). "
                f"Auto-transitioned to {updated_ret.state} per FR-97."
            )

    return processed


def scan_and_process_expired_keep_offers(
    repo: DatabaseRepository,
    current_time: datetime | None = None,
) -> list[dict[str, Any]]:
    """Scan active (OFFERED/PENDING) keep offers and mark them EXPIRED when expires_at timestamp has passed (FR-78)."""
    now = current_time or datetime.now(UTC)
    pending_offers = repo.list_pending_keep_offers()
    expired: list[dict[str, Any]] = []

    for offer in pending_offers:
        exp = offer.expires_at
        if exp is not None:
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if exp < now:
                offer.status = "EXPIRED"
                repo.save_keep_offer(offer)
                expired.append({
                    "offer_id": offer.offer_id,
                    "return_id": offer.return_id,
                    "expires_at": exp.isoformat(),
                    "status": "EXPIRED",
                })
                logger.info(f"[KEEP-OFFER-EXPIRED] Keep offer {offer.offer_id} expired at {exp.isoformat()}.")

    return expired


def record_shopper_cusum_observation(
    repo: DatabaseRepository,
    account_id: str,
    is_adjacent_below: bool,
    theta0: Fraction | None = None,
) -> tuple[float, bool]:
    """Record an adjacent-grade mismatch observation for a shopper and update DB score (FR-62, FR-103)."""
    shopper = repo.get_shopper(account_id)
    if not shopper:
        raise ValueError(f"Shopper account {account_id} not found.")

    cfg = CusumConfig.for_category_theta0(theta0 or Fraction(10, 100))
    monitor = CusumMonitor(config=cfg)
    monitor.cusum_value = Fraction(int(round(shopper.cusum_score * 1000)), 1000)
    alarm = monitor.observe(is_adjacent_below=is_adjacent_below)

    shopper.cusum_score = float(monitor.cusum_value)
    repo.save_shopper(shopper)
    return shopper.cusum_score, alarm


def scan_and_evaluate_cusum_drift(
    repo: DatabaseRepository,
    threshold_h: float = 4.0,
) -> list[dict[str, Any]]:
    """Evaluate CUSUM drift on shopper accounts; downgrade 1 trust tier when threshold exceeded (FR-62, FR-103)."""
    shoppers = repo.list_shoppers()
    downgrades: list[dict[str, Any]] = []

    tier_demotion_map = {
        "TRUSTED": "ESTABLISHED",
        "ESTABLISHED": "NEW",
        "NEW": "RESTRICTED",
        "RESTRICTED": "RESTRICTED",
    }

    for shopper in shoppers:
        if shopper.cusum_score >= threshold_h:
            old_tier = shopper.trust_tier
            new_tier = tier_demotion_map.get(old_tier, "RESTRICTED")
            shopper.trust_tier = new_tier
            # Reset score after review action per FR-103
            shopper.cusum_score = 0.0
            repo.save_shopper(shopper)

            downgrades.append({
                "account_id": shopper.account_id,
                "old_tier": old_tier,
                "new_tier": new_tier,
                "cusum_score_triggered": threshold_h,
                "explanation": "Account trust tier adjusted based on return condition variance pattern. No penalty fees applied.",
            })
            logger.warning(
                f"[CUSUM-DRIFT-ALARM] Shopper {shopper.account_id} crossed CUSUM threshold ({threshold_h}). "
                f"Demoted tier {old_tier} -> {new_tier} without fraud label (FR-62)."
            )

    return downgrades


def run_all_automation_jobs(
    repo: DatabaseRepository,
    current_time: datetime | None = None,
) -> dict[str, Any]:
    """Execute all automation jobs synchronously and return comprehensive execution report."""
    sla_results = scan_and_process_sla_escalations(repo, current_time=current_time)
    keep_results = scan_and_process_expired_keep_offers(repo, current_time=current_time)
    cusum_results = scan_and_evaluate_cusum_drift(repo)
    return {
        "executed_at": (current_time or datetime.now(UTC)).isoformat(),
        "sla_escalations_processed": sla_results,
        "keep_offers_expired": keep_results,
        "cusum_drift_downgrades": cusum_results,
    }


class SchedulerLeaseCoordinator:
    """Coordinates leader election across scheduler instances via lease rows or Postgres advisory locks (RV2-02)."""

    def __init__(
        self,
        repo: DatabaseRepository,
        lease_name: str = "automation_scheduler",
        holder_id: str | None = None,
        ttl_seconds: float = 30.0,
    ) -> None:
        self.repo = repo
        self.lease_name = lease_name
        self.holder_id = holder_id or f"worker_{secrets.token_hex(6)}"
        self.ttl_seconds = ttl_seconds
        self.is_leader = False

    def acquire_lease(self) -> bool:
        """Attempt to acquire or renew the leadership lease."""
        acquired = self.repo.acquire_scheduler_lease(
            lease_name=self.lease_name,
            holder_id=self.holder_id,
            ttl_seconds=self.ttl_seconds,
        )
        self.is_leader = acquired
        return acquired

    def release_lease(self) -> bool:
        """Release the leadership lease."""
        released = self.repo.release_scheduler_lease(
            lease_name=self.lease_name,
            holder_id=self.holder_id,
        )
        self.is_leader = False
        return released


class ScheduledJob:
    """Metadata and execution wrapper for a registered periodic automation job (RV2-02)."""

    def __init__(
        self,
        name: str,
        fn: Callable[[], Any],
        interval_seconds: float | None = None,
    ) -> None:
        self.name = name
        self.fn = fn
        self.interval_seconds = interval_seconds
        self.last_run: datetime | None = None
        self.last_duration_seconds: float = 0.0
        self.last_result_count: int = 0


class BackgroundAutomationScheduler:
    """Threaded background automation daemon running jobs at periodic intervals with leader election (Section 34.2, RV2-02)."""

    def __init__(
        self,
        repo: DatabaseRepository,
        interval_seconds: float = 60.0,
        holder_id: str | None = None,
        metrics: Any | None = None,
        outbox_executor: Any | None = None,
        run_on_start: bool = True,
    ) -> None:
        self.repo = repo
        self.interval_seconds = interval_seconds
        self.metrics = metrics
        self.outbox_executor = outbox_executor
        self.run_on_start = run_on_start
        self.lease_coordinator = SchedulerLeaseCoordinator(
            repo=repo,
            lease_name="automation_scheduler",
            holder_id=holder_id,
            ttl_seconds=max(30.0, interval_seconds * 2),
        )
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._jobs: dict[str, ScheduledJob] = {}

        # Register canonical automation jobs (RV2-02)
        self._register_default_jobs()

    def _register_default_jobs(self) -> None:
        self.register_job("sla_escalation", lambda: scan_and_process_sla_escalations(self.repo))
        self.register_job("keep_offer_expiry", lambda: scan_and_process_expired_keep_offers(self.repo))
        self.register_job("cusum_drift", lambda: scan_and_evaluate_cusum_drift(self.repo))
        self.register_job(
            "alert_evaluation",
            lambda: (evaluate_alerts(self.metrics) if self.metrics else []),
        )
        self.register_job(
            "refund_outbox",
            lambda: (self.outbox_executor.run_once(limit=10) if self.outbox_executor else {"processed": 0}),
        )

    def register_job(self, name: str, fn: Callable[[], Any], interval_seconds: float | None = None) -> None:
        self._jobs[name] = ScheduledJob(name=name, fn=fn, interval_seconds=interval_seconds)

    @property
    def registered_jobs(self) -> dict[str, ScheduledJob]:
        return self._jobs

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name=f"AutomationScheduler-{self.lease_coordinator.holder_id[:8]}",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self.lease_coordinator.release_lease()

    def _count_results(self, res: Any) -> int:
        if isinstance(res, list):
            return len(res)
        if isinstance(res, dict):
            if "confirmed" in res:
                return int(res["confirmed"])
            if "processed" in res:
                return int(res["processed"])
            return len(res)
        if isinstance(res, int):
            return res
        return 1 if res else 0

    def run_once(self) -> dict[str, Any]:
        """Execute all registered jobs under leader lease and log name, duration, result count (RV2-02)."""
        if not self.lease_coordinator.acquire_lease():
            logger.debug("[SCHEDULER] Not lease leader; skipping automation pass.")
            return {"status": "SKIPPED_NOT_LEADER"}

        execution_results: dict[str, Any] = {}
        for job_name, job in list(self._jobs.items()):
            start_time = time.perf_counter()
            try:
                res = job.fn()
                duration = time.perf_counter() - start_time
                count = self._count_results(res)
                job.last_run = datetime.now(UTC)
                job.last_duration_seconds = duration
                job.last_result_count = count
                logger.info(
                    "[JOB-RUN] job=%s duration=%.4fs result_count=%d",
                    job_name,
                    duration,
                    count,
                )
                execution_results[job_name] = res
            except Exception as exc:
                duration = time.perf_counter() - start_time
                logger.exception(
                    "[JOB-RUN-ERROR] job=%s duration=%.4fs error=%s",
                    job_name,
                    duration,
                    exc,
                )
                execution_results[job_name] = {"error": str(exc)}

        execution_results["executed_at"] = datetime.now(UTC).isoformat()
        execution_results["sla_escalations_processed"] = execution_results.get("sla_escalation", [])
        execution_results["keep_offers_expired"] = execution_results.get("keep_offer_expiry", [])
        execution_results["cusum_drift_downgrades"] = execution_results.get("cusum_drift", [])
        return execution_results

    def _run_loop(self) -> None:
        if self.run_on_start and not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:
                logger.error("[AUTOMATION-SCHEDULER-ERROR] Initial run failed: %s", exc)

        while not self._stop_event.wait(self.interval_seconds):
            try:
                self.run_once()
            except Exception as exc:
                logger.error("[AUTOMATION-SCHEDULER-ERROR] Background automation pass failed: %s", exc)
