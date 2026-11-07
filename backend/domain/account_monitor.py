"""CUSUM Account Monitor for repeated adjacent-grade mismatches (Section 8.7, FR-62, FR-103)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class CusumConfig:
    """FR-103: Per-category calibrated honest mismatch rate theta0, target shift theta1, and ARL threshold h_c."""

    # ASSUMPTION(A-22): Honest adjacent-mismatch rate theta0 is category-specific
    theta0: Fraction = Fraction(10, 100)
    theta1: Fraction = Fraction(40, 100)
    threshold_h: Fraction = Fraction(40, 10)  # 4.0 for theta0=0.10, 3.5 for theta0=0.20

    @classmethod
    def for_category_theta0(cls, theta0: Fraction) -> CusumConfig:
        """Section 8.7: Calibrate threshold h_c for <= 5.5% false alarms within 20 verified returns."""
        if theta0 >= Fraction(20, 100):
            return cls(theta0=theta0, theta1=Fraction(50, 100), threshold_h=Fraction(35, 10))
        return cls(theta0=theta0, theta1=Fraction(40, 100), threshold_h=Fraction(40, 10))

    def log_likelihood_step(self, is_adjacent_below: bool) -> Fraction:
        p0 = float(self.theta0)
        p1 = float(self.theta1)
        if is_adjacent_below:
            val = math.log(p1 / p0)
        else:
            val = math.log((1.0 - p1) / (1.0 - p0))
        return Fraction(round(val * 1_000_000), 1_000_000)


class CusumMonitor:
    """FR-62 & FR-103: One-sided Bernoulli CUSUM monitor; alarm downgrades 1 tier and opens review, never applies F."""

    def __init__(self, config: CusumConfig | None = None) -> None:
        self.config = config or CusumConfig()
        self.cusum_value: Fraction = Fraction(0)
        self.observation_count: int = 0
        self.alarm_triggered: bool = False

    def observe(self, *, is_adjacent_below: bool) -> bool:
        self.observation_count += 1
        step = self.config.log_likelihood_step(is_adjacent_below)
        self.cusum_value = max(Fraction(0), self.cusum_value + step)
        if self.cusum_value >= self.config.threshold_h:
            self.alarm_triggered = True
            return True
        return False

    def reset_after_review(self) -> None:
        """FR-103: S is reset to 0 after each completed review."""
        self.cusum_value = Fraction(0)
        self.alarm_triggered = False


def check_subgroup_alarm_fairness(
    global_alarm_rate: Fraction,
    subgroup_alarm_rates: dict[str, Fraction],
) -> tuple[bool, list[str]]:
    """FR-103 & Section 12.3: Any device/lighting subgroup above 2x global rate blocks release."""
    flagged: list[str] = []
    limit = Fraction(2, 1) * global_alarm_rate
    for subgroup, rate in subgroup_alarm_rates.items():
        if rate > limit:
            flagged.append(subgroup)
    return (len(flagged) == 0), flagged
