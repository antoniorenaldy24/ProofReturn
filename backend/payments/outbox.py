"""Transactional refund outbox executor for reliable PayPal Sandbox dispatch (AUD-02 CRITICAL, ARC-19, RV3-01, RV3-02)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.db.models import RefundAction
from backend.db.repository import DatabaseRepository

logger = logging.getLogger("proofreturn.payments.outbox")


class RefundOutboxExecutor:
    """Executes planned refund actions and reconciles in-flight refunds via PayPal Sandbox API using the transactional outbox pattern."""

    def __init__(self, repository: DatabaseRepository, client: Any) -> None:
        self.repository = repository
        self.client = client

    def _apply_refund_response(self, action: RefundAction, resp: Any) -> str:
        """Apply PayPal refund response status mapping (RV3-01, RV3-02).
        - Missing 'id' -> UNKNOWN and log REFUND_ID_MISSING
        - COMPLETED -> CONFIRMED (move pending to confirmed)
        - PENDING -> SUBMITTED with status_detail stored (stays pending)
        - FAILED or CANCELLED -> FAILED_PERMANENT (release pending)
        - Any other or missing status -> UNKNOWN (keep pending, retry later)
        """
        if not isinstance(resp, dict):
            logger.warning(
                "REFUND_ID_MISSING: Non-dict PayPal refund response for %s; marking UNKNOWN.",
                action.request_id,
            )
            self.repository.record_refund_unknown(
                request_id=action.request_id,
                paypal_debug_id="REFUND_ID_MISSING",
            )
            return "UNKNOWN"

        paypal_refund_id = str(resp.get("id") or "").strip()
        paypal_debug_id = str(resp.get("paypal_debug_id") or "").strip()

        if not paypal_refund_id:
            logger.warning(
                "REFUND_ID_MISSING: PayPal refund response for %s missing 'id' (debug_id=%s); marking UNKNOWN.",
                action.request_id,
                paypal_debug_id,
            )
            self.repository.record_refund_unknown(
                request_id=action.request_id,
                paypal_debug_id=paypal_debug_id or "REFUND_ID_MISSING",
            )
            return "UNKNOWN"

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
        self.repository.record_refund_unknown(
            request_id=action.request_id,
            paypal_debug_id=paypal_debug_id or raw_status or "STATUS_UNKNOWN",
            paypal_refund_id=paypal_refund_id,
            status_detail=status_detail,
        )
        return "UNKNOWN"

    def run_once(self, limit: int = 10, merchant_id: str | None = None) -> dict[str, Any]:
        """Reconcile SUBMITTED actions with paypal_refund_id via GET /v2/payments/refunds/{id},
        then claim and execute up to limit PLANNED or UNKNOWN refund actions (AUD-02, ARC-19, RV3-01).
        """
        has_credentials = getattr(self.client, "has_credentials", True)
        if not has_credentials:
            logger.warning("PAYPAL_NOT_CONFIGURED: PayPal credentials not configured; skipping outbox run.")
            return {
                "processed": 0,
                "confirmed": 0,
                "unknown": 0,
                "failed_permanent": 0,
                "status": "PAYPAL_NOT_CONFIGURED",
            }

        submitted_actions = self.repository.list_submitted_refund_actions_with_paypal_id(
            limit=limit, merchant_id=merchant_id
        )
        actions = self.repository.claim_planned_refund_actions(limit=limit, merchant_id=merchant_id)
        if not actions and not submitted_actions:
            return {
                "processed": 0,
                "confirmed": 0,
                "unknown": 0,
                "failed_permanent": 0,
            }

        confirmed_count = 0
        unknown_count = 0
        failed_count = 0

        # 1. Reconciliation step: poll GET /v2/payments/refunds/{id} for SUBMITTED actions with paypal_refund_id
        get_refund_fn = getattr(self.client, "get_refund_live", None) or getattr(self.client, "get_refund", None)
        if get_refund_fn is not None:
            for sub_act in submitted_actions:
                if not sub_act.paypal_refund_id:
                    continue
                try:
                    resp = get_refund_fn(refund_id=sub_act.paypal_refund_id)
                    mapped = self._apply_refund_response(sub_act, resp)
                    if mapped == "CONFIRMED":
                        confirmed_count += 1
                    elif mapped == "FAILED_PERMANENT":
                        failed_count += 1
                    elif mapped == "UNKNOWN":
                        unknown_count += 1
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
                mapped = self._apply_refund_response(action, resp)
                if mapped == "CONFIRMED":
                    confirmed_count += 1
                elif mapped == "FAILED_PERMANENT":
                    failed_count += 1
                elif mapped == "UNKNOWN":
                    unknown_count += 1
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
                    self.repository.record_refund_unknown(
                        request_id=action.request_id,
                        paypal_debug_id=debug_id,
                    )
                    unknown_count += 1
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RequestError) as exc:
                logger.warning("PayPal network timeout/error for refund %s: %s", action.request_id, exc)
                self.repository.record_refund_unknown(
                    request_id=action.request_id,
                    paypal_debug_id=None,
                )
                unknown_count += 1
            except RuntimeError as exc:
                if "PAYPAL_NOT_CONFIGURED" in str(exc) or "credentials" in str(exc).lower():
                    logger.warning("PAYPAL_NOT_CONFIGURED raised during refund %s: %s", action.request_id, exc)
                    # Client lacked credentials; revert to PLANNED and exit fail-closed
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
                        "status": "PAYPAL_NOT_CONFIGURED",
                    }
                logger.exception("Unexpected runtime error for refund %s: %s", action.request_id, exc)
                self.repository.record_refund_unknown(
                    request_id=action.request_id,
                    paypal_debug_id=None,
                )
                unknown_count += 1
            except Exception as exc:
                logger.exception("Unexpected error executing refund %s: %s", action.request_id, exc)
                self.repository.record_refund_unknown(
                    request_id=action.request_id,
                    paypal_debug_id=None,
                )
                unknown_count += 1

        return {
            "processed": len(actions) + len(submitted_actions),
            "confirmed": confirmed_count,
            "unknown": unknown_count,
            "failed_permanent": failed_count,
        }
