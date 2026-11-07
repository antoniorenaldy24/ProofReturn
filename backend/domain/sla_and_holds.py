"""High-Value Deposit Hold Guard (F-13: FR-54, FR-55) and Inspection SLA Credit (F-14: FR-56)."""

from __future__ import annotations

from typing import Any


def validate_rental_duration_days(*, days: int, st03_reauth_verified: bool = False) -> bool:
    """Enforce FR-55: Rentals are capped at <= 3 days until ST-03 reauthorization is verified in Sandbox."""
    if days <= 0:
        raise ValueError("Rental duration must be positive.")
    if not st03_reauth_verified and days > 3:
        raise ValueError(
            "FR-55 violation: Rental duration exceeds 3-day authorization honor period before ST-03 verification."
        )
    return True


def compute_sla_breach_credit(
    *,
    elapsed_hours: int,
    sla_hours: int,
    disputed_amount_minor: int,
    credit_rate_bps: int = 1000,
) -> dict[str, Any]:
    """Compute automatic SLA credit when merchant inspection exceeds `sla_hours` (FR-56)."""
    if elapsed_hours <= sla_hours:
        return {"breached": False, "credit_minor": 0}
    credit_minor = (disputed_amount_minor * credit_rate_bps) // 10_000
    return {
        "breached": True,
        "elapsed_hours": elapsed_hours,
        "sla_hours": sla_hours,
        "credit_minor": credit_minor,
    }
