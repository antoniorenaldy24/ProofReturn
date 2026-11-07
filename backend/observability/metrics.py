"""Observability Metrics, Structured Logs, Alerts (AL-01..AL-07), and Runbooks (RB-01..RB-06).

Implements Section 34 of ProofReturn SSOT v1.2.1 (NFR-08).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import threading
from typing import Any, Callable


@dataclass(frozen=True)
class FiredAlert:
    alert_id: str
    severity: str
    condition: str
    runbook_id: str


@dataclass(frozen=True)
class Runbook:
    runbook_id: str
    title: str
    steps: list[str]


_RUNBOOKS: dict[str, Runbook] = {
    "RB-01": Runbook(
        runbook_id="RB-01",
        title="Reconciliation Mismatch Detected (AL-01)",
        steps=[
            "1. Pause automatic money actions on affected merchant tenant.",
            "2. Inspect reconciliation_runs table and compare payment_actions against PayPal transaction report.",
            "3. Resolve UNKNOWN actions via GET /v2/payments/captures/{id} or /refunds/{id} using stored PayPal-Request-Id.",
            "4. Record incident note and re-run REC-02 before re-enabling automatic payouts.",
        ],
    ),
    "RB-02": Runbook(
        runbook_id="RB-02",
        title="Stuck UNKNOWN Payment Action > 15 min (AL-02)",
        steps=[
            "1. Query payment_actions where status = 'UNKNOWN' and updated_at < now() - interval '15 minutes'.",
            "2. Execute REC-01 status lookup by paypal_id or replay idempotent request with identical PayPal-Request-Id.",
            "3. Transition to CONFIRMED or FAILED based on authoritative PayPal response.",
        ],
    ),
    "RB-03": Runbook(
        runbook_id="RB-03",
        title="Webhook Verification Failure Spike (AL-03)",
        steps=[
            "1. Verify PAYPAL_WEBHOOK_ID in environment configuration matches PayPal Developer Dashboard.",
            "2. Check PayPal verify-webhook-signature endpoint availability and cert URL domain allow-list.",
            "3. Trigger REC-01 polling fallback so confirmed refunds are not delayed by webhook drops.",
        ],
    ),
    "RB-04": Runbook(
        runbook_id="RB-04",
        title="Grading Model Error Rate > 5% over 10 min (AL-04)",
        steps=[
            "1. Check primary grader API health and quota metrics (ai_stage_latency_seconds, model error codes).",
            "2. Verify automatic fallback FB-01 (single grader + raised uncertainty) or FB-02 (human review routing) is active.",
            "3. Ensure zero automatic accusations occur during degraded AI mode (INV-10).",
        ],
    ),
    "RB-05": Runbook(
        runbook_id="RB-05",
        title="Review Queue Backlog > 50 or Oldest > 24h (AL-05)",
        steps=[
            "1. Notify merchant reviewer operations channel and sort queue by SLA deadline ascending.",
            "2. Prioritize ESCALATED cases approaching 48h SLA to prevent automatic undisputed release (#34).",
            "3. Audit recent intake routing thresholds for unexpected spike in escalations.",
        ],
    ),
    "RB-06": Runbook(
        runbook_id="RB-06",
        title="Audit Rate Outside Expected Band or ESCALATED Near Deadline (AL-06 / AL-07)",
        steps=[
            "1. Verify commit-reveal audit seed generation (FR-61, FR-95) and policy p_audit floor configuration.",
            "2. For AL-07 (ESCALATED within 24h of deadline), alert merchant admin immediately.",
            "3. Confirm timer #34 is scheduled to release undisputed amount if deadline expires without human review.",
        ],
    ),
}


def format_structured_log(
    *,
    level: str,
    service: str,
    message: str,
    request_id: str,
    trace_id: str,
    merchant_id: str | None = None,
    return_id: str | None = None,
    decision_id: str | None = None,
    payment_action_id: str | None = None,
    paypal_debug_id: str | None = None,
    model_id: str | None = None,
    prompt_id: str | None = None,
) -> dict[str, Any]:
    """Emit structured JSON log entry with required Section 34.1 fields (no raw PII or secrets)."""
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": level.upper(),
        "service": service,
        "message": message,
        "request_id": request_id,
        "trace_id": trace_id,
        "merchant_id": merchant_id,
        "return_id": return_id,
        "decision_id": decision_id,
        "payment_action_id": payment_action_id,
        "paypal_debug_id": paypal_debug_id,
        "model_id": model_id,
        "prompt_id": prompt_id,
    }


@dataclass
class MetricsRegistry:
    """In-memory OpenTelemetry-compatible metrics store for Section 34.1 signals."""

    counters: dict[str, int] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)
    histograms: dict[str, list[float]] = field(default_factory=dict)

    def inc_counter(self, name: str, value: int = 1, labels: dict[str, str] | None = None) -> None:
        key = self._format_key(name, labels)
        self.counters[key] = self.counters.get(key, 0) + value

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        key = self._format_key(name, labels)
        self.gauges[key] = float(value)

    def get_gauge(self, name: str, default: float = 0.0) -> float:
        return self.gauges.get(name, default)

    def observe_histogram(
        self, name: str, value: float, labels: dict[str, str] | None = None
    ) -> None:
        key = self._format_key(name, labels)
        self.histograms.setdefault(key, []).append(float(value))

    @staticmethod
    def _format_key(name: str, labels: dict[str, str] | None) -> str:
        if not labels:
            return name
        sorted_pairs = ",".join(f"{k}=\"{v}\"" for k, v in sorted(labels.items()))
        return f"{name}{{{sorted_pairs}}}"

    def to_prometheus_text(self) -> str:
        """Export metrics in Prometheus text format (NFR-08, AUD-37)."""
        lines: list[str] = []
        for k, v in sorted(self.counters.items()):
            base = k.split("{")[0]
            lines.append(f"# TYPE {base} counter")
            lines.append(f"{k} {v}")
        for k, v in sorted(self.gauges.items()):
            base = k.split("{")[0]
            lines.append(f"# TYPE {base} gauge")
            lines.append(f"{k} {v}")
        for k, vals in sorted(self.histograms.items()):
            base = k.split("{")[0]
            lines.append(f"# TYPE {base} summary")
            lines.append(f"{base}_count {len(vals)}")
            lines.append(f"{base}_sum {sum(vals):.4f}")
        return "\n".join(lines) + ("\n" if lines else "")


def evaluate_alerts(metrics: MetricsRegistry) -> list[FiredAlert]:
    """Evaluate Section 34.2 alert conditions AL-01..AL-07 against current metrics."""
    fired: list[FiredAlert] = []

    if metrics.get_gauge("reconciliation_mismatches") > 0:
        fired.append(
            FiredAlert(
                alert_id="AL-01",
                severity="CRITICAL",
                condition="reconciliation_mismatches > 0",
                runbook_id="RB-01",
            )
        )
    if metrics.get_gauge("unknown_payment_action_max_age_minutes") > 15:
        fired.append(
            FiredAlert(
                alert_id="AL-02",
                severity="HIGH",
                condition="UNKNOWN payment action > 15 min",
                runbook_id="RB-02",
            )
        )
    if metrics.get_gauge("webhook_verify_failures_5m") >= 10:
        fired.append(
            FiredAlert(
                alert_id="AL-03",
                severity="HIGH",
                condition="Webhook verify failure spike",
                runbook_id="RB-03",
            )
        )
    if metrics.get_gauge("grading_model_error_rate_10m") > 0.05:
        fired.append(
            FiredAlert(
                alert_id="AL-04",
                severity="HIGH",
                condition="Grading model error rate > 5% over 10 min",
                runbook_id="RB-04",
            )
        )
    if (
        metrics.get_gauge("review_queue_backlog") > 50
        or metrics.get_gauge("review_queue_oldest_hours") > 24
    ):
        fired.append(
            FiredAlert(
                alert_id="AL-05",
                severity="MEDIUM",
                condition="Queue backlog > 50 or oldest > 24 h",
                runbook_id="RB-05",
            )
        )
    if metrics.get_gauge("audit_rate_deviation_sigma") > 3.0:
        fired.append(
            FiredAlert(
                alert_id="AL-06",
                severity="MEDIUM",
                condition="Audit rate outside expected band (±3 SD)",
                runbook_id="RB-06",
            )
        )
    if metrics.get_gauge("escalated_within_24h_of_deadline") > 0:
        fired.append(
            FiredAlert(
                alert_id="AL-07",
                severity="HIGH",
                condition="ESCALATED case within 24 h of deadline",
                runbook_id="RB-06",
            )
        )
    return fired


def get_runbook(runbook_id: str) -> Runbook:
    """Retrieve operational runbook RB-01..RB-06 by ID."""
    if runbook_id not in _RUNBOOKS:
        raise KeyError(f"Unknown runbook ID: {runbook_id}")
    return _RUNBOOKS[runbook_id]


class AlertScheduler:
    """Background operational alert evaluation scheduler (AUD-37, Section 34.2)."""

    def __init__(
        self,
        metrics: MetricsRegistry,
        interval_seconds: float = 60.0,
        on_alert_fired: Callable[[list[FiredAlert]], None] | None = None,
    ) -> None:
        self.metrics = metrics
        self.interval_seconds = interval_seconds
        self.on_alert_fired = on_alert_fired
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_evaluated: list[FiredAlert] = []

    @property
    def is_running(self) -> bool:
        """True if the background alert scheduler thread is active."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start background scheduler loop."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="AlertScheduler")
        self._thread.start()

    def stop(self) -> None:
        """Signal background scheduler to stop and wait for termination."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def evaluate_now(self) -> list[FiredAlert]:
        """Manually trigger immediate alert evaluation."""
        alerts = evaluate_alerts(self.metrics)
        self._last_evaluated = alerts
        if alerts and self.on_alert_fired:
            self.on_alert_fired(alerts)
        return alerts

    def _run_loop(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            self.evaluate_now()

