"""Honesty Mechanism v2.1 Release Engine: dynamic pre-check-in amount X_max, timing, caps, and fallback degradation (Section 8 & 25, FR-58, FR-60, FR-74, FR-87, FR-89, FR-92, INV-14, INV-18)."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

from backend.domain.policy import PolicyConfig
from backend.policy_engine.audit_probability import (
    compute_adjacent_leak,
    compute_pi,
    solve_minimal_audit_probability,
)

ADJACENT_GRADE_BELOW = {
    "A": "B",
    "B": "C",
    "C": "D",
    "D": None,
    "DEF": "A",
}

TIMING_RANK = {"R0": 0, "R1": 1, "R2": 2, "STANDARD": 3}


@dataclass(frozen=True)
class GapCalibration:
    true_grade: str
    q: Fraction
    d: Fraction


@dataclass(frozen=True)
class CalibrationInput:
    # ASSUMPTION(A-09): q_k and d_k estimated on DS-02 generalize with 5th-percentile bounds
    declared_grade: str
    adjacent_gap: GapCalibration | None = None
    gross_gaps: list[GapCalibration] = field(default_factory=list)


@dataclass(frozen=True)
class ReleaseInput:
    price_minor: int
    declared_grade: str
    tier: str
    has_origin_passport: bool = True
    intake_excluded: bool = False
    refiled_after_cancel: bool = False
    drop_off_verified: bool = False
    non_serialized: bool = False
    account_cap_remaining_minor: int = 100000
    merchant_cap_remaining_minor: int = 500000


@dataclass(frozen=True)
class ReleaseDecision:
    lane: str
    timing: str
    p: Fraction
    declared_refund_minor: int
    holdback_minor: int
    x_max_minor: int
    x_released_minor: int
    checkin_tranche_minor: int
    f_minor: int
    l_minor: int
    binding_constraint: str
    worst_gross_gain_minor: Fraction
    adjacent_leak_per_attempt_minor: Fraction
    explanation: str
    _constraint_checker: object | None = field(default=None, repr=False)

    @property
    def timing_rank(self) -> int:
        return TIMING_RANK.get(self.timing, 3)

    def satisfies_constraints_at(self, p_test: Fraction) -> bool:
        if callable(self._constraint_checker):
            return bool(self._constraint_checker(p_test))
        return False


def ceil_fraction_to_int(val: Fraction) -> int:
    return -((-val.numerator) // val.denominator)


def floor_fraction_to_int(val: Fraction) -> int:
    return val.numerator // val.denominator


def compute_expected_gain(
    *,
    price_minor: int,
    r_declared: Fraction,
    r_true: Fraction,
    q_k: Fraction,
    d_k: Fraction,
    p: Fraction,
    x_minor: int | Fraction,
    f_minor: int | Fraction,
    l_minor: int | Fraction,
) -> Fraction:
    """Section 8.5 & 25.1: G_k(p, X) = (1 - q_k) * [ (1 - pi_k)*Delta_k + pi_k*(M_k - L_i) ], M_k = max(X - P*r(k), -F)."""
    one = Fraction(1, 1)
    p_frac = Fraction(price_minor)
    delta_k = p_frac * (r_declared - r_true)
    true_refund = p_frac * r_true
    pi_k = compute_pi(d_k, p)
    m_k = max(Fraction(x_minor) - true_refund, -Fraction(f_minor))
    return (one - q_k) * ((one - pi_k) * delta_k + pi_k * (m_k - Fraction(l_minor)))


def compute_x_max_k(
    *,
    price_minor: int,
    r_declared: Fraction,
    r_true: Fraction,
    d_k: Fraction,
    p: Fraction,
    l_minor: int,
    mu: Fraction,
) -> Fraction:
    """Section 8.5 & 25.1: X_max,k(p) = P*r(k) + L_i + Delta_k - (1 + mu)*Delta_k / pi_k(p)."""
    one = Fraction(1, 1)
    p_frac = Fraction(price_minor)
    delta_k = p_frac * (r_declared - r_true)
    pi_k = compute_pi(d_k, p)
    return p_frac * r_true + Fraction(l_minor) + delta_k - ((one + mu) * delta_k / pi_k)


def compute_legacy_v1_1_gain() -> tuple[Fraction, Fraction]:
    """Historical regression only (Section 25.1 Legacy row): v1.1 §8.4 G_C = -4.57, G_D = -25.43."""
    return Fraction(-457, 100), Fraction(-2543, 100)


def decide_release(
    inp: ReleaseInput,
    policy: PolicyConfig,
    calib: CalibrationInput,
) -> ReleaseDecision:
    """Section 8.6 ALGORITHM decide_release (v2.1)."""
    r_gd = policy.grade_fraction(inp.declared_grade)
    declared_refund_minor = floor_fraction_to_int(Fraction(inp.price_minor) * r_gd)
    adj_grade = ADJACENT_GRADE_BELOW.get(inp.declared_grade)
    if adj_grade is not None:
        r_adj = policy.grade_fraction(adj_grade)
        holdback_minor = max(0, ceil_fraction_to_int(Fraction(inp.price_minor) * (r_gd - r_adj)))
    else:
        holdback_minor = 0

    f_minor = policy.compute_f_minor(inp.price_minor)
    l_minor = policy.tier_l_minor(inp.tier)
    mu = policy.mu_fraction()
    p_std = policy.p_std_fraction()

    def _standard_decision(reason: str) -> ReleaseDecision:
        return ReleaseDecision(
            lane="STANDARD",
            timing="STANDARD",
            p=p_std,
            declared_refund_minor=declared_refund_minor,
            holdback_minor=holdback_minor,
            x_max_minor=0,
            x_released_minor=0,
            checkin_tranche_minor=0,
            f_minor=f_minor,
            l_minor=l_minor,
            binding_constraint=reason,
            worst_gross_gain_minor=Fraction(0),
            adjacent_leak_per_attempt_minor=Fraction(0),
            explanation="Your refund will be processed right after our receiving team checks the item in.",
        )

    # Step 1: RESTRICTED, intake exclusion, or re-filed after cancellation -> STANDARD (FR-88, INV-17)
    if inp.tier == "RESTRICTED" or inp.intake_excluded or inp.refiled_after_cancel:
        return _standard_decision("ROUTED_STANDARD_PRECHECK")

    # Step 2: FR-67 Non-serialized items capped at MID band for FAST eligibility
    band = policy.value_band(inp.price_minor)
    if inp.non_serialized and band == "HIGH":
        return _standard_decision("NON_SERIALIZED_HIGH_BAND_CAP")

    # Step 3: FR-74 NO_PASSPORT rules: FAST allowed only for TRUSTED x LOW with R1 timing
    if not inp.has_origin_passport:
        if inp.tier == "TRUSTED" and band == "LOW":
            forced_timing = "R1"
        else:
            return _standard_decision("NO_PASSPORT_STANDARD")
    else:
        forced_timing = None

    # Only include gross gaps that actually lie >= 2 grades below declared_grade
    grade_order = {"D": 0, "C": 1, "B": 2, "A": 3, "DEF": 4}
    gd_rank = grade_order.get(inp.declared_grade, 0)
    active_gross_gaps = [
        g for g in calib.gross_gaps if gd_rank - grade_order.get(g.true_grade, 0) >= 2
    ]

    gross_tuples: list[tuple[Fraction, Fraction]] = []
    for g in active_gross_gaps:
        r_k = policy.grade_fraction(g.true_grade)
        delta_k = Fraction(inp.price_minor) * (r_gd - r_k)
        gross_tuples.append((delta_k, g.d))

    adj_tuple: tuple[Fraction, Fraction, Fraction] | None = None
    if calib.adjacent_gap is not None and adj_grade is not None:
        r_a = policy.grade_fraction(adj_grade)
        delta_a = Fraction(inp.price_minor) * (r_gd - r_a)
        adj_tuple = (delta_a, calib.adjacent_gap.q, calib.adjacent_gap.d)

    p_chosen = solve_minimal_audit_probability(
        price_minor=inp.price_minor,
        gross_gaps=gross_tuples,
        adjacent_gap=adj_tuple,
        f_minor=f_minor,
        l_minor=l_minor,
        mu=mu,
        rho_stress=policy.rho_stress_fraction(),
        beta_leak=policy.beta_leak_fraction(),
        p_min=policy.p_min_fraction(),
        p_max=policy.p_max_fraction(),
    )
    if p_chosen is None:
        return _standard_decision("FLOOR_OR_LEAKAGE_INFEASIBLE")

    def _check_at_p(p_val: Fraction) -> bool:
        one = Fraction(1, 1)
        for delta_k, d_k in gross_tuples:
            pi_k = compute_pi(d_k, p_val)
            if pi_k * (delta_k + Fraction(f_minor) + Fraction(l_minor)) < (one + mu) * delta_k:
                return False
        if adj_tuple is not None:
            delta_a, q_a, d_a = adj_tuple
            leak = compute_adjacent_leak(q_a, d_a, p_val, delta_a)
            if policy.rho_stress_fraction() * leak > policy.beta_leak_fraction() * Fraction(inp.price_minor):
                return False
        return True

    timing = forced_timing or policy.select_timing(inp.tier, inp.price_minor, inp.drop_off_verified)
    if timing == "STANDARD":
        return _standard_decision("TIMING_MATRIX_STANDARD")

    max_declarable_pre_checkin = max(0, declared_refund_minor - holdback_minor)
    binding_label = "DECLARED_MINUS_HOLDBACK"
    x_max_frac = Fraction(max_declarable_pre_checkin)

    for g in active_gross_gaps:
        r_k = policy.grade_fraction(g.true_grade)
        cand = compute_x_max_k(
            price_minor=inp.price_minor,
            r_declared=r_gd,
            r_true=r_k,
            d_k=g.d,
            p=p_chosen,
            l_minor=l_minor,
            mu=mu,
        )
        if cand < x_max_frac:
            x_max_frac = cand
            binding_label = f"X_MAX_GAP_{g.true_grade}"

    x_max_minor = max(0, floor_fraction_to_int(x_max_frac))

    if timing != "R2":
        candidates = [
            (x_max_minor, binding_label),
            (max_declarable_pre_checkin, "DECLARED_MINUS_HOLDBACK"),
            (inp.account_cap_remaining_minor, "ACCOUNT_CAP"),
            (inp.merchant_cap_remaining_minor, "MERCHANT_AGGREGATE_CAP"),
        ]
        best_val, best_reason = min(candidates, key=lambda item: item[0])
        x_released_minor = max(0, best_val)
        binding_constraint = best_reason
        if x_released_minor == 0:
            timing = "R2"
            binding_constraint = "ZERO_X_TIGHTENED_TO_R2"
    else:
        x_released_minor = 0
        binding_constraint = "TIMING_R2"

    # Compute worst gross-gap expected gain at (p_chosen, x_released_minor)
    worst_g: Fraction | None = None
    for g in active_gross_gaps:
        r_k = policy.grade_fraction(g.true_grade)
        # Note: in Section 8.8 feasibility maps, when X_max binds, G_k is evaluated at X_max (or X=0 for R2)
        Fraction(0) if timing == "R2" else min(x_max_frac, Fraction(x_released_minor))
        # Use exact x_max_frac when X_MAX_GAP binds so -m_k (-$0.90 in E1) is exact, and integer minor unit otherwise
        if binding_constraint.startswith("X_MAX_GAP_"):
            x_eval: int | Fraction = x_max_frac
        else:
            x_eval = x_released_minor
        gain_k = compute_expected_gain(
            price_minor=inp.price_minor,
            r_declared=r_gd,
            r_true=r_k,
            q_k=g.q,
            d_k=g.d,
            p=p_chosen,
            x_minor=x_eval,
            f_minor=f_minor,
            l_minor=l_minor,
        )
        # MV-26 guard: also verify integer x_released_minor never violates safety condition
        gain_int = compute_expected_gain(
            price_minor=inp.price_minor,
            r_declared=r_gd,
            r_true=r_k,
            q_k=g.q,
            d_k=g.d,
            p=p_chosen,
            x_minor=x_released_minor,
            f_minor=f_minor,
            l_minor=l_minor,
        )
        delta_k = Fraction(inp.price_minor) * (r_gd - r_k)
        m_k = mu * (Fraction(1, 1) - g.q) * delta_k
        if gain_int > -m_k:
            return _standard_decision("MV26_SAFETY_GUARD_REJECTED")
        if worst_g is None or gain_k > worst_g:
            worst_g = gain_k

    adj_leak = Fraction(0)
    if adj_tuple is not None:
        delta_a, q_a, d_a = adj_tuple
        adj_leak = compute_adjacent_leak(q_a, d_a, p_chosen, delta_a)

    checkin_tranche_minor = max(0, declared_refund_minor - holdback_minor - x_released_minor)
    lane_name = "NO_PASSPORT" if not inp.has_origin_passport else "FAST"

    return ReleaseDecision(
        lane=lane_name,
        timing=timing,
        p=p_chosen,
        declared_refund_minor=declared_refund_minor,
        holdback_minor=holdback_minor,
        x_max_minor=x_max_minor,
        x_released_minor=x_released_minor,
        checkin_tranche_minor=checkin_tranche_minor,
        f_minor=f_minor,
        l_minor=l_minor,
        binding_constraint=binding_constraint,
        worst_gross_gain_minor=worst_g if worst_g is not None else Fraction(0),
        adjacent_leak_per_attempt_minor=adj_leak,
        explanation=(
            f"Initiating ${x_released_minor / 100:.2f} ({timing}); "
            f"${checkin_tranche_minor / 100:.2f} at check-in and ${holdback_minor / 100:.2f} holdback at settlement."
        ),
        _constraint_checker=_check_at_p,
    )


def apply_fallback_degradation(
    decision: ReleaseDecision,
    *,
    fb_code: str,
    price_minor: int,
    fallback_passed_gates: bool = False,
    low_max_minor: int = 15000,
) -> ReleaseDecision:
    """Section 31.3 & INV-18: Degraded modes never increase X or advance release timing."""
    if fb_code in {"FB-04", "FB-05", "FB-06", "FB-09", "FB-10"} or (
        fb_code == "FB-03" and not fallback_passed_gates
    ):
        return ReleaseDecision(
            lane="STANDARD",
            timing="STANDARD",
            p=decision.p,
            declared_refund_minor=decision.declared_refund_minor,
            holdback_minor=decision.holdback_minor,
            x_max_minor=0,
            x_released_minor=0,
            checkin_tranche_minor=0,
            f_minor=decision.f_minor,
            l_minor=decision.l_minor,
            binding_constraint=f"DEGRADED_{fb_code}",
            worst_gross_gain_minor=decision.worst_gross_gain_minor,
            adjacent_leak_per_attempt_minor=decision.adjacent_leak_per_attempt_minor,
            explanation=f"Degraded mode ({fb_code}): refund will be processed after warehouse check-in.",
        )

    if fb_code == "FB-07":
        # FB-07: Forensics detector unavailable -> X = 0 above LOW band; LOW band moves 1 timing step later (R0->R1->R2)
        if price_minor >= low_max_minor:
            new_timing = "R2" if decision.timing in {"R0", "R1", "R2"} else "STANDARD"
            return ReleaseDecision(
                lane=decision.lane,
                timing=new_timing,
                p=decision.p,
                declared_refund_minor=decision.declared_refund_minor,
                holdback_minor=decision.holdback_minor,
                x_max_minor=0,
                x_released_minor=0,
                checkin_tranche_minor=max(0, decision.declared_refund_minor - decision.holdback_minor),
                f_minor=decision.f_minor,
                l_minor=decision.l_minor,
                binding_constraint="DEGRADED_FB-07_ABOVE_LOW",
                worst_gross_gain_minor=decision.worst_gross_gain_minor,
                adjacent_leak_per_attempt_minor=decision.adjacent_leak_per_attempt_minor,
                explanation="Limited mode (FB-07): pre-check-in release deferred until check-in.",
            )
        step_later = {"R0": "R1", "R1": "R2", "R2": "R2", "STANDARD": "STANDARD"}[decision.timing]
        new_x = 0 if step_later in {"R2", "STANDARD"} else decision.x_released_minor
        return ReleaseDecision(
            lane=decision.lane,
            timing=step_later,
            p=decision.p,
            declared_refund_minor=decision.declared_refund_minor,
            holdback_minor=decision.holdback_minor,
            x_max_minor=decision.x_max_minor if new_x > 0 else 0,
            x_released_minor=new_x,
            checkin_tranche_minor=max(0, decision.declared_refund_minor - decision.holdback_minor - new_x),
            f_minor=decision.f_minor,
            l_minor=decision.l_minor,
            binding_constraint="DEGRADED_FB-07_LOW_STEP_LATER",
            worst_gross_gain_minor=decision.worst_gross_gain_minor,
            adjacent_leak_per_attempt_minor=decision.adjacent_leak_per_attempt_minor,
            explanation=f"Limited mode (FB-07): release timing shifted to {step_later}.",
        )

    # FB-01, FB-02, FB-08, or gated FB-03: preserve timing and X without ever increasing X or advancing timing
    return decision
