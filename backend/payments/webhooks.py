"""PayPal Webhook Verification, Event Deduplication, Monotonic Status, and Dispute Freeze (NFR-04, FR-75, AUD-12, RV-14)."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from backend.domain.cache import BoundedTTLCache
from backend.payments.ledger import RefundLedger

if TYPE_CHECKING:
    from backend.db.repository import DatabaseRepository


class WebhookProcessor:
    """Processes verified PayPal webhooks idempotently and enforces dispute/reversal freezes with persistent DB deduplication (AUD-12, RV-14)."""

    def __init__(
        self,
        ledger: RefundLedger,
        repository: DatabaseRepository | None = None,
    ) -> None:
        self.ledger = ledger
        self.repository = repository
        self._seen_event_ids: BoundedTTLCache[bool] = BoundedTTLCache(max_size=10000, ttl_seconds=86400 * 30)
        self._lock = threading.Lock()

    def process_webhook(
        self,
        *,
        event_id: str,
        event_type: str,
        signature_valid: bool,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify signature, deduplicate by event_id across memory and DB, and apply state updates atomically (AUD-12, RV-14)."""
        if not signature_valid:
            return {
                "status_code": 400,
                "code": "WEBHOOK_SIGNATURE_INVALID",
                "duplicate": False,
            }

        with self._lock:
            # 1. Check persistent DB deduplication first (RV-14), then memory cache
            is_dup = False
            if self.repository is not None:
                db_event = self.repository.get_webhook_event(event_id)
                if db_event is not None:
                    is_dup = True

            if not is_dup and event_id in self._seen_event_ids:
                is_dup = True

            if is_dup:
                return {
                    "status_code": 200,
                    "duplicate": True,
                    "event_id": event_id,
                }

            order_id = str(payload.get("order_id", ""))
            # If order not in in-memory ledger, query DB repository if available
            if order_id and order_id not in self.ledger._orders and self.repository is not None:
                db_order = self.repository.get_order(order_id)
                if db_order is not None and db_order.capture_id:
                    self.ledger.register_order(
                        order_id=db_order.order_id,
                        merchant_id=db_order.merchant_id,
                        capture_id=db_order.capture_id,
                        capture_amount_minor=db_order.capture_amount_minor,
                        currency=db_order.currency,
                    )

            if order_id and order_id not in self.ledger._orders:
                # AUD-12: Order unknown. Do not record event_id so future retry can be processed
                return {
                    "status_code": 404,
                    "code": "ORDER_NOT_FOUND",
                    "duplicate": False,
                    "event_id": event_id,
                }

            # Apply state mutation before marking as seen
            if event_type == "CUSTOMER.DISPUTE.CREATED" and order_id:
                self.ledger.freeze_order(order_id)
            elif event_type == "PAYMENT.CAPTURE.REVERSED" and order_id:
                self.ledger.reverse_order_capture(order_id)

            # Persist processed webhook event to database repository (RV-14)
            if self.repository is not None:
                from backend.db.models import WebhookEvent

                self.repository.save_webhook_event(
                    WebhookEvent(
                        event_id=event_id,
                        event_type=event_type,
                        payload_json=payload,
                    )
                )

            self._seen_event_ids.add(event_id)

            return {
                "status_code": 200,
                "duplicate": False,
                "event_id": event_id,
                "event_type": event_type,
            }
