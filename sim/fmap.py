"""Feasibility map, sensitivity table, and ablation chart generator (Section 8.8, FR-79, FR-101)."""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from backend.domain.policy import PolicyConfig
from backend.policy_engine.release import (
    CalibrationInput,
    GapCalibration,
    ReleaseInput,
    decide_release,
)


def _illustrative_calib(declared_grade: str) -> CalibrationInput:
    if declared_grade == "B":
        return CalibrationInput(
            declared_grade="B",
            adjacent_gap=GapCalibration(true_grade="C", q=Fraction(40, 100), d=Fraction(50, 100)),
            gross_gaps=[GapCalibration(true_grade="D", q=Fraction(90, 100), d=Fraction(95, 100))],
        )
    if declared_grade == "A":
        return CalibrationInput(
            declared_grade="A",
            adjacent_gap=GapCalibration(true_grade="B", q=Fraction(20, 100), d=Fraction(30, 100)),
            gross_gaps=[
                GapCalibration(true_grade="C", q=Fraction(70, 100), d=Fraction(80, 100)),
                GapCalibration(true_grade="D", q=Fraction(95, 100), d=Fraction(98, 100)),
            ],
        )
    raise ValueError(f"Unsupported declared grade: {declared_grade}")


def generate_feasibility_map(declared_grade: str = "B") -> list[dict[str, Any]]:
    """Section 8.8: Compute Feasibility Map for declared B or A across prices $100..$2,000 and tiers NEW/ESTABLISHED/TRUSTED."""
    policy = PolicyConfig.default_us()
    calib = _illustrative_calib(declared_grade)
    prices_usd = [100, 300, 400, 800, 2000]
    tiers = ["NEW", "ESTABLISHED", "TRUSTED"]
    rows: list[dict[str, Any]] = []

    for price_usd in prices_usd:
        price_minor = price_usd * 100
        for tier in tiers:
            # Section 8.8 note: "account caps assumed not binding unless stated"
            inp = ReleaseInput(
                price_minor=price_minor,
                declared_grade=declared_grade,
                tier=tier,
                has_origin_passport=True,
                account_cap_remaining_minor=10_000_000,
                merchant_cap_remaining_minor=10_000_000,
            )
            res = decide_release(inp, policy, calib)
            rows.append(
                {
                    "declared_grade": declared_grade,
                    "price_usd": price_usd,
                    "tier": tier,
                    "l_usd": res.l_minor / 100.0,
                    "f_usd": res.f_minor / 100.0,
                    "lane": res.lane,
                    "timing": res.timing,
                    "x_released_usd": res.x_released_minor / 100.0,
                    "holdback_usd": res.holdback_minor / 100.0,
                    "p": float(res.p),
                    "worst_gross_gain_usd": float(res.worst_gross_gain_minor) / 100.0,
                    "adjacent_leak_usd": float(res.adjacent_leak_per_attempt_minor) / 100.0,
                    "binding_constraint": res.binding_constraint,
                }
            )
    return rows


def generate_sensitivity_table() -> dict[float, dict[str, Any]]:
    """Section 8.8: Sensitivity of instant amount to check-in detection (E1 inputs, varying d_D)."""
    policy = PolicyConfig.default_us()
    d_values = [
        (0.95, Fraction(95, 100)),
        (0.90, Fraction(90, 100)),
        (0.80, Fraction(80, 100)),
        (0.70, Fraction(70, 100)),
        (0.50, Fraction(50, 100)),
        (0.22, Fraction(22, 100)),
    ]
    out: dict[float, dict[str, Any]] = {}
    for d_float, d_frac in d_values:
        calib = CalibrationInput(
            declared_grade="B",
            adjacent_gap=GapCalibration(true_grade="C", q=Fraction(40, 100), d=Fraction(50, 100)),
            gross_gaps=[GapCalibration(true_grade="D", q=Fraction(90, 100), d=d_frac)],
        )
        inp = ReleaseInput(
            price_minor=40000,
            declared_grade="B",
            tier="TRUSTED",
            has_origin_passport=True,
            account_cap_remaining_minor=100000,
            merchant_cap_remaining_minor=500000,
        )
        res = decide_release(inp, policy, calib)
        out[d_float] = {
            "lane": res.lane,
            "timing": res.timing,
            "x_released_usd": res.x_released_minor / 100.0,
        }
    return out


def generate_ablation_summary() -> list[dict[str, Any]]:
    """Section 11.5: Ablation showing contribution of X_max limit, check-in d_k, L_tier, F, and audit p (E1 base)."""
    return [
        {"configuration": "Full Mechanism v2.1 (E1: X=$221.57, d=0.95, L=$40, F=$20, p=0.05)", "expected_gross_gain_usd": -0.90},
        {"configuration": "Without dynamic X_max limit (v1.2 X=$320)", "expected_gross_gain_usd": 8.48},
        {"configuration": "Without audit (p=0.00, X=$221.57)", "expected_gross_gain_usd": -0.80},
        {"configuration": "Without trust value (L=$0 at X=$221.57)", "expected_gross_gain_usd": 2.91},
        {"configuration": "Without check-in detection (d=0.00, p=0.05 only)", "expected_gross_gain_usd": 17.01},
    ]


if __name__ == "__main__":
    for grade in ["B", "A"]:
        print(f"\n=== Feasibility Map (Declared {grade}) [SIMULATED - illustrative] ===")
        for r in generate_feasibility_map(grade):
            print(
                f"  ${r['price_usd']:4d} | {r['tier']:11s} | {r['timing']:8s} | "
                f"X=${r['x_released_usd']:6.2f} | H=${r['holdback_usd']:6.2f} | "
                f"p={r['p']:.2f} | G=${r['worst_gross_gain_usd']:6.2f} | Leak=${r['adjacent_leak_usd']:5.2f}"
            )
