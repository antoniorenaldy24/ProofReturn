"""Circular Disposition Engine comparing net recovery across 5 post-return paths (F-08: FR-38, FR-39, FR-40)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DispositionOption:
    """Expected net recovery for a single disposition option."""

    option: str
    expected_recovery_minor: int
    cost_minor: int
    net_recovery_minor: int


@dataclass(frozen=True)
class DispositionComparison:
    """Side-by-side comparison of all 5 disposition paths."""

    verified_grade: str
    options: list[DispositionOption]
    recommended_option: str


def evaluate_disposition_options(
    *,
    price_minor: int,
    verified_grade: str,
    estimated_resale_minor: int,
    refurb_cost_minor: int,
    return_shipping_minor: int,
    handling_minor: int,
) -> DispositionComparison:
    """Compare RESTOCK_AS_NEW, OPEN_BOX_RESALE, REFURBISH, SALVAGE, and RECYCLE (FR-38)."""
    logistics = return_shipping_minor + handling_minor
    restock_gross = price_minor if verified_grade == "A" else round(estimated_resale_minor * 0.90)
    open_box_gross = estimated_resale_minor
    refurb_gross = round(price_minor * 0.88)
    salvage_gross = round(price_minor * 0.25)
    recycle_gross = round(price_minor * 0.05)

    opts = [
        DispositionOption("RESTOCK_AS_NEW", restock_gross, logistics, restock_gross - logistics),
        DispositionOption("OPEN_BOX_RESALE", open_box_gross, logistics, open_box_gross - logistics),
        DispositionOption(
            "REFURBISH",
            refurb_gross,
            logistics + refurb_cost_minor,
            refurb_gross - logistics - refurb_cost_minor,
        ),
        DispositionOption("SALVAGE", salvage_gross, logistics, salvage_gross - logistics),
        DispositionOption("RECYCLE", recycle_gross, handling_minor, recycle_gross - handling_minor),
    ]
    best = max(opts, key=lambda o: o.net_recovery_minor)
    return DispositionComparison(
        verified_grade=verified_grade,
        options=opts,
        recommended_option=best.option,
    )
