"""Certified Open-Box Resale Listing with Public Passport Projection (F-09: FR-40..43)."""

from __future__ import annotations

from typing import Any


def create_certified_open_box_listing(
    *,
    passport_id: str,
    sku: str,
    verified_grade: str,
    list_price_minor: int,
    prior_owner_ref: str,
    prior_buyer_email: str,
) -> dict[str, Any]:
    """Create a Certified Open-Box listing linked to the item's Passport while stripping prior owner PII (FR-42, FR-43)."""
    _ = (prior_owner_ref, prior_buyer_email)  # Explicitly discarded from public listing projection
    return {
        "listing_id": f"ob_{passport_id}",
        "passport_id": passport_id,
        "sku": sku,
        "certified_open_box": True,
        "verified_grade": verified_grade,
        "list_price_minor": list_price_minor,
        "currency": "USD",
        "passport_public_url": f"/v1/passports/{passport_id}",
        "prior_owner_stripped": True,
    }
