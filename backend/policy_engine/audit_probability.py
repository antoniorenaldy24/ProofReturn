"""Minimal audit probability solver under gross-gap floor and adjacent-leakage constraints (Section 8.5 & 8.6, FR-21)."""

from __future__ import annotations

from fractions import Fraction


def compute_pi(d_k: Fraction, p: Fraction) -> Fraction:
    """Post-payment exclusion probability: pi_k(p) = 1 - (1 - d_k)*(1 - p)."""
    return Fraction(1, 1) - (Fraction(1, 1) - d_k) * (Fraction(1, 1) - p)


def compute_adjacent_leak(
    q_a: Fraction,
    d_a: Fraction,
    p: Fraction,
    delta_a_minor: Fraction,
) -> Fraction:
    """Section 8.5: Leak(p) = (1 - q_a) * (1 - pi_a(p)) * Delta_a (since X <= P*r(g_d) - H)."""
    pi_a = compute_pi(d_a, p)
    return (Fraction(1, 1) - q_a) * (Fraction(1, 1) - pi_a) * delta_a_minor


def solve_minimal_audit_probability(
    *,
    price_minor: int,
    gross_gaps: list[tuple[Fraction, Fraction]],  # list of (delta_k_minor, d_k)
    adjacent_gap: tuple[Fraction, Fraction, Fraction] | None,  # (delta_a_minor, q_a, d_a)
    f_minor: int,
    l_minor: int,
    mu: Fraction,
    rho_stress: Fraction,
    beta_leak: Fraction,
    p_min: Fraction,
    p_max: Fraction,
) -> Fraction | None:
    """FR-21 & Section 8.6: Find smallest p in [p_min, p_max] satisfying all gross floors and adjacent budget."""
    req_p = p_min
    one = Fraction(1, 1)

    for delta_k, d_k in gross_gaps:
        if delta_k <= 0:
            continue
        denom = delta_k + Fraction(f_minor) + Fraction(l_minor)
        if denom <= 0:
            return None
        target_pi = (one + mu) * delta_k / denom
        if target_pi > one:
            return None
        if target_pi > d_k:
            if d_k >= one:
                return None
            p_k = (target_pi - d_k) / (one - d_k)
            req_p = max(req_p, p_k)

    if adjacent_gap is not None:
        delta_a, q_a, d_a = adjacent_gap
        if delta_a > 0:
            # rho_stress * (1 - q_a) * (1 - d_a) * (1 - p) * delta_a <= beta_leak * P
            coeff = rho_stress * (one - q_a) * (one - d_a) * delta_a
            budget = beta_leak * Fraction(price_minor)
            if coeff > budget:
                if coeff <= 0:
                    return None
                p_leak = one - (budget / coeff)
                req_p = max(req_p, p_leak)

    if req_p > p_max:
        return None
    return req_p
