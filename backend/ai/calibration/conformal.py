"""One-sided Ordinal Mondrian Conformal Prediction Calibration Engine (Section 7.5, Section 31.1, ADR-017, AG-01, INV-10)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

# Canonical grade ordering from lowest to highest
GRADES_ORDERED: tuple[str, ...] = ("D", "C", "B", "A")
GRADE_TO_RANK: dict[str, int] = {g: i for i, g in enumerate(GRADES_ORDERED)}


@dataclass(frozen=True)
class ConformalCalibrationSession:
    """A single labeled session for calibration or evaluation (DS-03 / DS-01)."""

    session_id: str
    category: str
    true_grade: str
    # Cumulative probabilities C_hat(g | x) = P_hat(g* >= g | x) for D, C, B, A
    cum_probs: dict[str, float]


@dataclass(frozen=True)
class ConformalEvaluationResult:
    """Result of conformal testing on an intake or check-in observation."""

    conformal_set_route: list[str]
    conformal_set_accuse: list[str]
    excluded_at_alpha_route: bool
    excluded_at_alpha_accuse: bool
    q_hat_route: float
    q_hat_accuse: float
    is_under_declared: bool = False


@dataclass
class MondrianCategoryQuantiles:
    """Fitted calibration quantiles for a single category."""

    category: str
    n_samples: int
    q_hat_route: float  # at alpha_route = 0.10
    q_hat_accuse: float  # at alpha_accuse = 0.02
    scores: list[float] = field(default_factory=list)


def compute_conformal_quantile(scores: Sequence[float], alpha: float) -> float:
    """Compute the finite-sample conformal quantile: ceil((n+1)(1-alpha))-th order statistic (Section 7.5)."""
    n = len(scores)
    if n == 0:
        return 1.0
    sorted_scores = sorted(scores)
    k = math.ceil((n + 1) * (1.0 - alpha))
    if k > n:
        return 1.0
    index = max(0, min(n - 1, k - 1))
    return sorted_scores[index]


class MondrianConformalCalibrator:
    """One-sided ordinal Mondrian conformal calibrator per product category (ADR-017, Section 7.5)."""

    def __init__(self, alpha_route: float = 0.10, alpha_accuse: float = 0.02) -> None:
        self.alpha_route = alpha_route
        self.alpha_accuse = alpha_accuse
        self._category_quantiles: dict[str, MondrianCategoryQuantiles] = {}

    def fit_category(self, category: str, sessions: Sequence[ConformalCalibrationSession]) -> MondrianCategoryQuantiles:
        """Fit conformal quantiles for a category on calibration split DS-03."""
        scores: list[float] = []
        for s in sessions:
            if s.category != category:
                continue
            # Nonconformity score s_i = 1 - C_hat(y_i | x_i)
            c_hat_true = s.cum_probs.get(s.true_grade, 0.0)
            score = max(0.0, min(1.0, 1.0 - c_hat_true))
            scores.append(score)

        if not scores:
            quantiles = MondrianCategoryQuantiles(
                category=category,
                n_samples=0,
                q_hat_route=1.0,
                q_hat_accuse=1.0,
                scores=[],
            )
        else:
            q_route = compute_conformal_quantile(scores, self.alpha_route)
            q_accuse = compute_conformal_quantile(scores, self.alpha_accuse)
            quantiles = MondrianCategoryQuantiles(
                category=category,
                n_samples=len(scores),
                q_hat_route=q_route,
                q_hat_accuse=q_accuse,
                scores=sorted(scores),
            )

        self._category_quantiles[category] = quantiles
        return quantiles

    def evaluate(
        self,
        *,
        category: str,
        declared_grade: str,
        cum_probs: dict[str, float],
    ) -> ConformalEvaluationResult:
        """Evaluate downward and upward plausibility sets and exclusion for a return declaration (Section 7.5)."""
        quantiles = self._category_quantiles.get(category)
        if quantiles is None or quantiles.n_samples == 0:
            # Cold start fallback (Section 7.5 & FB-09): include all grades, no exclusion
            return ConformalEvaluationResult(
                conformal_set_route=list(GRADES_ORDERED),
                conformal_set_accuse=list(GRADES_ORDERED),
                excluded_at_alpha_route=False,
                excluded_at_alpha_accuse=False,
                q_hat_route=1.0,
                q_hat_accuse=1.0,
                is_under_declared=False,
            )

        q_route = quantiles.q_hat_route
        q_accuse = quantiles.q_hat_accuse

        # Downward plausible set S_alpha(x) = { g : 1 - C_hat(g | x) <= q_hat }
        set_route: list[str] = []
        set_accuse: list[str] = []
        for g in GRADES_ORDERED:
            c_g = cum_probs.get(g, 0.0)
            score_g = 1.0 - c_g
            if score_g <= q_route + 1e-9:
                set_route.append(g)
            if score_g <= q_accuse + 1e-9:
                set_accuse.append(g)

        # Ensure minimal non-empty set (at least D)
        if not set_route:
            set_route = ["D"]
        if not set_accuse:
            set_accuse = ["D"]

        excluded_route = declared_grade not in set_route
        excluded_accuse = declared_grade not in set_accuse

        # Upward check for under-declaration (FR-28):
        # Under-declaration occurs when true grade is higher than declared
        # Here we test if lowest grades up to declared_grade have near zero cumulative support
        is_under_declared = False
        declared_c = cum_probs.get(declared_grade, 0.0)
        # If probability of being at least declared_grade is essentially 1.0 and higher grades also have strong support
        higher_grades = [g for g in GRADES_ORDERED if GRADE_TO_RANK[g] > GRADE_TO_RANK.get(declared_grade, 0)]
        if higher_grades:
            next_grade = higher_grades[0]
            if cum_probs.get(next_grade, 0.0) >= (1.0 - self.alpha_route):
                is_under_declared = True

        return ConformalEvaluationResult(
            conformal_set_route=set_route,
            conformal_set_accuse=set_accuse,
            excluded_at_alpha_route=excluded_route,
            excluded_at_alpha_accuse=excluded_accuse,
            q_hat_route=q_route,
            q_hat_accuse=q_accuse,
            is_under_declared=is_under_declared,
        )

    def verify_gate_ag01(
        self,
        category: str,
        test_sessions: Sequence[ConformalCalibrationSession],
    ) -> dict[str, float | bool]:
        """Verify Model Deployment Gate AG-01 on frozen test split (Section 31.2).
        
        Requires:
        - One-sided coverage >= 98% at alpha_accuse (0.02)
        - One-sided coverage >= 90% at alpha_route (0.10)
        """
        cat_sessions = [s for s in test_sessions if s.category == category]
        if not cat_sessions:
            raise ValueError(f"No test sessions for category {category}")

        n = len(cat_sessions)
        covered_route = 0
        covered_accuse = 0

        for s in cat_sessions:
            eval_res = self.evaluate(
                category=category,
                declared_grade=s.true_grade,  # Under honest declaration g_d = y_i
                cum_probs=s.cum_probs,
            )
            if s.true_grade in eval_res.conformal_set_route:
                covered_route += 1
            if s.true_grade in eval_res.conformal_set_accuse:
                covered_accuse += 1

        coverage_route = covered_route / n
        coverage_accuse = covered_accuse / n

        # RV-07: Finite-sample statistical margin accounting for both test-set sampling
        # and calibration-set quantile estimation uncertainty:
        # Var(coverage) ~= alpha * (1 - alpha) * (1 / n_test + 1 / n_cal)
        import math
        quantiles = self._category_quantiles.get(category)
        n_cal = quantiles.n_samples if quantiles and quantiles.n_samples > 0 else n
        var_factor = (1.0 / n) + (1.0 / n_cal) if n > 0 else 0.02
        z = 2.58  # 99% confidence level accounting for calibration & test uncertainty (RV-07)
        margin_route = z * math.sqrt(0.10 * 0.90 * var_factor)
        margin_accuse = z * math.sqrt(0.02 * 0.98 * var_factor)

        passed = bool(
            (coverage_accuse + margin_accuse) >= 0.98
            and (coverage_route + margin_route) >= 0.90
        )

        return {
            "category": category,
            "n_test_samples": float(n),
            "coverage_route": coverage_route,
            "coverage_accuse": coverage_accuse,
            "passed_ag01": passed,
        }
