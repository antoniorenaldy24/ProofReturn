"""Transactional refund outbox executor for reliable PayPal Sandbox dispatch (AUD-02 CRITICAL, ARC-19, RV3-01, RV3-02, RV3-12)."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Any

import httpx

from backend.db.models import RefundAction
from backend.db.repository import DatabaseRepository

logger = logging.getLogger("proofreturn.payments.outbox")

MAX_OUTBOX_ATTEMPTS = 8


def compute_outbox_backoff_minutes(attempt_count: int) -> int:
    """Compute exponential backoff in minutes (1, 2, 4, 8, 16, 32, capped at 60; RV3-12)."""
    exponent = max(0, int(attempt_count) - 1)
    return min(60, 2**exponent)


class RefundOutboxExecutor:
    """Executes planned refund actions and reconciles in-flight refunds via PayPal Sandbox API using the transactional outbox pattern."""

    def __init__(
        self,
        repository: DatabaseRepository,
        client: Any,
        metrics: Any | None = None,
        max_attempts: int = MAX_OUTBOX_ATTEMPTS,
    ) -> None:
        self.repository = repository
        self.client = client
        self.metrics = metrics
        self.max_attempts = max_attempts

    def _reconcile_exhausted_action(self, action: RefundAction, effective_refund_id: str) -> str | None:
        """Perform final GET lookup on the refund (if id exists) or capture's refunds when max attempts are reached (RV3-12)."""
        try:
            if effective_refund_id:
                get_refund_fn = getattr(self.client, "get_refund_live", None) or getattr(self.client, "get_refund", None)
                if get_refund_fn is not None:
                    resp = get_refund_fn(refund_id=effective_refund_id)
                    if isinstance(resp, dict):
                        r_id = str(resp.get("id") or effective_refund_id).strip()
                        r_status = str(resp.get("status") or "").strip().upper()
                        r_dbg = str(resp.get("paypal_debug_id") or "").strip()
                        if r_id and r_status == "COMPLETED":
                            self.repository.record_refund_confirmed(
                                request_id=action.request_id,
                                paypal_refund_id=r_id,
                                paypal_debug_id=r_dbg,
                                status_detail="COMPLETED",
                            )
                            return "CONFIRMED"
                        if r_id and r_status in {"FAILED", "CANCELLED"}:
                            self.repository.record_refund_failed_permanent(
                                request_id=action.request_id,
                                paypal_debug_id=r_dbg or r_status,
                                paypal_refund_id=r_id,
                                status_detail=r_status,
                            )
                            return "FAILED_PERMANENT"
            else:
                get_cap_refunds_fn = getattr(self.client, "get_capture_refunds_live", None)
                get_cap_fn = getattr(self.client, "get_capture_live", None)
                refund_items: list[dict[str, Any]] = []
                if get_cap_refunds_fn is not None:
                    res_list = get_cap_refunds_fn(capture_id=action.capture_id)
                    if isinstance(res_list, list):
                        refund_items = [r for r in res_list if isinstance(r, dict)]
                elif get_cap_fn is not None:
                    cap_res = get_cap_fn(capture_id=action.capture_id)
                    if isinstance(cap_res, dict) and isinstance(cap_res.get("refunds"), list):
                        refund_items = [r for r in cap_res["refunds"] if isinstance(r, dict)]

                for item in refund_items:
                    item_req_id = str(item.get("request_id") or item.get("custom_id") or "").strip()
                    if item_req_id and item_req_id != action.request_id:
                        continue
                    r_id = str(item.get("id") or "").strip()
                    r_status = str(item.get("status") or "").strip().upper()
                    r_dbg = str(item.get("paypal_debug_id") or "").strip()
                    if r_id and r_status == "COMPLETED":
                        self.repository.record_refund_confirmed(
                            request_id=action.request_id,
                            paypal_refund_id=r_id,
                            paypal_debug_id=r_dbg,
                            status_detail="COMPLETED",
                        )
                        return "CONFIRMED"
                    if r_id and r_status in {"FAILED", "CANCELLED"}:
                        self.repository.record_refund_failed_permanent(
                            request_id=action.request_id,
                            paypal_debug_id=r_dbg or r_status,
                            paypal_refund_id=r_id,
                            status_detail=r_status,
                        )
                        return "FAILED_PERMANENT"
        except Exception as exc:
            logger.warning(
                "Final GET reconciliation failed for exhausted refund action %s: %s",
                action.request_id,
                exc,
            )
        return None

    def _handle_unknown_or_escalate(
        self,
        action: RefundAction,
        *,
        now: datetime,
        paypal_debug_id: str | None = None,
        paypal_refund_id: str | None = None,
        status_detail: str | None = None,
    ) -> str:
        """Schedule exponential backoff on UNKNOWN or escalate to NEEDS_ATTENTION after max_attempts (RV3-12)."""
        effective_refund_id = (paypal_refund_id or action.paypal_refund_id or "").strip()
        if action.attempt_count >= self.max_attempts:
            resolved = self._reconcile_exhausted_action(action, effective_refund_id)
            if resolved is not None:
                return resolved

            self.repository.record_refund_needs_attention(
                request_id=action.request_id,
                status_detail=status_detail or "MAX_ATTEMPTS_EXCEEDED",
                paypal_debug_id=paypal_debug_id,
                paypal_refund_id=effective_refund_id or None,
            )
            if self.metrics is not None:
                needs_att = self.repository.list_refund_actions_by_status("NEEDS_ATTENTION")
                self.metrics.set_gauge("outbox_needs_attention_count", float(max(1, len(needs_att))))
            logger.error(
                "OUTBOX_NEEDS_ATTENTION: Refund action %s reached %d failed attempts and remains unresolved; set NEEDS_ATTENTION.",
                action.request_id,
                action.attempt_count,
            )
            return "NEEDS_ATTENTION"

        self.repository.record_refund_unknown(
            request_id=action.request_id,
            paypal_debug_id=paypal_debug_id,
            paypal_refund_id=effective_refund_id or None,
            status_detail=status_detail,
            now=now,
        )
        return "UNKNOWN"

    def _apply_refund_response(self, action: RefundAction, resp: Any, *, now: datetime) -> str:
        """Apply PayPal refund response status mapping (RV3-01, RV3-02, RV3-12).
        - Missing 'id' -> UNKNOWN and log REFUND_ID_MISSING (or NEEDS_ATTENTION if max attempts reached)
        - COMPLETED -> CONFIRMED (move pending to confirmed)
        - PENDING -> SUBMITTED with status_detail stored (stays pending)
        - FAILED or CANCELLED -> FAILED_PERMANENT (release pending)
        - Any other or missing status -> UNKNOWN (keep pending, retry later with backoff)
        """
        if not isinstance(resp, dict):
            logger.warning(
                "REFUND_ID_MISSING: Non-dict PayPal refund response for %s; marking UNKNOWN.",
                action.request_id,
            )
            return self._handle_unknown_or_escalate(
                action,
                now=now,
                paypal_debug_id="REFUND_ID_MISSING",
                status_detail="REFUND_ID_MISSING",
            )

        paypal_refund_id = str(resp.get("id") or "").strip()
        paypal_debug_id = str(resp.get("paypal_debug_id") or "").strip()

        if not paypal_refund_id:
            logger.warning(
                "REFUND_ID_MISSING: PayPal refund response for %s missing 'id' (debug_id=%s); marking UNKNOWN.",
                action.request_id,
                paypal_debug_id,
            )
            return self._handle_unknown_or_escalate(
                action,
                now=now,
                paypal_debug_id=paypal_debug_id or "REFUND_ID_MISSING",
                status_detail="REFUND_ID_MISSING",
            )

        raw_status = str(resp.get("status") or "").strip().upper()
        raw_detail = resp.get("status_detail") or resp.get("status_details")
        if isinstance(raw_detail, dict):
            status_detail = str(raw_detail.get("reason") or raw_detail)
        elif raw_detail is not None:
            status_detail = str(raw_detail)
        else:
            status_detail = raw_status or None

        if raw_status == "COMPLETED":
            self.repository.record_refund_confirmed(
                request_id=action.request_id,
                paypal_refund_id=paypal_refund_id,
                paypal_debug_id=paypal_debug_id,
                status_detail=status_detail or "COMPLETED",
            )
            return "CONFIRMED"

        if raw_status == "PENDING":
            self.repository.record_refund_submitted_pending(
                request_id=action.request_id,
                paypal_refund_id=paypal_refund_id,
                status_detail=status_detail or "PENDING",
                paypal_debug_id=paypal_debug_id,
            )
            return "SUBMITTED"

        if raw_status in {"FAILED", "CANCELLED"}:
            self.repository.record_refund_failed_permanent(
                request_id=action.request_id,
                paypal_debug_id=paypal_debug_id or raw_status,
                paypal_refund_id=paypal_refund_id,
                status_detail=status_detail or raw_status,
            )
            return "FAILED_PERMANENT"

        logger.warning(
            "PayPal refund %s returned unexpected/missing status '%s' (id=%s); marking UNKNOWN.",
            action.request_id,
            raw_status,
            paypal_refund_id,
        )
        return self._handle_unknown_or_escalate(
            action,
            now=now,
            paypal_debug_id=paypal_debug_id or raw_status or "STATUS_UNKNOWN",
            paypal_refund_id=paypal_refund_id,
            status_detail=status_detail,
        )

    def run_once(
        self,
        limit: int = 10,
        merchant_id: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Reconcile SUBMITTED actions with paypal_refund_id via GET /v2/payments/refunds/{id},
        then claim and execute up to limit PLANNED or eligible UNKNOWN refund actions (AUD-02, ARC-19, RV3-01, RV3-12).
        """
        effective_now = now or datetime.now(UTC)
        if effective_now.tzinfo is None:
            effective_now = effective_now.replace(tzinfo=UTC)
        else:
            effective_now = effective_now.astimezone(UTC)

        has_credentials = getattr(self.client, "has_credentials", True)
        if not has_credentials:
            logger.warning("PAYPAL_NOT_CONFIGURED: PayPal credentials not configured; skipping outbox run.")
            return {
                "processed": 0,
                "confirmed": 0,
                "unknown": 0,
                "failed_permanent": 0,
                "needs_attention": 0,
                "status": "PAYPAL_NOT_CONFIGURED",
            }

        exhausted_actions = self.repository.list_exhausted_unknown_refund_actions(
            max_attempts=self.max_attempts,
            merchant_id=merchant_id,
        )
        submitted_actions = self.repository.list_submitted_refund_actions_with_paypal_id(
            limit=limit, merchant_id=merchant_id
        )
        actions = self.repository.claim_planned_refund_actions(
            limit=limit,
            merchant_id=merchant_id,
            now=effective_now,
            max_attempts=self.max_attempts,
        )
        if not actions and not submitted_actions and not exhausted_actions:
            return {
                "processed": 0,
                "confirmed": 0,
                "unknown": 0,
                "failed_permanent": 0,
                "needs_attention": 0,
            }

        confirmed_count = 0
        unknown_count = 0
        failed_count = 0
        needs_attention_count = 0

        # 0. Escalate any pre-existing UNKNOWN actions that already reached max_attempts
        for ex_act in exhausted_actions:
            mapped_ex = self._handle_unknown_or_escalate(ex_act, now=effective_now)
            if mapped_ex == "CONFIRMED":
                confirmed_count += 1
            elif mapped_ex == "FAILED_PERMANENT":
                failed_count += 1
            elif mapped_ex == "NEEDS_ATTENTION":
                needs_attention_count += 1

        # 1. Reconciliation step: poll GET /v2/payments/refunds/{id} for SUBMITTED actions with paypal_refund_id
        get_refund_fn = getattr(self.client, "get_refund_live", None) or getattr(self.client, "get_refund", None)
        if get_refund_fn is not None:
            for sub_act in submitted_actions:
                if not sub_act.paypal_refund_id:
                    continue
                try:
                    resp = get_refund_fn(refund_id=sub_act.paypal_refund_id)
                    mapped = self._apply_refund_response(sub_act, resp, now=effective_now)
                    if mapped == "CONFIRMED":
                        confirmed_count += 1
                    elif mapped == "FAILED_PERMANENT":
                        failed_count += 1
                    elif mapped == "UNKNOWN":
                        unknown_count += 1
                    elif mapped == "NEEDS_ATTENTION":
                        needs_attention_count += 1
                except Exception as exc:
                    logger.warning("Failed to reconcile SUBMITTED refund %s: %s", sub_act.request_id, exc)

        # 2. Dispatch step: POST /v2/payments/captures/{id}/refund for newly claimed PLANNED/UNKNOWN actions
        for action in actions:
            try:
                resp = self.client.refund_capture_live(
                    capture_id=action.capture_id,
                    request_id=action.request_id,
                    amount_minor=action.amount_minor,
                    currency=action.currency,
                )
                mapped = self._apply_refund_response(action, resp, now=effective_now)
                if mapped == "CONFIRMED":
                    confirmed_count += 1
                elif mapped == "FAILED_PERMANENT":
                    failed_count += 1
                elif mapped == "UNKNOWN":
                    unknown_count += 1
                elif mapped == "NEEDS_ATTENTION":
                    needs_attention_count += 1
            except httpx.HTTPStatusError as exc:
                debug_id = exc.response.headers.get("paypal-debug-id", "")
                if 400 <= exc.response.status_code < 500:
                    try:
                        err_data = exc.response.json()
                        err_name = err_data.get("name") or err_data.get("message") or str(exc)
                    except Exception:
                        err_name = str(exc)
                    logger.warning(
                        "PayPal 4xx client error for refund %s (%s, debug_id=%s): %s",
                        action.request_id,
                        err_name,
                        debug_id,
                        exc,
                    )
                    self.repository.record_refund_failed_permanent(
                        request_id=action.request_id,
                        paypal_debug_id=debug_id or err_name,
                    )
                    failed_count += 1
                else:
                    logger.warning(
                        "PayPal 5xx server error for refund %s (debug_id=%s): %s",
                        action.request_id,
                        debug_id,
                        exc,
                    )
                    mapped = self._handle_unknown_or_escalate(
                        action,
                        now=effective_now,
                        paypal_debug_id=debug_id,
                        status_detail="HTTP_5XX",
                    )
                    if mapped == "CONFIRMED":
                        confirmed_count += 1
                    elif mapped == "FAILED_PERMANENT":
                        failed_count += 1
                    elif mapped == "NEEDS_ATTENTION":
                        needs_attention_count += 1
                    else:
                        unknown_count += 1
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RequestError) as exc:
                logger.warning("PayPal network timeout/error for refund %s: %s", action.request_id, exc)
                mapped = self._handle_unknown_or_escalate(
                    action,
                    now=effective_now,
                    paypal_debug_id=None,
                    status_detail="NETWORK_TIMEOUT",
                )
                if mapped == "CONFIRMED":
                    confirmed_count += 1
                elif mapped == "FAILED_PERMANENT":
                    failed_count += 1
                elif mapped == "NEEDS_ATTENTION":
                    needs_attention_count += 1
                else:
                    unknown_count += 1
            except RuntimeError as exc:
                if "PAYPAL_NOT_CONFIGURED" in str(exc) or "credentials" in str(exc).lower():
                    logger.warning("PAYPAL_NOT_CONFIGURED raised during refund %s: %s", action.request_id, exc)
                    with self.repository._lock, self.repository.get_session() as s:
                        act = s.get(RefundAction, action.request_id)
                        if act:
                            act.status = "PLANNED"
                            s.add(act)
                            s.commit()
                    return {
                        "processed": 0,
                        "confirmed": 0,
                        "unknown": 0,
                        "failed_permanent": 0,
                        "needs_attention": 0,
                        "status": "PAYPAL_NOT_CONFIGURED",
                    }
                logger.exception("Unexpected runtime error for refund %s: %s", action.request_id, exc)
                mapped = self._handle_unknown_or_escalate(
                    action,
                    now=effective_now,
                    paypal_debug_id=None,
                    status_detail="RUNTIME_ERROR",
                )
                if mapped == "NEEDS_ATTENTION":
                    needs_attention_count += 1
                elif mapped == "CONFIRMED":
                    confirmed_count += 1
                elif mapped == "FAILED_PERMANENT":
                    failed_count += 1
                else:
                    unknown_count += 1
            except Exception as exc:
                logger.exception("Unexpected error executing refund %s: %s", action.request_id, exc)
                mapped = self._handle_unknown_or_escalate(
                    action,
                    now=effective_now,
                    paypal_debug_id=None,
                    status_detail="UNEXPECTED_ERROR",
                )
                if mapped == "NEEDS_ATTENTION":
                    needs_attention_count += 1
                elif mapped == "CONFIRMED":
                    confirmed_count += 1
                elif mapped == "FAILED_PERMANENT":
                    failed_count += 1
                else:
                    unknown_count += 1

        return {
            "processed": len(actions) + len(submitted_actions) + len(exhausted_actions),
            "confirmed": confirmed_count,
            "unknown": unknown_count,
            "failed_permanent": failed_count,
            "needs_attention": needs_attention_count,
        }
