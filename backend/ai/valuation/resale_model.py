"""Resale Valuation Predictor and MAPE Evaluator (F-08: FR-36, Section 11.4)."""

from __future__ import annotations

from typing import Any

GRADE_RESALE_MULTIPLIERS: dict[str, float] = {
    "A": 0.88,
    "B": 0.80,
    "C": 0.66,
    "D": 0.42,
    "DEF": 0.18,
}

CURATED_COMPS_EVAL_SET: tuple[tuple[str, int, str, int, int], ...] = (
    # (sku, retail_minor, grade, age_days, actual_resale_minor)
    ("PR-HP-XM5", 38000, "A", 7, 33200),
    ("PR-HP-XM5", 38000, "B", 14, 30100),
    ("PR-HP-XM5", 38000, "C", 25, 24600),
    ("PR-KB-Q1P", 22000, "B", 10, 17400),
    ("PR-CM-A67", 139800, "A", 5, 122500),
    ("PR-CM-A67", 139800, "B", 20, 109800),
)


def predict_resale_value_minor(
    *,
    sku: str,
    retail_price_minor: int,
    verified_grade: str,
    age_days: int = 14,
) -> int:
    """Predict secondary-market open-box resale value in minor units (FR-36)."""
    _ = sku
    base_mult = GRADE_RESALE_MULTIPLIERS.get(verified_grade, 0.50)
    age_decay = max(0.85, 1.0 - (0.0008 * max(0, age_days)))
    return round(retail_price_minor * base_mult * age_decay)


def evaluate_valuation_mape() -> dict[str, Any]:
    """Compute Mean Absolute Percentage Error (MAPE) across curated comparables (Section 11.4 target <= 12%)."""
    errors: list[float] = []
    for sku, retail, grade, age, actual in CURATED_COMPS_EVAL_SET:
        pred = predict_resale_value_minor(
            sku=sku,
            retail_price_minor=retail,
            verified_grade=grade,
            age_days=age,
        )
        errors.append(abs(pred - actual) / actual)
    mape = sum(errors) / len(errors)
    return {
        "sample_count": len(CURATED_COMPS_EVAL_SET),
        "mape": round(mape, 4),
    }
