"""Lane routing semantics, hard-failure escalation, and re-file rules (FR-19, FR-65, FR-68, FR-88, INV-17)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntakeRoutingResult:
    lane: str
    reason_code: str
    explanation: str
    penalty_minor: int = 0
    status_affected: bool = False


def route_intake_and_refile(
    *,
    intake_excluded: bool,
    refiled_after_cancel: bool,
    hard_failure: bool,
    nonce_unreadable: bool,
    declared_def_without_selftest: bool = False,
) -> IntakeRoutingResult:
    """FR-19, FR-65, FR-68, FR-88, INV-17: Route intake exclusions and re-files to STANDARD with zero penalty."""
    if hard_failure:
        return IntakeRoutingResult(
            lane="ESCALATED",
            reason_code="HARD_FORENSIC_OR_IDENTITY_FAILURE",
            explanation="A person is reviewing this return because the serial number or package seal did not match.",
            penalty_minor=0,
            status_affected=False,
        )
    if refiled_after_cancel:
        return IntakeRoutingResult(
            lane="STANDARD",
            reason_code="REFILE_STANDARD_ONLY",
            explanation="Because a previous return for this item was cancelled after routing, this return will be refunded after warehouse check-in.",
            penalty_minor=0,
            status_affected=False,
        )
    if declared_def_without_selftest:
        return IntakeRoutingResult(
            lane="STANDARD",
            reason_code="DEF_SELFTEST_REQUIRED_AT_CHECKIN",
            explanation="We will perform a quick functional check when your item arrives and issue your full refund.",
            penalty_minor=0,
            status_affected=False,
        )
    if nonce_unreadable:
        # FR-65: Unreadable nonce is never escalated by itself; routes to STANDARD after retry
        return IntakeRoutingResult(
            lane="STANDARD",
            reason_code="NONCE_UNREADABLE_STANDARD_FALLBACK",
            explanation="We could not clearly read the seal code in the photo, so we will verify the item at check-in with no penalty.",
            penalty_minor=0,
            status_affected=False,
        )
    if intake_excluded:
        return IntakeRoutingResult(
            lane="STANDARD",
            reason_code="INTAKE_ROUTED_TO_STANDARD",
            explanation="We will confirm the item's condition at check-in before issuing your refund. You may also cancel this return at no cost.",
            penalty_minor=0,
            status_affected=False,
        )
    return IntakeRoutingResult(
        lane="FAST",
        reason_code="INTAKE_ELIGIBLE",
        explanation="Intake checks passed.",
        penalty_minor=0,
        status_affected=False,
    )
