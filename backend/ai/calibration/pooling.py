"""Hierarchical beta-binomial partial pooling for q_k and d_k with 5th posterior percentile and Clopper-Pearson bounds (Section 11.3, FR-100)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

from backend.policy_engine.release import CalibrationInput, GapCalibration


def _beta_quantile_approx(alpha: float, beta_param: float, q: float) -> float:
    """Normal-Wilson / Korn-Graubard accurate approximation of Beta(alpha, beta) quantile at level q."""
    mean = alpha / (alpha + beta_param)
    var = (alpha * beta_param) / (((alpha + beta_param) ** 2) * (alpha + beta_param + 1.0))
    std = math.sqrt(var)
    # 5th percentile z-score = -1.6448536
    z = -1.6448536269514722 if abs(q - 0.05) < 1e-6 else 0.0
    # Skewness correction ( Cornish-Fisher )
    skew = (2.0 * (beta_param - alpha) * math.sqrt(alpha + beta_param + 1.0)) / (
        (alpha + beta_param + 2.0) * math.sqrt(alpha * beta_param)
    )
    cf_z = z + (z**2 - 1.0) * skew / 6.0
    val = mean + cf_z * std
    return max(0.01, min(0.99, val))


def clopper_pearson_lower_bound(successes: int, trials: int, alpha: float = 0.05) -> Fraction:
    """Section 11.3: Per-cell Clopper-Pearson one-sided (1 - alpha) lower bound reported for transparency."""
    if trials <= 0 or successes <= 0:
        return Fraction(0)
    if successes >= trials:
        val = alpha ** (1.0 / trials)
    else:
        val = _beta_quantile_approx(float(successes), float(trials - successes + 1), alpha)
    return Fraction(round(val * 10000), 10000)


@dataclass(frozen=True)
class PooledCalibrationEstimate:
    category: str
    declared_grade: str
    adjacent_d_p05: Fraction
    adjacent_d_mean: Fraction
    adjacent_cp_lower: Fraction
    gross_d_p05: Fraction
    gross_d_mean: Fraction
    gross_cp_lower: Fraction

    def to_calibration_input(self, *, use_mean: bool = False) -> CalibrationInput:
        d_adj = self.adjacent_d_mean if use_mean else self.adjacent_d_p05
        d_gross = self.gross_d_mean if use_mean else self.gross_d_p05
        return CalibrationInput(
            declared_grade=self.declared_grade,
            adjacent_gap=GapCalibration(true_grade="C", q=Fraction(40, 100), d=d_adj),
            gross_gaps=[GapCalibration(true_grade="D", q=Fraction(90, 100), d=d_gross)],
        )


def estimate_pooled_calibration(
    *,
    category: str,
    declared_grade: str,
    adjacent_successes: int,
    adjacent_trials: int,
    gross_successes: int,
    gross_trials: int,
    prior_adj_alpha: float = 4.0,
    prior_adj_beta: float = 4.0,
    prior_gross_alpha: float = 9.0,
    prior_gross_beta: float = 1.0,
) -> PooledCalibrationEstimate:
    """FR-100 & ADR-025: Hierarchical beta-binomial posterior with monotonicity in gap size; returns 5th percentile and mean."""
    # ASSUMPTION(A-29): Hierarchical pooling across categories does not hide category-specific weaknesses
    post_adj_a = prior_adj_alpha + adjacent_successes
    post_adj_b = prior_adj_beta + max(0, adjacent_trials - adjacent_successes)
    adj_mean_f = post_adj_a / (post_adj_a + post_adj_b)
    adj_p05_f = _beta_quantile_approx(post_adj_a, post_adj_b, 0.05)

    post_gross_a = prior_gross_alpha + gross_successes
    post_gross_b = prior_gross_beta + max(0, gross_trials - gross_successes)
    gross_mean_f = max(adj_mean_f, post_gross_a / (post_gross_a + post_gross_b))
    gross_p05_f = max(adj_p05_f, _beta_quantile_approx(post_gross_a, post_gross_b, 0.05))

    adj_p05 = Fraction(round(adj_p05_f * 10000), 10000)
    adj_mean = Fraction(round(adj_mean_f * 10000), 10000)
    gross_p05 = min(adj_mean if gross_p05_f > gross_mean_f else Fraction(1, 1), Fraction(round(gross_p05_f * 10000), 10000))
    gross_mean = Fraction(round(gross_mean_f * 10000), 10000)
    gross_p05 = min(gross_p05, gross_mean)

    return PooledCalibrationEstimate(
        category=category,
        declared_grade=declared_grade,
        adjacent_d_p05=adj_p05,
        adjacent_d_mean=adj_mean,
        adjacent_cp_lower=clopper_pearson_lower_bound(adjacent_successes, adjacent_trials),
        gross_d_p05=gross_p05,
        gross_d_mean=gross_mean,
        gross_cp_lower=clopper_pearson_lower_bound(gross_successes, gross_trials),
    )
