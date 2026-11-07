"""Deterministic return settlement rules 1-8 (Section 8.4, FR-23, FR-26, FR-28, FR-32, FR-73, INV-01, INV-10, INV-15)."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from backend.domain.policy import PolicyConfig
from backend.policy_engine.misdeclaration import GRADE_ORDER, evaluate_misdeclaration


@dataclass(frozen=True)
class SettlementInput:
    price_minor: int
    capture_amount_minor: int
    declared_grade: str
    verified_grade: str
    x_released_minor: int
    holdback_minor: int
    f_minor: int
    human_confirmed_gross: bool = False
    excluded_at_alpha_accuse: bool = False
    hard_identity_failure: bool = False
    has_merchant_evidence: bool = False
    already_refunded_external_minor: int = 0


@dataclass(frozen=True)
class SettlementResult:
    effective_verified_grade: str
    final_total_refund_minor: int
    additional_refund_minor: int
    topup_minor: int
    f_charged_minor: int
    status_affected: bool
    new_tier_override: str | None
    feed_account_monitor: bool
    explanation: str
    status: str = "SETTLED"
    is_escalated: bool = False


def settle_return(inp: SettlementInput, policy: PolicyConfig) -> SettlementResult:
    """Section 8.4 & FR-23, FR-28, FR-32, FR-73, INV-01, INV-10, INV-15: Compute final settlement tranches and status effects."""
    from backend.policy_engine.caps import validate_curve_for_jurisdiction

    validate_curve_for_jurisdiction(policy, policy.jurisdiction, settlement_f_minor=inp.f_minor)
    # FR-32: Two-way fairness: merchant claim that item is worse than declared requires check-in/audit evidence
    effective_grade = inp.verified_grade if inp.has_merchant_evidence else inp.declared_grade

    g_d_rank = GRADE_ORDER.get(inp.declared_grade, 0)
    g_v_rank = GRADE_ORDER.get(effective_grade, 0)

    declared_target_minor = int(Fraction(inp.price_minor) * policy.grade_fraction(inp.declared_grade))
    verified_target_minor = int(Fraction(inp.price_minor) * policy.grade_fraction(effective_grade))

    mis = evaluate_misdeclaration(
        declared_grade=inp.declared_grade,
        verified_grade=effective_grade,
        excluded_at_alpha_accuse=inp.excluded_at_alpha_accuse,
        hard_identity_failure=inp.hard_identity_failure,
        human_confirmed=inp.human_confirmed_gross,
    )

    topup_minor = 0
    f_charged_minor = 0
    new_tier_override: str | None = None
    status = "SETTLED"
    is_escalated = False

    if g_v_rank > g_d_rank and not inp.hard_identity_failure:
        # FR-28: Under-declaration never benefits the merchant -> automatic top-up to verified grade
        raw_final = verified_target_minor
        topup_minor = max(0, verified_target_minor - declared_target_minor)
        explanation = (
            f"Good news: check-in verified your item at Grade {effective_grade}, higher than declared. "
            f"We automatically topped up your refund by ${topup_minor / 100:.2f}."
        )
    elif g_v_rank == g_d_rank and not inp.hard_identity_failure:
        raw_final = declared_target_minor
        explanation = f"Check-in confirmed Grade {effective_grade}. Your remaining refund and holdback are released."
    elif mis.is_adjacent_mismatch:
        # INV-15 & FR-26: Adjacent mismatch settled at verified grade within holdback; no F, no status loss
        raw_final = max(inp.x_released_minor, verified_target_minor)
        explanation = mis.explanation
    else:
        # Gross mismatch (gap >= 2) or hard identity failure (Section 8.4 Rule 5, FR-73, AUD-08)
        if not inp.human_confirmed_gross:
            status = "ESCALATED"
            is_escalated = True
            raw_final = inp.x_released_minor
            explanation = (
                "Discrepancy routed for human review before any status-affecting decision (Rule 5, FR-73). "
                "Remaining tranches are frozen."
            )
        elif mis.is_confirmed_gross:
            f_charged_minor = policy.compute_f_minor(inp.price_minor)
            # Section 8.4 Rule 5: final refund = max(X, P*r(g*) - F); released tranches are never clawed back
            raw_final = max(inp.x_released_minor, max(0, verified_target_minor - f_charged_minor))
            new_tier_override = "RESTRICTED"
            explanation = mis.explanation
        else:
            # Unconfirmed by conformal exclusion or hard failure -> cannot charge F or restrict status (INV-10)
            raw_final = max(inp.x_released_minor, verified_target_minor)
            explanation = "Settled at the verified grade without misdeclaration fee (conformal exclusion not established, INV-10)."

    # INV-01: Sum of all refunds against a capture never exceeds the captured amount
    max_refundable_total = max(0, inp.capture_amount_minor - inp.already_refunded_external_minor)
    final_total_refund_minor = min(raw_final, max_refundable_total)
    additional_refund_minor = 0 if is_escalated else max(0, final_total_refund_minor - inp.x_released_minor)

    return SettlementResult(
        effective_verified_grade=effective_grade,
        final_total_refund_minor=final_total_refund_minor,
        additional_refund_minor=additional_refund_minor,
        topup_minor=topup_minor,
        f_charged_minor=f_charged_minor,
        status_affected=bool(mis.status_affecting and inp.human_confirmed_gross),
        new_tier_override=new_tier_override,
        feed_account_monitor=mis.feed_account_monitor,
        explanation=explanation,
        status=status,
        is_escalated=is_escalated,
    )
