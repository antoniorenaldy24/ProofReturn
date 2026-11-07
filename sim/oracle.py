"""Independent brute-force oracle for MV-10 (Section 25.2 & 25.3).

Rule (Section 25.3): Must NOT import the closed-form solver in backend.policy_engine.
Searches over p (step 1e-4) and X (step $0.01 / 1 minor unit) directly from the payoff definition.
"""

from __future__ import annotations

from typing import Any

CURVE = {"A": 1.00, "B": 0.95, "C": 0.80, "D": 0.50}
ADJ_MAP = {"A": "B", "B": "C", "C": "D", "D": None}
TIER_L_MINOR = {"NEW": 0, "ESTABLISHED": 2000, "TRUSTED": 4000, "RESTRICTED": 0}
TIMING_MATRIX = {
    "TRUSTED": {"LOW": "R0", "MID": "R0", "HIGH": "R1"},
    "ESTABLISHED": {"LOW": "R0", "MID": "R1", "HIGH": "R2"},
    "NEW": {"LOW": "R2", "MID": "R2", "HIGH": "R2"},
    "RESTRICTED": {"LOW": "STANDARD", "MID": "STANDARD", "HIGH": "STANDARD"},
}


def brute_force_decide_release(
    *,
    price_minor: int,
    declared_grade: str,
    tier: str,
    calib: Any,
    account_cap_minor: int = 100000,
    merchant_cap_minor: int = 500000,
    mu: float = 0.05,
    rho_stress: float = 0.30,
    beta_leak: float = 0.02,
    p_min: float = 0.05,
    p_max: float = 0.25,
) -> dict[str, Any]:
    """MV-10: Brute-force grid search over p (step 1e-4) and X (step $0.01 = 1 minor unit)."""
    if tier == "RESTRICTED":
        return {"lane": "STANDARD", "p": 0.25, "x_released_minor": 0}

    r_gd = CURVE[declared_grade]
    adj_g = ADJ_MAP[declared_grade]
    r_adj = CURVE[adj_g] if adj_g else r_gd
    declared_refund_minor = round(price_minor * r_gd)
    holdback_minor = round(price_minor * (r_gd - r_adj))
    f_minor = max(1200, round(0.05 * price_minor))
    l_minor = TIER_L_MINOR[tier]

    # Step 1: Brute-force search p in [0.0500, 0.2500] with step 1e-4
    chosen_p: float | None = None
    for p_step in range(round(p_min * 10000), round(p_max * 10000) + 1):
        p = p_step / 10000.0
        ok = True
        # Check floor condition at X = 0 (where M_k = -F) for every gross gap
        for g in calib.gross_gaps:
            r_k = CURVE[g.true_grade]
            delta_k = price_minor * (r_gd - r_k)
            q_k = float(g.q)
            d_k = float(g.d)
            pi_k = 1.0 - (1.0 - d_k) * (1.0 - p)
            m_k_floor = -float(f_minor)
            gain_floor = (1.0 - q_k) * ((1.0 - pi_k) * delta_k + pi_k * (m_k_floor - l_minor))
            margin_k = mu * (1.0 - q_k) * delta_k
            if gain_floor > -margin_k + 1e-7:
                ok = False
                break
        if not ok:
            continue

        # Check adjacent leakage budget
        if calib.adjacent_gap is not None and adj_g is not None:
            q_a = float(calib.adjacent_gap.q)
            d_a = float(calib.adjacent_gap.d)
            pi_a = 1.0 - (1.0 - d_a) * (1.0 - p)
            delta_a = price_minor * (r_gd - r_adj)
            leak = (1.0 - q_a) * (1.0 - pi_a) * delta_a
            if rho_stress * leak > beta_leak * price_minor + 1e-7:
                continue

        chosen_p = p
        break

    if chosen_p is None:
        return {"lane": "STANDARD", "p": 0.25, "x_released_minor": 0}

    band = "LOW" if price_minor < 15000 else ("MID" if price_minor <= 60000 else "HIGH")
    timing = TIMING_MATRIX[tier][band]
    if timing == "R2":
        return {"lane": "FAST", "timing": "R2", "p": chosen_p, "x_released_minor": 0}

    # Step 2: Brute-force search largest integer X (step 1 minor unit = $0.01) up to upper cap
    upper_x = min(declared_refund_minor - holdback_minor, account_cap_minor, merchant_cap_minor)
    best_x = 0
    for x_cand in range(upper_x, -1, -1):
        safe = True
        for g in calib.gross_gaps:
            r_k = CURVE[g.true_grade]
            true_refund = price_minor * r_k
            delta_k = price_minor * (r_gd - r_k)
            q_k = float(g.q)
            d_k = float(g.d)
            pi_k = 1.0 - (1.0 - d_k) * (1.0 - chosen_p)
            m_k = max(float(x_cand) - true_refund, -float(f_minor))
            gain = (1.0 - q_k) * ((1.0 - pi_k) * delta_k + pi_k * (m_k - l_minor))
            margin_k = mu * (1.0 - q_k) * delta_k
            if gain > -margin_k + 1e-6:
                safe = False
                break
        if safe:
            best_x = x_cand
            break

    return {
        "lane": "FAST",
        "timing": "R2" if best_x == 0 else timing,
        "p": chosen_p,
        "x_released_minor": best_x,
    }
