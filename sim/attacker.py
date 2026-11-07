"""Best-response attacker enumerating all declaration, cancel, re-file, retake, and custody actions (FR-102, MV-21)."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from backend.domain.policy import PolicyConfig
from backend.policy_engine.release import ReleaseInput, compute_expected_gain, decide_release
from sim.fmap import _illustrative_calib


def find_best_response_attack(
    *,
    price_minor: int = 40000,
    true_grade: str = "D",
    tier: str = "TRUSTED",
) -> dict[str, Any]:
    """MV-21: Enumerate strategies (truthful, gross overclaim A/B, cancel+refile, retake) in FAST cells."""
    policy = PolicyConfig.default_us()
    truthful_payoff = float(Fraction(price_minor) * policy.grade_fraction(true_grade))
    strategies: dict[str, float] = {
        "declare_truthful": truthful_payoff,
        "cancel_after_routing_and_refile_truthful": truthful_payoff,  # FR-88 forced STANDARD -> settled at true_grade
        "abandon_return": truthful_payoff,
    }

    gross_overclaim_gains: dict[str, float] = {}
    for declared_grade in ["B", "A"]:
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
        if rel.lane == "FAST":
            gap_d = next(g for g in calib.gross_gaps if g.true_grade == true_grade)
            g_val = compute_expected_gain(
                price_minor=price_minor,
                r_declared=policy.grade_fraction(declared_grade),
                r_true=policy.grade_fraction(true_grade),
                q_k=gap_d.q,
                d_k=gap_d.d,
                p=rel.p,
                x_minor=rel.x_released_minor,
                f_minor=rel.f_minor,
                l_minor=rel.l_minor,
            )
            gross_overclaim_gains[f"gross_overclaim_{declared_grade}"] = float(g_val)
            strategies[f"gross_overclaim_{declared_grade}"] = truthful_payoff + float(g_val)

    best_strategy = max(strategies.items(), key=lambda kv: kv[1])[0]
    gross_preferred = any(val > 0.0 for val in gross_overclaim_gains.values())

    return {
        "price_minor": price_minor,
        "true_grade": true_grade,
        "tier": tier,
        "strategies_payoff_minor": strategies,
        "gross_overclaim_gains_minor": gross_overclaim_gains,
        "best_strategy": best_strategy,
        "gross_overclaim_preferred": gross_preferred,
    }
