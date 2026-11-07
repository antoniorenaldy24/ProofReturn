"""Transactional Refund Outbox and Cumulative Capture Ledger (INV-01, INV-02, INV-03, Section 24.3)."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass


class OverRefundError(ValueError):
    """Raised when a planned refund would cause cumulative refunds to exceed capture_amount_minor (INV-01)."""


class IdempotencyConflictError(ValueError):
    """Raised when an action is replanned with a different amount or payload (AUD-18)."""


PROOFRETURN_REFUND_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


@dataclass
class OrderCaptureRecord:
    """Tracks original capture and freeze/reversal status for an order."""

    order_id: str
    merchant_id: str
    capture_id: str
    capture_amount_minor: int
    currency: str = "USD"
    frozen_by_dispute: bool = False
    reversed_by_chargeback: bool = False


@dataclass
class RefundActionRecord:
    """Outbox row representing a single refund tranche action (Section 24.3)."""

    request_id: str
    order_id: str
    merchant_id: str
    capture_id: str
    decision_id: str
    tranche: str
    amount_minor: int
    status: str = "PLANNED"
    paypal_refund_id: str | None = None
    paypal_debug_id: str | None = None
    attempt_count: int = 0


def compute_deterministic_request_id(decision_id: str, tranche: str) -> str:
    """Compute UUIDv5(namespace, decision_id + ':' + tranche) per INV-03 / Section 24.3."""
    return str(uuid.uuid5(PROOFRETURN_REFUND_NAMESPACE, f"{decision_id}:{tranche}"))


class RefundLedger:
    """Enforces INV-01 (no over-refund), INV-02 (merchant/capture binding), and INV-03 (idempotent outbox).
    All state mutations and balance queries are synchronized with reentrant lock to eliminate race conditions (AUD-11).
    """

    def __init__(self) -> None:
        self._orders: dict[str, OrderCaptureRecord] = {}
        self._actions_by_request_id: dict[str, RefundActionRecord] = {}
        self._actions_by_order: dict[str, list[RefundActionRecord]] = {}
        self._lock = threading.RLock()

    def register_order(
        self,
        *,
        order_id: str,
        merchant_id: str,
        capture_id: str,
        capture_amount_minor: int,
        currency: str = "USD",
    ) -> OrderCaptureRecord:
        with self._lock:
            rec = OrderCaptureRecord(
                order_id=order_id,
                merchant_id=merchant_id,
                capture_id=capture_id,
                capture_amount_minor=capture_amount_minor,
                currency=currency,
            )
            self._orders[order_id] = rec
            self._actions_by_order.setdefault(order_id, [])
            return rec

    def rehydrate_action(
        self,
        *,
        request_id: str,
        order_id: str,
        merchant_id: str,
        capture_id: str,
        decision_id: str,
        tranche: str,
        amount_minor: int,
        status: str = "PLANNED",
        paypal_refund_id: str | None = None,
        paypal_debug_id: str | None = None,
        attempt_count: int = 1,
    ) -> RefundActionRecord:
        """Rehydrate an existing refund action from database into memory without re-planning."""
        with self._lock:
            rec = RefundActionRecord(
                request_id=request_id,
                order_id=order_id,
                merchant_id=merchant_id,
                capture_id=capture_id,
                decision_id=decision_id,
                tranche=tranche,
                amount_minor=amount_minor,
                status=status,
                paypal_refund_id=paypal_refund_id,
                paypal_debug_id=paypal_debug_id,
                attempt_count=attempt_count,
            )
            self._actions_by_request_id[request_id] = rec
            if order_id in self._actions_by_order:
                self._actions_by_order[order_id].append(rec)
            else:
                self._actions_by_order[order_id] = [rec]
            return rec

    def is_order_frozen(self, order_id: str) -> bool:
        with self._lock:
            rec = self._orders[order_id]
            return rec.frozen_by_dispute or rec.reversed_by_chargeback

    def freeze_order(self, order_id: str) -> None:
        with self._lock:
            if order_id not in self._orders:
                raise KeyError(f"Unknown order {order_id}")
            self._orders[order_id].frozen_by_dispute = True

    def reverse_order_capture(self, order_id: str) -> None:
        with self._lock:
            if order_id not in self._orders:
                raise KeyError(f"Unknown order {order_id}")
            rec = self._orders[order_id]
            rec.reversed_by_chargeback = True
            rec.frozen_by_dispute = True

    def remaining_refundable_minor(self, order_id: str) -> int:
        """Compute remaining_refundable = capture_amount - confirmed - pending (0 if reversed)."""
        with self._lock:
            rec = self._orders[order_id]
            if rec.reversed_by_chargeback:
                return 0
            actions = self._actions_by_order.get(order_id, [])
            committed = sum(
                a.amount_minor
                for a in actions
                if a.status in {"PLANNED", "SUBMITTED", "CONFIRMED", "UNKNOWN", "IN_FLIGHT"}
            )
            return max(0, rec.capture_amount_minor - committed)

    def plan_refund_action(
        self,
        *,
        order_id: str,
        merchant_id: str,
        capture_id: str,
        decision_id: str,
        tranche: str,
        amount_minor: int,
    ) -> RefundActionRecord:
        """Insert or return an idempotent PLANNED refund action after checking INV-01, INV-02, INV-03 under lock."""
        with self._lock:
            if order_id not in self._orders:
                raise ValueError(f"Unknown order_id: {order_id}")
            order_rec = self._orders[order_id]

            # INV-02: Verify merchant_id and capture_id belong to this order
            if order_rec.merchant_id != merchant_id or order_rec.capture_id != capture_id:
                raise ValueError(
                    f"INV-02 violation: (merchant_id={merchant_id}, capture_id={capture_id}) "
                    f"does not match order {order_id}."
                )

            if order_rec.frozen_by_dispute or order_rec.reversed_by_chargeback:
                raise OverRefundError(f"Order {order_id} is frozen by dispute or capture reversal.")

            request_id = compute_deterministic_request_id(decision_id, tranche)
            if request_id in self._actions_by_request_id:
                existing = self._actions_by_request_id[request_id]
                if existing.amount_minor != amount_minor:
                    raise IdempotencyConflictError(
                        f"AUD-18 idempotency conflict: action {request_id} already planned for "
                        f"{existing.amount_minor} minor, cannot re-plan with {amount_minor} minor."
                    )
                return existing

            remaining = self.remaining_refundable_minor(order_id)
            if amount_minor > remaining:
                raise OverRefundError(
                    f"INV-01 violation: requested {amount_minor} exceeds remaining_refundable {remaining}."
                )

            action = RefundActionRecord(
                request_id=request_id,
                order_id=order_id,
                merchant_id=merchant_id,
                capture_id=capture_id,
                decision_id=decision_id,
                tranche=tranche,
                amount_minor=amount_minor,
                status="PLANNED",
            )
            self._actions_by_request_id[request_id] = action
            self._actions_by_order[order_id].append(action)
            return action
