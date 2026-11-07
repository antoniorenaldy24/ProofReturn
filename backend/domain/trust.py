"""Value-weighted, age-gated trust tiers, promotion rules, and exposure caps (Section 8.3 & 8.7, FR-57, FR-70, FR-91, FR-92)."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from backend.domain.constants import (
    COUNTER_VERIFIED_DROPOFF_CAP_MINOR,
    TIER_CAPS_MINOR,
    TIER_RANK,
    TRUST_TIERS,
    TrustTier,
)


@dataclass
class TrustProfile:
    tier: str = "NEW"
    clean_count: int = 0
    cumulative_verified_value_minor: int = 0
    largest_clean_value_minor: int = 0
    kept_order_count: int = 0
    kept_order_value_minor: int = 0
    audited_confirmed_count: int = 0
    gross_misdeclare_count: int = 0
    account_age_days: int = 0
    outstanding_pre_checkin_minor: int = 0
    confirmed_fraud_amount_minor: int = 0
    clean_standard_since_restricted: int = 0
    days_since_restricted: int = 0


def compute_account_exposure_cap_minor(
    tier: str,
    largest_clean_value_minor: int,
    *,
    counter_verified_dropoff: bool = False,
    kappa: Fraction = Fraction(3, 2),
) -> int:
    """FR-92 & INV-14: account cap = min(tier cap, kappa * largest clean verified return value)."""
    if tier == "NEW":
        return COUNTER_VERIFIED_DROPOFF_CAP_MINOR if counter_verified_dropoff else 0
    if tier == "RESTRICTED":
        return 0
    base_cap = TIER_CAPS_MINOR.get(tier, 0)
    if largest_clean_value_minor > 0:
        scaled_max = int(Fraction(largest_clean_value_minor) * kappa)
        return min(base_cap, scaled_max)
    return base_cap


def evaluate_tier_promotion(profile: TrustProfile) -> str:
    """Section 8.7 & FR-91: Value-weighted, age-gated promotion with kept-order credit and single-step progression (AUD-13)."""
    if profile.tier == "RESTRICTED":
        # RESTRICTED -> NEW: >= 3 clean STANDARD returns with verified value >= confirmed fraud amount AND >= 180 days
        if (
            profile.clean_standard_since_restricted >= 3
            and profile.cumulative_verified_value_minor >= profile.confirmed_fraud_amount_minor
            and profile.days_since_restricted >= 180
        ):
            return "NEW"
        return "RESTRICTED"

    # Kept-order credit: >= 3 kept orders with cumulative value >= $300 (30000 minor) count as 1 clean return
    raw_kept_credits = 0
    if profile.kept_order_count >= 3 and profile.kept_order_value_minor >= 30000:
        raw_kept_credits = min(2, profile.kept_order_count // 3)

    if profile.tier == "NEW":
        # NEW -> ESTABLISHED: >= 2 effective clean returns (max 1 kept credit),
        # cumulative verified value >= $150 (15000 minor), and >= 30 days. Single-step only (AUD-13).
        eff_clean_est = profile.clean_count + min(1, raw_kept_credits)
        if (
            eff_clean_est >= 2
            and profile.cumulative_verified_value_minor >= 15000
            and profile.account_age_days >= 30
        ):
            return "ESTABLISHED"
        return "NEW"

    if profile.tier == "ESTABLISHED":
        # ESTABLISHED -> TRUSTED: >= 5 effective clean returns (audited confirmed counts as 2, up to 2 kept credits),
        # cumulative verified value >= $750 (75000 minor), and >= 90 days.
        eff_clean_trusted = (
            profile.clean_count
            + profile.audited_confirmed_count
            + min(2, raw_kept_credits)
        )
        if (
            eff_clean_trusted >= 5
            and profile.cumulative_verified_value_minor >= 75000
            and profile.account_age_days >= 90
        ):
            return "TRUSTED"
        return "ESTABLISHED"

    return "TRUSTED"


def apply_confirmed_fraud_downgrade(
    profile: TrustProfile,
    *,
    human_confirmed: bool,
    fraud_amount_minor: int,
) -> str:
    """FR-70 & INV-10: Revocation to RESTRICTED requires human confirmation."""
    if not human_confirmed:
        return profile.tier
    profile.tier = "RESTRICTED"
    profile.gross_misdeclare_count += 1
    profile.confirmed_fraud_amount_minor += fraud_amount_minor
    profile.clean_standard_since_restricted = 0
    profile.days_since_restricted = 0
    return "RESTRICTED"
