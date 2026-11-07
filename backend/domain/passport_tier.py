"""Passport tier selection by item value band (FR-63, FR-67)."""

from __future__ import annotations


def select_passport_tier(
    price_minor: int,
    low_max_minor: int = 15000,
    mid_max_minor: int = 60000,
    merchant_override_tier: str | None = None,
) -> str:
    """FR-63: FULL (HIGH > $600), LITE (MID $150-$600), NONE (LOW < $150); merchant may raise tier."""
    rank = {"NONE": 0, "LITE": 1, "FULL": 2}
    if price_minor < low_max_minor:
        base = "NONE"
    elif price_minor <= mid_max_minor:
        base = "LITE"
    else:
        base = "FULL"
    if merchant_override_tier and rank.get(merchant_override_tier, -1) > rank[base]:
        return merchant_override_tier
    return base
