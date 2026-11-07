"""Posted-Price Keep-Offer calculator and eligibility guardrails (Section 8.12, F-08, F-10, FR-37, FR-46, FR-78)."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from backend.domain.policy import PolicyConfig


@dataclass(frozen=True)
class KeepOfferInput:
    refund_owed_minor: int
    reverse_shipping_minor: int
    handling_cost_minor: int
    recovery_lower_bound_minor: int
    tier: str
    intake_passed: bool
    is_safety_sensitive: bool = False
    group_keep_offers_last_90d: int = 0
    already_offered_on_return: bool = False


@dataclass(frozen=True)
class KeepOfferDecision:
    eligible: bool
    posted_price_minor: int | None
    _k_max_internal_minor: int
    reason_code: str
    explanation: str

    def to_public_dict(self) -> dict[str, Any]:
        """FR-46 & FR-78 & MV-18: Expose only the posted price and accept/decline actions; never expose k_max bounds."""
        return {
            "eligible": self.eligible,
            "posted_price": (
                {"amount_minor": self.posted_price_minor, "currency": "USD"}
                if self.posted_price_minor is not None
                else None
            ),
            "allowed_actions": ["accept", "decline"] if self.eligible else [],
            "explanation": self.explanation,
        }


def compute_posted_keep_offer(inp: KeepOfferInput, policy: PolicyConfig) -> KeepOfferDecision:
    """FR-37 & FR-78: k_max = R + S + C_h - V_lower; posted price k <= (1 - theta_h)*k_max."""
    # ASSUMPTION(A-23): Keep-offer harvest share theta_h approx 0.30
    if inp.already_offered_on_return:
        return KeepOfferDecision(False, None, 0, "ALREADY_OFFERED", "A keep-offer was already presented for this return.")
    if inp.is_safety_sensitive:
        return KeepOfferDecision(False, None, 0, "SAFETY_EXCLUDED", "Safety-sensitive items must be returned.")
    if not inp.intake_passed:
        return KeepOfferDecision(False, None, 0, "INTAKE_NOT_PASSED", "Keep-offers require verified intake evidence.")
    if inp.tier not in {"ESTABLISHED", "TRUSTED"}:
        return KeepOfferDecision(False, None, 0, "TIER_NOT_ELIGIBLE", "Keep-offers are available for established and trusted accounts.")
    if inp.group_keep_offers_last_90d >= 1:
        return KeepOfferDecision(False, None, 0, "FREQUENCY_CAP_90D", "Keep-offer limit (1 per 90 days) reached.")

    k_max_minor = (
        inp.refund_owed_minor
        + inp.reverse_shipping_minor
        + inp.handling_cost_minor
        - inp.recovery_lower_bound_minor
    )
    if k_max_minor <= 0:
        return KeepOfferDecision(False, None, k_max_minor, "NON_POSITIVE_BOUND", "Return shipping is more economical than a keep-offer for this item.")

    theta_h = policy.theta_h_fraction()
    posted_minor = int( (Fraction(1, 1) - theta_h) * Fraction(k_max_minor) )
    posted_minor = min(posted_minor, inp.refund_owed_minor)
    if posted_minor <= 0:
        return KeepOfferDecision(False, None, k_max_minor, "NON_POSITIVE_POSTED", "No keep-offer available.")

    return KeepOfferDecision(
        eligible=True,
        posted_price_minor=posted_minor,
        _k_max_internal_minor=k_max_minor,
        reason_code="KEEP_OFFER_AVAILABLE",
        explanation=f"Keep the item and receive an instant partial refund of ${posted_minor / 100:.2f} with no shipping required.",
    )
