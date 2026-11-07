"""Transactional refund outbox executor for reliable PayPal Sandbox dispatch (AUD-02 CRITICAL, ARC-19)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.db.models import RefundAction
from backend.db.repository import DatabaseRepository

logger = logging.getLogger("proofreturn.payments.outbox")


class RefundOutboxExecutor:
    """Executes planned refund actions via PayPal Sandbox API using the transactional outbox pattern."""

    def __init__(self, repository: DatabaseRepository, client: Any) -> None:
        self.repository = repository
        self.client = client

    def run_once(self, limit: int = 10, merchant_id: str | None = None) -> dict[str, Any]:
        """Claim and execute up to limit PLANNED or UNKNOWN refund actions (AUD-02, ARC-19)."""
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

        actions = self.repository.claim_planned_refund_actions(limit=limit, merchant_id=merchant_id)
        if not actions:
            return {
                "processed": 0,
                "confirmed": 0,
                "unknown": 0,
                "failed_permanent": 0,
            }

        confirmed_count = 0
        unknown_count = 0
        failed_count = 0

        for action in actions:
            try:
                resp = self.client.refund_capture_live(
                    capture_id=action.capture_id,
                    request_id=action.request_id,
                    amount_minor=action.amount_minor,
                    currency=action.currency,
                )
                paypal_refund_id = resp.get("id") or f"PP-REF-{action.request_id[:8]}"
                paypal_debug_id = resp.get("paypal_debug_id") or ""
                self.repository.record_refund_confirmed(
                    request_id=action.request_id,
                    paypal_refund_id=paypal_refund_id,
                    paypal_debug_id=paypal_debug_id,
                )
                confirmed_count += 1
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
            "processed": len(actions),
            "confirmed": confirmed_count,
            "unknown": unknown_count,
            "failed_permanent": failed_count,
        }
