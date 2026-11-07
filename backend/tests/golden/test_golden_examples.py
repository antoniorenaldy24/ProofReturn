"""Golden tests for Honesty Mechanism v2.1 worked examples E1-E8, Legacy, and Feasibility Maps (Sections 8.8 & 25.1)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from backend.domain.policy import PolicyConfig
from backend.policy_engine.release import (
    CalibrationInput,
    GapCalibration,
    ReleaseInput,
    compute_expected_gain,
    compute_legacy_v1_1_gain,
    decide_release,
)
from sim.fmap import generate_feasibility_map, generate_sensitivity_table


def get_illustrative_calibration(declared_grade: str) -> CalibrationInput:
    """Section 8.8 illustrative (q, d) profile."""
    if declared_grade == "B":
        return CalibrationInput(
            declared_grade="B",
            adjacent_gap=GapCalibration(true_grade="C", q=Fraction(40, 100), d=Fraction(50, 100)),
            gross_gaps=[
                GapCalibration(true_grade="D", q=Fraction(90, 100), d=Fraction(95, 100)),
            ],
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
    raise ValueError(f"Unsupported declared grade in golden helper: {declared_grade}")


@pytest.mark.req("FR-21", "FR-58", "FR-87", "FR-89", "INV-14")
def test_golden_e1_trusted_r0_declared_b() -> None:
    """E1: P = $400, B, TRUSTED (L = $40), R0 -> p = 0.05, X = $221.57, H = $60, G_D = -$0.90, Leak = $17.10."""
    policy = PolicyConfig.default_us()
    calib = get_illustrative_calibration("B")
    inp = ReleaseInput(
        price_minor=40000,
        declared_grade="B",
        tier="TRUSTED",
        has_origin_passport=True,
        intake_excluded=False,
        refiled_after_cancel=False,
        account_cap_remaining_minor=100000,
        merchant_cap_remaining_minor=500000,
    )
    res = decide_release(inp, policy, calib)
    assert res.lane == "FAST"
    assert res.timing == "R0"
    assert res.p == Fraction(5, 100)
    assert res.holdback_minor == 6000
    assert res.x_released_minor == 22157
    assert res.checkin_tranche_minor == 9843
    assert res.x_released_minor + res.checkin_tranche_minor + res.holdback_minor == 38000
    assert round(float(res.worst_gross_gain_minor) / 100.0, 2) == -0.90
    assert round(float(res.adjacent_leak_per_attempt_minor) / 100.0, 2) == 17.10


@pytest.mark.req("FR-87", "FR-89")
def test_golden_e2_v12_bug_regression_rejected() -> None:
    """E2 (MV-26): P = $400, B, TRUSTED, X = $320 -> consistent G_D(0.05) = +$8.475 (+$8.47), G_D(1) = +$8.00 -> rejected."""
    calib = get_illustrative_calibration("B")
    gap_d = calib.gross_gaps[0]
    g_005 = compute_expected_gain(
        price_minor=40000,
        r_declared=Fraction(95, 100),
        r_true=Fraction(50, 100),
        q_k=gap_d.q,
        d_k=gap_d.d,
        p=Fraction(5, 100),
        x_minor=32000,
        f_minor=2000,
        l_minor=4000,
    )
    g_100 = compute_expected_gain(
        price_minor=40000,
        r_declared=Fraction(95, 100),
        r_true=Fraction(50, 100),
        q_k=gap_d.q,
        d_k=gap_d.d,
        p=Fraction(1, 1),
        x_minor=32000,
        f_minor=2000,
        l_minor=4000,
    )
    assert int(g_005) == 847  # +$8.475 -> $8.47 truncated / > 0
    assert float(g_005) / 100.0 == pytest.approx(8.475, abs=1e-3)
    assert float(g_100) / 100.0 == pytest.approx(8.00, abs=1e-6)


@pytest.mark.req("FR-21", "FR-58", "FR-87")
def test_golden_e3_new_r2_declared_b() -> None:
    """E3: P = $400, B, NEW (L = 0), R2 -> p = 0.05, X = 0, G_D = -$1.05."""
    policy = PolicyConfig.default_us()
    calib = get_illustrative_calibration("B")
    inp = ReleaseInput(
        price_minor=40000,
        declared_grade="B",
        tier="NEW",
        has_origin_passport=True,
    )
    res = decide_release(inp, policy, calib)
    assert res.lane == "FAST"
    assert res.timing == "R2"
    assert res.p == Fraction(5, 100)
    assert res.x_released_minor == 0
    assert float(res.worst_gross_gain_minor) / 100.0 == pytest.approx(-1.05, abs=1e-2)


@pytest.mark.req("FR-58", "FR-87", "FR-92")
def test_golden_e4_high_value_trusted_r1() -> None:
    """E4: P = $2,000, B, TRUSTED, R1, F = $100 -> X = $947.87, G_D = -$4.50."""
    policy = PolicyConfig.default_us()
    calib = get_illustrative_calibration("B")
    inp = ReleaseInput(
        price_minor=200000,
        declared_grade="B",
        tier="TRUSTED",
        has_origin_passport=True,
        account_cap_remaining_minor=100000,
        merchant_cap_remaining_minor=500000,
    )
    res = decide_release(inp, policy, calib)
    assert res.lane == "FAST"
    assert res.timing == "R1"
    assert res.f_minor == 10000
    assert res.x_released_minor == 94787
    assert float(res.worst_gross_gain_minor) / 100.0 == pytest.approx(-4.50, abs=1e-2)


@pytest.mark.req("FR-60", "FR-84", "INV-11")
def test_golden_e5_eu_new_infeasible_routes_standard() -> None:
    """E5: P = $400, B, NEW, EU (F = 0) -> Floor pi >= 1.05 infeasible -> STANDARD."""
    policy = PolicyConfig.default_eu()
    calib = get_illustrative_calibration("B")
    inp = ReleaseInput(
        price_minor=40000,
        declared_grade="B",
        tier="NEW",
        has_origin_passport=True,
    )
    res = decide_release(inp, policy, calib)
    assert res.lane == "STANDARD"
    assert res.x_released_minor == 0
    assert res.p == Fraction(25, 100)


@pytest.mark.req("FR-58", "FR-87")
def test_golden_e6_declared_a_trusted_r0() -> None:
    """E6: P = $400, A, TRUSTED, R0 -> X = $225.93 (binding gap D), H = $20, worst G = -$0.50."""
    policy = PolicyConfig.default_us()
    calib = get_illustrative_calibration("A")
    inp = ReleaseInput(
        price_minor=40000,
        declared_grade="A",
        tier="TRUSTED",
        has_origin_passport=True,
        account_cap_remaining_minor=100000,
        merchant_cap_remaining_minor=500000,
    )
    res = decide_release(inp, policy, calib)
    assert res.lane == "FAST"
    assert res.timing == "R0"
    assert res.holdback_minor == 2000
    assert res.x_released_minor == 22593
    assert res.binding_constraint == "X_MAX_GAP_D"
    assert float(res.worst_gross_gain_minor) / 100.0 == pytest.approx(-0.50, abs=1e-2)


@pytest.mark.req("FR-21", "FR-58")
def test_golden_e7_declared_a_new_r2() -> None:
    """E7: P = $300, A, NEW, R2 -> Floor on gap C requires p = 0.20; X = 0; worst G = -$0.62."""
    policy = PolicyConfig.default_us()
    calib = get_illustrative_calibration("A")
    inp = ReleaseInput(
        price_minor=30000,
        declared_grade="A",
        tier="NEW",
        has_origin_passport=True,
    )
    res = decide_release(inp, policy, calib)
    assert res.lane == "FAST"
    assert res.timing == "R2"
    assert res.p == Fraction(20, 100)
    assert res.x_released_minor == 0
    assert round(float(res.worst_gross_gain_minor) / 100.0, 2) == -0.62


@pytest.mark.req("FR-60", "FR-100")
def test_golden_e8_low_data_profile_routes_standard() -> None:
    """E8: E1 with d_D = 0.22 -> Floor requires p approx 0.73 > p_max -> STANDARD."""
    policy = PolicyConfig.default_us()
    calib = CalibrationInput(
        declared_grade="B",
        adjacent_gap=GapCalibration(true_grade="C", q=Fraction(40, 100), d=Fraction(50, 100)),
        gross_gaps=[
            GapCalibration(true_grade="D", q=Fraction(90, 100), d=Fraction(22, 100)),
        ],
    )
    inp = ReleaseInput(
        price_minor=40000,
        declared_grade="B",
        tier="TRUSTED",
        has_origin_passport=True,
    )
    res = decide_release(inp, policy, calib)
    assert res.lane == "STANDARD"
    assert res.x_released_minor == 0


def test_golden_legacy_v1_1_regression() -> None:
    """Legacy row in Section 25.1: v1.1 §8.4 inputs (H = 38, L = 40, F = 0, p = 0.05) -> G_C = -4.57, G_D = -25.43."""
    g_c, g_d = compute_legacy_v1_1_gain()
    assert round(float(g_c), 2) == -4.57
    assert round(float(g_d), 2) == -25.43


@pytest.mark.req("FR-79", "FR-101")
def test_golden_feasibility_maps_declared_b_and_a() -> None:
    """Reproduce all 15 rows of Feasibility Map B and 15 rows of Feasibility Map A in Section 8.8."""
    map_b = generate_feasibility_map("B")
    assert len(map_b) == 15
    # Verify key rows in Map B
    by_key_b = {(r["price_usd"], r["tier"]): r for r in map_b}
    assert by_key_b[(100, "ESTABLISHED")]["x_released_usd"] == pytest.approx(65.39, abs=1e-2)
    assert by_key_b[(100, "TRUSTED")]["x_released_usd"] == pytest.approx(80.00, abs=1e-2)
    assert by_key_b[(300, "ESTABLISHED")]["x_released_usd"] == pytest.approx(156.18, abs=1e-2)
    assert by_key_b[(400, "TRUSTED")]["x_released_usd"] == pytest.approx(221.57, abs=1e-2)
    assert by_key_b[(800, "TRUSTED")]["x_released_usd"] == pytest.approx(403.14, abs=1e-2)
    assert by_key_b[(2000, "TRUSTED")]["x_released_usd"] == pytest.approx(947.87, abs=1e-2)

    map_a = generate_feasibility_map("A")
    assert len(map_a) == 15
    by_key_a = {(r["price_usd"], r["tier"]): r for r in map_a}
    assert by_key_a[(100, "ESTABLISHED")]["x_released_usd"] == pytest.approx(66.48, abs=1e-2)
    assert by_key_a[(100, "TRUSTED")]["x_released_usd"] == pytest.approx(86.48, abs=1e-2)
    assert by_key_a[(300, "NEW")]["p"] == pytest.approx(0.20, abs=1e-3)
    assert by_key_a[(400, "TRUSTED")]["x_released_usd"] == pytest.approx(225.93, abs=1e-2)
    assert by_key_a[(800, "TRUSTED")]["x_released_usd"] == pytest.approx(411.86, abs=1e-2)
    assert by_key_a[(2000, "TRUSTED")]["x_released_usd"] == pytest.approx(969.66, abs=1e-2)

    sens = generate_sensitivity_table()
    assert sens[0.95]["x_released_usd"] == pytest.approx(221.57, abs=1e-2)
    assert sens[0.90]["x_released_usd"] == pytest.approx(211.16, abs=1e-2)
    assert sens[0.80]["x_released_usd"] == pytest.approx(186.66, abs=1e-2)
    assert sens[0.70]["lane"] == "STANDARD"
    assert sens[0.50]["lane"] == "STANDARD"
    assert sens[0.22]["lane"] == "STANDARD"
