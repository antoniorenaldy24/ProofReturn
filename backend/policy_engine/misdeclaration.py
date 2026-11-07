"""Misdeclaration evaluation enforcing one-sided conformal exclusion + human confirmation (FR-25, FR-26, INV-10, INV-15)."""

from __future__ import annotations

from dataclasses import dataclass

from backend.domain.constants import GRADE_RANK

GRADE_ORDER = GRADE_RANK


@dataclass(frozen=True)
class MisdeclarationEvaluation:
    gap_steps: int
    is_adjacent_mismatch: bool
    is_confirmed_gross: bool
    status_affecting: bool
    feed_account_monitor: bool
    explanation: str


def evaluate_misdeclaration(
    *,
    declared_grade: str,
    verified_grade: str,
    excluded_at_alpha_accuse: bool,
    hard_identity_failure: bool,
    human_confirmed: bool,
) -> MisdeclarationEvaluation:
    """FR-25, FR-26, INV-10, INV-15: Adjacent mismatches never penalize; gross requires alpha_accuse/hard-fail AND human review."""
    g_d = GRADE_ORDER.get(declared_grade, 0)
    g_v = GRADE_ORDER.get(verified_grade, 0)
    gap = g_d - g_v

    if not hard_identity_failure and gap <= 0:
        return MisdeclarationEvaluation(
            gap_steps=gap,
            is_adjacent_mismatch=False,
            is_confirmed_gross=False,
            status_affecting=False,
            feed_account_monitor=False,
            explanation="Check-in grade matches or exceeds your declaration.",
        )

    if not hard_identity_failure and gap == 1:
        # INV-15: Single adjacent-grade mismatch is settled within holdback, never penalized or accused
        return MisdeclarationEvaluation(
            gap_steps=1,
            is_adjacent_mismatch=True,
            is_confirmed_gross=False,
            status_affecting=False,
            feed_account_monitor=True,
            explanation="Check-in graded the item one step lower than declared. Your refund is settled at the verified grade with no fee or status penalty.",
        )

    # Gross gap (gap >= 2 or hard identity failure): INV-10 requires (excluded_at_alpha_accuse or hard_identity_failure) AND human_confirmed
    qualifies_evidence = excluded_at_alpha_accuse or hard_identity_failure
    confirmed_gross = qualifies_evidence and human_confirmed
    return MisdeclarationEvaluation(
        gap_steps=max(gap, 2 if hard_identity_failure else gap),
        is_adjacent_mismatch=False,
        is_confirmed_gross=confirmed_gross,
        status_affecting=confirmed_gross,
        feed_account_monitor=False,
        explanation=(
            "A reviewer confirmed a significant condition or identity discrepancy against the origin Condition Passport."
            if confirmed_gross
            else "Discrepancy routed for human review before any status-affecting decision."
        ),
    )
