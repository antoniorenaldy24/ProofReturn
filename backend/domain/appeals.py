"""Buyer Appeal & Second-Reviewer Portal (F-15: FR-69, FR-70)."""

from __future__ import annotations

from dataclasses import dataclass


class SameReviewerAppealError(ValueError):
    """Raised when an appeal is assigned to or resolved by the original reviewer (FR-69)."""


@dataclass
class AppealRecord:
    """Appeal record tracking original vs second reviewer and compensating top-up refund."""

    appeal_id: str
    return_id: str
    order_id: str
    original_reviewer_id: str
    buyer_reason: str
    status: str = "OPEN"
    appeal_reviewer_id: str | None = None
    topup_amount_minor: int = 0
    topup_tranche_planned: bool = False


class AppealPortal:
    """Enforces 7-day appeal window, different reviewer rule (FR-69), and compensating TOPUP tranche."""

    def __init__(self) -> None:
        self._appeals: dict[str, AppealRecord] = {}
        self._counter = 0

    def file_appeal(
        self,
        *,
        return_id: str,
        order_id: str,
        original_reviewer_id: str,
        within_window: bool,
        buyer_reason: str,
    ) -> AppealRecord:
        if not within_window:
            raise ValueError("Appeal window (7 days from settlement/rejection) has expired.")
        self._counter += 1
        appeal_id = f"app_{self._counter:03d}"
        rec = AppealRecord(
            appeal_id=appeal_id,
            return_id=return_id,
            order_id=order_id,
            original_reviewer_id=original_reviewer_id,
            buyer_reason=buyer_reason,
        )
        self._appeals[appeal_id] = rec
        return rec

    def resolve_appeal(
        self,
        *,
        appeal_id: str,
        appeal_reviewer_id: str,
        overturn: bool,
        topup_amount_minor: int = 0,
    ) -> AppealRecord:
        rec = self._appeals[appeal_id]
        if appeal_reviewer_id == rec.original_reviewer_id:
            raise SameReviewerAppealError(
                f"FR-69 violation: appeal reviewer '{appeal_reviewer_id}' cannot be the original reviewer."
            )
        rec.appeal_reviewer_id = appeal_reviewer_id
        if overturn:
            rec.status = "OVERTURNED"
            rec.topup_amount_minor = topup_amount_minor
            rec.topup_tranche_planned = topup_amount_minor > 0
        else:
            rec.status = "UPHELD"
        return rec
