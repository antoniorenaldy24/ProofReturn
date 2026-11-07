"""Intake & Explanation Agent Output Guard preventing outcome promises (F-03: FR-15)."""

from __future__ import annotations

from typing import Any

FORBIDDEN_OUTCOME_PROMISE_PATTERNS: tuple[str, ...] = (
    "guaranteed an instant refund",
    "guaranteed instant refund",
    "100% approved",
    "zero inspection",
    "automatic approval guaranteed",
    "money is already in your account",
)


def validate_intake_explanation(text: str) -> dict[str, Any]:
    """Verify intake/explanation agent text contains no unauthorized financial outcome promises (FR-15)."""
    lowered = text.lower()
    for pat in FORBIDDEN_OUTCOME_PROMISE_PATTERNS:
        if pat in lowered:
            return {
                "valid": False,
                "violation": "OUTCOME_PROMISE_FORBIDDEN",
                "matched_pattern": pat,
            }
    return {
        "valid": True,
        "violation": None,
    }
