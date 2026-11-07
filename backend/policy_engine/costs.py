"""Misdeclaration cost computation and application guardrails (FR-59, INV-10, INV-15, INV-17)."""

from __future__ import annotations

from backend.domain.policy import PolicyConfig


def compute_misdeclaration_cost_minor(
    price_minor: int,
    policy: PolicyConfig,
    *,
    is_confirmed_gross_overclaim: bool,
    human_confirmed: bool,
) -> int:
    """FR-59, INV-10, INV-15: F applies ONLY when a gross overclaim is confirmed by conformal/hard-fail AND human reviewer."""
    if not is_confirmed_gross_overclaim or not human_confirmed:
        return 0
    return policy.compute_f_minor(price_minor)
