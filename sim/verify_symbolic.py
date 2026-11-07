"""Symbolic derivation verification of Honesty Mechanism v2.1 using SymPy (MV-11, Section 8.5 & 25.1)."""

from __future__ import annotations

import sympy as sp


def verify_all_symbolic_identities() -> bool:
    """MV-11: Derive G_k, the relative-margin safety condition, the floor condition, and X_max from the settlement payoff tree."""
    P, r_d, r_k, q_k, d_k, p, X, F, L_i, mu = sp.symbols(
        "P r_d r_k q_k d_k p X F L_i mu", real=True, positive=True
    )
    Delta_k = P * (r_d - r_k)
    pi_k = 1 - (1 - d_k) * (1 - p)

    # 1. Settlement payoff tree under routing semantics (Section 8.4 & 8.5):
    # - Truthful payoff: P * r_k
    # - Overclaim caught at intake (prob q_k): routed to STANDARD -> shopper cancels freely -> payoff P * r_k (gain 0)
    # - Overclaim passes intake (prob 1 - q_k):
    #     - Not excluded at check-in or audit (prob 1 - pi_k): receives P * r_d -> gain = P * r_d - P * r_k = Delta_k
    #     - Excluded at check-in or audit (prob pi_k): receives X (when X >= P*r_k - F), loses L_i -> gain = M_k - L_i
    M_k = sp.Symbol("M_k", real=True)
    payoff_truthful = P * r_k
    payoff_overclaim = (
        q_k * (P * r_k)
        + (1 - q_k) * ((1 - pi_k) * (P * r_d) + pi_k * (P * r_k + M_k - L_i))
    )
    G_k_tree = sp.simplify(payoff_overclaim - payoff_truthful)
    G_k_canonical = (1 - q_k) * ((1 - pi_k) * Delta_k + pi_k * (M_k - L_i))

    if sp.simplify(G_k_tree - G_k_canonical) != 0:
        return False

    # 2. Relative safety margin m_k = mu * (1 - q_k) * Delta_k:
    # Condition G_k <= -m_k  <=>  G_k + m_k <= 0
    m_k = mu * (1 - q_k) * Delta_k
    lhs_minus_rhs = sp.simplify((G_k_canonical + m_k) / (1 - q_k))
    # Should equal (1 + mu)*Delta_k - pi_k*(Delta_k - M_k + L_i)
    expected_ineq_term = (1 + mu) * Delta_k - pi_k * (Delta_k - M_k + L_i)
    if sp.simplify(lhs_minus_rhs - expected_ineq_term) != 0:
        return False

    # 3. Floor condition when M_k = -F (i.e., X <= P * r_k - F):
    floor_term = expected_ineq_term.subs(M_k, -F)
    expected_floor = (1 + mu) * Delta_k - pi_k * (Delta_k + F + L_i)
    if sp.simplify(floor_term - expected_floor) != 0:
        return False

    # 4. Solve for X_max when M_k = X - P * r_k (at boundary G_k = -m_k):
    eq_boundary = sp.Eq(expected_ineq_term.subs(M_k, X - P * r_k), 0)
    sol_X = sp.solve(eq_boundary, X)[0]
    expected_X_max = P * r_k + L_i + Delta_k - (1 + mu) * Delta_k / pi_k
    return sp.simplify(sol_X - expected_X_max) == 0


if __name__ == "__main__":
    ok = verify_all_symbolic_identities()
    print(f"Symbolic verification MV-11: {'PASSED' if ok else 'FAILED'}")
    raise SystemExit(0 if ok else 1)
