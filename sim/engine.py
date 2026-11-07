"""Rule-based simulator executing settlement rules (Section 8.4) and state transitions directly (FR-102, MV-12)."""

from __future__ import annotations

import math
import random
from fractions import Fraction
from typing import Any

from backend.domain.policy import PolicyConfig
from backend.policy_engine.lanes import route_intake_and_refile
from backend.policy_engine.release import ReleaseInput, decide_release
from backend.policy_engine.settlement import SettlementInput, settle_return
from sim.fmap import _illustrative_calib


def simulate_single_return_episode(
    *,
    rng: random.Random,
    price_minor: int,
    declared_grade: str,
    true_grade: str,
    tier: str,
    policy: PolicyConfig,
    q_exclude: float,
    d_exclude: float,
    cancel_if_routed_standard: bool = True,
) -> float:
    """Execute one return episode through intake routing, release decision, check-in, audit draw, and settlement."""
    truthful_refund = float(Fraction(price_minor) * policy.grade_fraction(true_grade))
    l_minor = float(policy.tier_l_minor(tier))

    # Stage 1: Intake assessment and routing
    intake_excluded = rng.random() < q_exclude
    routing = route_intake_and_refile(
        intake_excluded=intake_excluded,
        refiled_after_cancel=False,
        hard_failure=False,
        nonce_unreadable=False,
    )
    if routing.lane == "STANDARD" and cancel_if_routed_standard:
        # Routing semantics (Section 8.4 Rule 1 & FR-88): shopper cancels freely and re-files truthfully -> gain 0
        return 0.0

    calib = _illustrative_calib(declared_grade)
    rel = decide_release(
        ReleaseInput(
            price_minor=price_minor,
            declared_grade=declared_grade,
            tier=tier,
            has_origin_passport=True,
            intake_excluded=intake_excluded,
            account_cap_remaining_minor=10_000_000,
            merchant_cap_remaining_minor=10_000_000,
        ),
        policy,
        calib,
    )

    # Stage 2: Check-in and sampled audit
    checkin_excluded = rng.random() < d_exclude
    audit_selected = rng.random() < float(rel.p)
    caught = checkin_excluded or audit_selected

    verified_grade = true_grade if caught else declared_grade
    s_res = settle_return(
        SettlementInput(
            price_minor=price_minor,
            capture_amount_minor=price_minor,
            declared_grade=declared_grade,
            verified_grade=verified_grade,
            x_released_minor=rel.x_released_minor,
            holdback_minor=rel.holdback_minor,
            f_minor=rel.f_minor,
            human_confirmed_gross=caught,
            excluded_at_alpha_accuse=caught,
            has_merchant_evidence=True,
        ),
        policy,
    )
    status_cost = l_minor if s_res.status_affected else 0.0
    net_payoff = float(s_res.final_total_refund_minor) - status_cost
    return net_payoff - truthful_refund


def simulate_cell_analytic_agreement(
    *,
    price_minor: int = 40000,
    declared_grade: str = "B",
    tier: str = "TRUSTED",
    n_trials: int = 4000,
    seed: int = 42,
) -> dict[str, Any]:
    """MV-12: Compare mean simulated gain from rule execution against analytic G_k within 95% CI."""
    policy = PolicyConfig.default_us()
    calib = _illustrative_calib(declared_grade)
    rel = decide_release(
        ReleaseInput(
            price_minor=price_minor,
            declared_grade=declared_grade,
            tier=tier,
            has_origin_passport=True,
            account_cap_remaining_minor=10_000_000,
            merchant_cap_remaining_minor=10_000_000,
        ),
        policy,
        calib,
    )
    gap = calib.gross_gaps[-1]  # worst gross gap (D)
    rng = random.Random(seed)
    gains = [
        simulate_single_return_episode(
            rng=rng,
            price_minor=price_minor,
            declared_grade=declared_grade,
            true_grade=gap.true_grade,
            tier=tier,
            policy=policy,
            q_exclude=float(gap.q),
            d_exclude=float(gap.d),
            cancel_if_routed_standard=True,
        )
        for _ in range(n_trials)
    ]
    mean_sim = sum(gains) / len(gains)
    var_sim = sum((x - mean_sim) ** 2 for x in gains) / max(1, len(gains) - 1)
    se_sim = math.sqrt(var_sim / len(gains))
    ci_half_width = 1.96 * se_sim + 5.0  # allow minor-unit rounding tolerance
    analytic_g = float(rel.worst_gross_gain_minor)
    within_ci = abs(mean_sim - analytic_g) <= ci_half_width

    return {
        "mean_simulated_minor": mean_sim,
        "analytic_g_minor": analytic_g,
        "ci_half_width_minor": ci_half_width,
        "within_95_ci": within_ci,
    }
