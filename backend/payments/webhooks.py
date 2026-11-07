"""PayPal Webhook Verification, Event Deduplication, Monotonic Status, and Dispute Freeze (NFR-04, FR-75, AUD-12, RV-14, RV3-11)."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

from backend.payments.ledger import RefundLedger

if TYPE_CHECKING:
    from backend.db.repository import DatabaseRepository


class WebhookProcessor:
    """Processes verified PayPal webhooks idempotently and enforces dispute/reversal freezes on the DB Order table in a single transaction (AUD-12, RV-14, RV3-11, FR-75)."""

    def __init__(
        self,
        ledger: RefundLedger | None = None,
        repository: DatabaseRepository | None = None,
    ) -> None:
        self.ledger = ledger
        self.repository = repository
        if self.ledger is not None and self.repository is not None:
            self.ledger._repository = self.repository
            for ord_rec in list(self.ledger._orders.values()):
                if self.repository.get_order(ord_rec.order_id) is None:
                    self.repository.ensure_order_registered(
                        order_id=ord_rec.order_id,
                        merchant_id=ord_rec.merchant_id,
                        capture_id=ord_rec.capture_id,
                        capture_amount_minor=ord_rec.capture_amount_minor,
                        currency=ord_rec.currency,
                    )
        self._lock = threading.Lock()

    def process_webhook(
        self,
        *,
        event_id: str,
        event_type: str,
        signature_valid: bool,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify signature, deduplicate by event_id in DB, and apply Order freeze/reversal in the same DB transaction (AUD-12, RV-14, RV3-11, FR-75)."""
        if not signature_valid:
            return {
                "status_code": 400,
                "code": "WEBHOOK_SIGNATURE_INVALID",
                "duplicate": False,
            }

        repo = self.repository or (self.ledger.repository if self.ledger is not None else None)
        if repo is None:
            raise RuntimeError("WebhookProcessor requires a DatabaseRepository.")

        with self._lock:
            return repo.process_webhook_event_transactional(
                event_id=event_id,
                event_type=event_type,
                payload=payload,
            )
