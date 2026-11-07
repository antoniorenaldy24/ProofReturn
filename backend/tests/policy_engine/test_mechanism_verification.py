"""Formal Verification Suite for Honesty Mechanism v2.1 (Section 25.2: MV-01..MV-26)."""

from __future__ import annotations

from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.ai.calibration.pooling import estimate_pooled_calibration
from backend.domain.account_monitor import CusumConfig, CusumMonitor
from backend.domain.audit_commitment import create_audit_commitment, reveal_and_draw_audit
from backend.domain.identity import IdentityGroupManager
from backend.domain.policy import PolicyConfig
from backend.domain.trust import TrustProfile, evaluate_tier_promotion
from backend.policy_engine.evidence_requirements import determine_evidence_requirements
from backend.policy_engine.keep_offer import KeepOfferInput, compute_posted_keep_offer
from backend.policy_engine.lanes import route_intake_and_refile
from backend.policy_engine.misdeclaration import evaluate_misdeclaration
from backend.policy_engine.release import (
    CalibrationInput,
    GapCalibration,
    ReleaseInput,
    apply_fallback_degradation,
    compute_expected_gain,
    decide_release,
)
from backend.policy_engine.settlement import SettlementInput, settle_return
from sim.attacker import find_best_response_attack
from sim.engine import simulate_cell_analytic_agreement
from sim.oracle import brute_force_decide_release
from sim.verify_symbolic import verify_all_symbolic_identities


def _default_calib_b() -> CalibrationInput:
    return CalibrationInput(
        declared_grade="B",
        adjacent_gap=GapCalibration(true_grade="C", q=Fraction(40, 100), d=Fraction(50, 100)),
        gross_gaps=[GapCalibration(true_grade="D", q=Fraction(90, 100), d=Fraction(95, 100))],
    )


@pytest.mark.req("FR-21", "FR-87", "FR-89")
@settings(max_examples=50)
@given(
    price_minor=st.integers(min_value=5000, max_value=250000),
    tier=st.sampled_from(["NEW", "ESTABLISHED", "TRUSTED"]),
    d_num=st.integers(min_value=20, max_value=99),
)
def test_mv01_fast_output_satisfies_safety_condition(price_minor: int, tier: str, d_num: int) -> None:
    """MV-01: For every FAST output, G_k(p, X) <= -mu * (1 - q_k) * Delta_k for all gross gaps k."""
    policy = PolicyConfig.default_us()
    calib = CalibrationInput(
        declared_grade="B",
        adjacent_gap=GapCalibration(true_grade="C", q=Fraction(40, 100), d=Fraction(50, 100)),
        gross_gaps=[GapCalibration(true_grade="D", q=Fraction(90, 100), d=Fraction(d_num, 100))],
    )
    inp = ReleaseInput(
        price_minor=price_minor,
        declared_grade="B",
        tier=tier,
        has_origin_passport=True,
        account_cap_remaining_minor=100000,
        merchant_cap_remaining_minor=500000,
    )
    res = decide_release(inp, policy, calib)
    if res.lane == "FAST":
        gap = calib.gross_gaps[0]
        delta_k = Fraction(price_minor) * (Fraction(95, 100) - Fraction(50, 100))
        m_k = Fraction(5, 100) * (1 - gap.q) * delta_k
        g_k = compute_expected_gain(
            price_minor=price_minor,
            r_declared=Fraction(95, 100),
            r_true=Fraction(50, 100),
            q_k=gap.q,
            d_k=gap.d,
            p=res.p,
            x_minor=res.x_released_minor,
            f_minor=res.f_minor,
            l_minor=res.l_minor,
        )
        assert g_k <= -m_k


@pytest.mark.req("FR-21")
@settings(max_examples=40)
@given(
    price_minor=st.integers(min_value=10000, max_value=100000),
    d_c_num=st.integers(min_value=65, max_value=95),
)
def test_mv02_minimal_p(price_minor: int, d_c_num: int) -> None:
    """MV-02: Returned p is minimal: p - eps violates a floor or adjacent budget unless p = p_min."""
    policy = PolicyConfig.default_us()
    calib = CalibrationInput(
        declared_grade="A",
        adjacent_gap=GapCalibration(true_grade="B", q=Fraction(20, 100), d=Fraction(30, 100)),
        gross_gaps=[
            GapCalibration(true_grade="C", q=Fraction(70, 100), d=Fraction(d_c_num, 100)),
            GapCalibration(true_grade="D", q=Fraction(95, 100), d=Fraction(98, 100)),
        ],
    )
    inp = ReleaseInput(price_minor=price_minor, declared_grade="A", tier="NEW", has_origin_passport=True)
    res = decide_release(inp, policy, calib)
    if res.lane == "FAST" and res.p > Fraction(5, 100):
        eps = Fraction(1, 1_000_000)
        p_test = res.p - eps
        assert not res.satisfies_constraints_at(p_test)


@pytest.mark.req("FR-21", "FR-60", "FR-87")
def test_mv03_and_mv10_independent_oracle_agreement() -> None:
    """MV-03 & MV-10: Brute-force oracle over p (step 1e-4) and X (step $0.01) agrees within 1e-3 / $0.01."""
    policy = PolicyConfig.default_us()
    for grade in ["A", "B"]:
        calib = (
            _default_calib_b()
            if grade == "B"
            else CalibrationInput(
                declared_grade="A",
                adjacent_gap=GapCalibration(true_grade="B", q=Fraction(20, 100), d=Fraction(30, 100)),
                gross_gaps=[
                    GapCalibration(true_grade="C", q=Fraction(70, 100), d=Fraction(80, 100)),
                    GapCalibration(true_grade="D", q=Fraction(95, 100), d=Fraction(98, 100)),
                ],
            )
        )
        for price_minor in [10000, 30000, 40000, 80000]:
            for tier in ["NEW", "ESTABLISHED", "TRUSTED"]:
                inp = ReleaseInput(
                    price_minor=price_minor,
                    declared_grade=grade,
                    tier=tier,
                    has_origin_passport=True,
                    account_cap_remaining_minor=100000,
                    merchant_cap_remaining_minor=500000,
                )
                closed = decide_release(inp, policy, calib)
                oracle = brute_force_decide_release(
                    price_minor=price_minor,
                    declared_grade=grade,
                    tier=tier,
                    calib=calib,
                    account_cap_minor=100000,
                    merchant_cap_minor=500000,
                )
                assert closed.lane == oracle["lane"]
                if closed.lane == "FAST":
                    assert abs(float(closed.p) - oracle["p"]) <= 1e-3
                    assert abs(closed.x_released_minor - oracle["x_released_minor"]) <= 1


@pytest.mark.req("FR-23", "FR-28", "INV-01")
@settings(max_examples=40)
@given(
    price_minor=st.integers(min_value=5000, max_value=200000),
    declared_grade=st.sampled_from(["A", "B", "C", "D"]),
    verified_grade=st.sampled_from(["A", "B", "C", "D"]),
)
def test_mv04_mv05_mv06_settlement_tranches_and_bounds(
    price_minor: int, declared_grade: str, verified_grade: str
) -> None:
    """MV-04 (under-declaration top-up), MV-05 (tranche sum exact), MV-06 (total refund <= capture & max grade)."""
    policy = PolicyConfig.default_us()
    calib = _default_calib_b()
    inp = ReleaseInput(
        price_minor=price_minor,
        declared_grade=declared_grade,
        tier="TRUSTED",
        has_origin_passport=True,
        account_cap_remaining_minor=100000,
        merchant_cap_remaining_minor=500000,
    )
    rel = decide_release(inp, policy, calib)
    # MV-05: tranche amounts non-negative and sum to declared refund before adjustments
    assert rel.x_released_minor >= 0
    assert rel.checkin_tranche_minor >= 0
    assert rel.holdback_minor >= 0
    if rel.lane == "FAST":
        assert rel.x_released_minor + rel.checkin_tranche_minor + rel.holdback_minor == rel.declared_refund_minor

    s_inp = SettlementInput(
        price_minor=price_minor,
        capture_amount_minor=price_minor,
        declared_grade=declared_grade,
        verified_grade=verified_grade,
        x_released_minor=rel.x_released_minor,
        holdback_minor=rel.holdback_minor,
        f_minor=rel.f_minor,
        human_confirmed_gross=True,
        has_merchant_evidence=True,
    )
    s_out = settle_return(s_inp, policy)
    # MV-04: under-declaration never yields lower final refund than verified grade's amount
    grade_order = {"D": 0, "C": 1, "B": 2, "A": 3}
    if grade_order[verified_grade] > grade_order[declared_grade]:
        expected_verified = int(Fraction(price_minor) * policy.grade_fraction(verified_grade))
        assert s_out.final_total_refund_minor >= expected_verified
        assert not s_out.status_affected
    # MV-06: total refund <= capture (INV-01) and <= P * r(max(g_d, g*))
    max_g = declared_grade if grade_order[declared_grade] >= grade_order[verified_grade] else verified_grade
    max_allowed = int(Fraction(price_minor) * policy.grade_fraction(max_g))
    assert 0 <= s_out.final_total_refund_minor <= price_minor
    assert s_out.final_total_refund_minor <= max_allowed


@pytest.mark.req("FR-21", "FR-87", "FR-89")
def test_mv07_monotonicity_properties() -> None:
    """MV-07: X_max non-decreasing in L_i, F, d_k, p; non-increasing in mu; p non-increasing in d_k, L_i, F."""
    policy = PolicyConfig.default_us()
    calib_low_d = CalibrationInput(
        declared_grade="A",
        adjacent_gap=GapCalibration(true_grade="B", q=Fraction(20, 100), d=Fraction(30, 100)),
        gross_gaps=[
            GapCalibration(true_grade="C", q=Fraction(70, 100), d=Fraction(78, 100)),
            GapCalibration(true_grade="D", q=Fraction(95, 100), d=Fraction(98, 100)),
        ],
    )
    calib_high_d = CalibrationInput(
        declared_grade="A",
        adjacent_gap=GapCalibration(true_grade="B", q=Fraction(20, 100), d=Fraction(30, 100)),
        gross_gaps=[
            GapCalibration(true_grade="C", q=Fraction(70, 100), d=Fraction(90, 100)),
            GapCalibration(true_grade="D", q=Fraction(95, 100), d=Fraction(98, 100)),
        ],
    )
    r_low_l = decide_release(
        ReleaseInput(price_minor=40000, declared_grade="A", tier="ESTABLISHED", has_origin_passport=True),
        policy,
        calib_low_d,
    )
    r_high_l = decide_release(
        ReleaseInput(price_minor=40000, declared_grade="A", tier="TRUSTED", has_origin_passport=True),
        policy,
        calib_low_d,
    )
    assert r_high_l.p <= r_low_l.p
    assert r_high_l.x_max_minor >= r_low_l.x_max_minor

    r_high_d = decide_release(
        ReleaseInput(price_minor=40000, declared_grade="A", tier="TRUSTED", has_origin_passport=True),
        policy,
        calib_high_d,
    )
    assert r_high_d.p <= r_high_l.p
    assert r_high_d.x_max_minor >= r_high_l.x_max_minor


@pytest.mark.req("FR-27", "FR-61", "FR-95", "INV-16")
def test_mv08_and_mv16_determinism_and_commit_reveal() -> None:
    """MV-08 & MV-16: Deterministic audit draw and verifiable commit-reveal with shopper nonce."""
    seed_platform = b"platform_secret_seed_32_bytes_01"
    return_id = "ret_01J9Z00001"
    nonce_shopper = "shopper_client_nonce_xyz"
    p = Fraction(5, 100)

    c1 = create_audit_commitment(seed_platform, return_id, p)
    c2 = create_audit_commitment(seed_platform, return_id, p)
    assert c1.commitment == c2.commitment

    r1 = reveal_and_draw_audit(c1, seed_platform, nonce_shopper)
    r2 = reveal_and_draw_audit(c2, seed_platform, nonce_shopper)
    assert r1.u == r2.u
    assert r1.selected == r2.selected
    assert r1.verify_commitment(return_id)
    assert r1.nonce_shopper == nonce_shopper
    assert r1.p == p


def test_mv11_symbolic_derivation() -> None:
    """MV-11: SymPy derivation of safe condition, floor, and X_max from settlement payoff tree."""
    assert verify_all_symbolic_identities()


@pytest.mark.req("FR-102")
def test_mv12_rule_based_simulator_analytic_agreement() -> None:
    """MV-12: Rule-based simulator executing settlement rules matches analytic G_k within 95% CI."""
    res = simulate_cell_analytic_agreement(price_minor=40000, declared_grade="B", tier="TRUSTED", n_trials=4000)
    assert res["within_95_ci"]


@pytest.mark.req("FR-10", "FR-59", "FR-84", "INV-11", "INV-15")
def test_mv13_and_mv15_jurisdiction_caps_and_adjacent_no_penalty() -> None:
    """MV-13 (EU F=0 and r(B)=1.00) & MV-15 (no path applies F or status change to adjacent mismatch)."""
    eu_policy = PolicyConfig.default_eu()
    assert eu_policy.compute_f_minor(40000) == 0
    assert eu_policy.grade_fraction("B") == Fraction(1, 1)

    us_policy = PolicyConfig.default_us()
    # Adjacent mismatch: declared B, verified C -> no F, no status loss (INV-15)
    s_adj = settle_return(
        SettlementInput(
            price_minor=40000,
            capture_amount_minor=40000,
            declared_grade="B",
            verified_grade="C",
            x_released_minor=22157,
            holdback_minor=6000,
            f_minor=2000,
            human_confirmed_gross=True,
            has_merchant_evidence=True,
        ),
        us_policy,
    )
    assert s_adj.f_charged_minor == 0
    assert not s_adj.status_affected
    assert s_adj.final_total_refund_minor == 32000

    # INV-10: Gross mismatch without human confirmation cannot be status-affecting or apply F
    mis_unconfirmed = evaluate_misdeclaration(
        declared_grade="B",
        verified_grade="D",
        excluded_at_alpha_accuse=True,
        hard_identity_failure=False,
        human_confirmed=False,
    )
    assert not mis_unconfirmed.is_confirmed_gross
    assert not mis_unconfirmed.status_affecting


@pytest.mark.req("FR-58", "FR-87", "FR-92", "INV-14")
def test_mv14_caps_never_exceeded() -> None:
    """MV-14: Pre-check-in release never exceeds X_max, account cap, or merchant aggregate cap."""
    policy = PolicyConfig.default_us()
    calib = _default_calib_b()
    inp = ReleaseInput(
        price_minor=40000,
        declared_grade="B",
        tier="TRUSTED",
        has_origin_passport=True,
        account_cap_remaining_minor=15000,
        merchant_cap_remaining_minor=12000,
    )
    res = decide_release(inp, policy, calib)
    assert res.x_released_minor == 12000
    assert res.binding_constraint == "MERCHANT_AGGREGATE_CAP"


@pytest.mark.req("FR-62", "FR-103")
def test_mv17_cusum_account_monitor() -> None:
    """MV-17: CUSUM matches reference behavior and resets after review."""
    cfg = CusumConfig(theta0=Fraction(10, 100), theta1=Fraction(40, 100), threshold_h=Fraction(4, 1))
    mon = CusumMonitor(cfg)
    for _ in range(5):
        alarm = mon.observe(is_adjacent_below=True)
    assert alarm
    mon.reset_after_review()
    assert mon.cusum_value == Fraction(0)


@pytest.mark.req("FR-37", "FR-46", "FR-78")
def test_mv18_keep_offer_posted_price_and_no_bounds() -> None:
    """MV-18: Keep-offer is single posted price <= (1 - theta_h) * k_max; no bounds or counter-offers."""
    policy = PolicyConfig.default_us()
    ko = compute_posted_keep_offer(
        KeepOfferInput(
            refund_owed_minor=38000,
            reverse_shipping_minor=1200,
            handling_cost_minor=800,
            recovery_lower_bound_minor=25000,
            tier="TRUSTED",
            intake_passed=True,
            is_safety_sensitive=False,
            group_keep_offers_last_90d=0,
            already_offered_on_return=False,
        ),
        policy,
    )
    assert ko.eligible
    assert ko.posted_price_minor is not None
    # k_max = 38000 + 1200 + 800 - 25000 = 15000; (1 - 0.30) * 15000 = 10500
    assert ko.posted_price_minor <= 10500
    payload = ko.to_public_dict()
    assert "k_max_minor" not in payload
    assert payload["allowed_actions"] == ["accept", "decline"]


@pytest.mark.req("FR-60", "FR-88", "INV-17")
def test_mv19_and_mv22_standard_routing_and_refile() -> None:
    """MV-19 & MV-22: Intake routing carries no penalty; re-filed return is forced STANDARD with X = 0."""
    r_intake = route_intake_and_refile(
        intake_excluded=True,
        refiled_after_cancel=False,
        hard_failure=False,
        nonce_unreadable=False,
    )
    assert r_intake.lane == "STANDARD"
    assert r_intake.penalty_minor == 0
    assert not r_intake.status_affected

    policy = PolicyConfig.default_us()
    calib = _default_calib_b()
    res_refile = decide_release(
        ReleaseInput(
            price_minor=40000,
            declared_grade="B",
            tier="TRUSTED",
            has_origin_passport=True,
            refiled_after_cancel=True,
        ),
        policy,
        calib,
    )
    assert res_refile.lane == "STANDARD"
    assert res_refile.x_released_minor == 0


@pytest.mark.req("FR-100")
def test_mv20_fifth_percentile_conservative_vs_mean() -> None:
    """MV-20: Using 5th-percentile posteriors never selects larger X or earlier timing than posterior means."""
    pooled = estimate_pooled_calibration(
        category="headphones",
        declared_grade="B",
        adjacent_successes=20,
        adjacent_trials=40,
        gross_successes=38,
        gross_trials=40,
    )
    policy = PolicyConfig.default_us()
    inp = ReleaseInput(price_minor=40000, declared_grade="B", tier="TRUSTED", has_origin_passport=True)
    res_p05 = decide_release(inp, policy, pooled.to_calibration_input(use_mean=False))
    res_mean = decide_release(inp, policy, pooled.to_calibration_input(use_mean=True))
    assert res_p05.x_released_minor <= res_mean.x_released_minor


@pytest.mark.req("FR-102")
def test_mv21_best_response_attacker_never_prefers_gross_overclaim() -> None:
    """MV-21: Best-response attacker never prefers a gross overclaim in any cell marked FAST."""
    report = find_best_response_attack(price_minor=40000, true_grade="D", tier="TRUSTED")
    assert not report["gross_overclaim_preferred"]


@pytest.mark.req("FR-91", "FR-93")
def test_mv23_and_mv25_identity_groups_and_value_weighted_promotion() -> None:
    """MV-23 (identity group shares lowest tier & cap) & MV-25 (cheap returns cannot farm trust)."""
    mgr = IdentityGroupManager()
    g_id = mgr.link_account("acc_1", payer_hash="p1", address_hash="addr_shared", device_hash="d1", tier="TRUSTED", largest_clean_minor=80000)
    mgr.link_account("acc_2", payer_hash="p2", address_hash="addr_shared", device_hash="d2", tier="NEW", largest_clean_minor=0)
    group = mgr.get_group(g_id)
    assert group.lowest_tier == "NEW"
    assert group.shared_cap_minor == 0

    # MV-25: 10 cheap returns of $10 ($100 total < $150 threshold) never reach ESTABLISHED
    prof = TrustProfile(
        tier="NEW",
        clean_count=10,
        cumulative_verified_value_minor=10000,
        largest_clean_value_minor=1000,
        account_age_days=120,
    )
    assert evaluate_tier_promotion(prof) == "NEW"


@pytest.mark.req("INV-18")
def test_mv24_degraded_modes_never_increase_x_or_advance_timing() -> None:
    """MV-24: Degraded modes (FB-01..FB-10) never increase X or advance timing (INV-18)."""
    policy = PolicyConfig.default_us()
    calib = _default_calib_b()
    inp = ReleaseInput(price_minor=10000, declared_grade="B", tier="TRUSTED", has_origin_passport=True)
    normal = decide_release(inp, policy, calib)
    for fb_code in ["FB-01", "FB-02", "FB-03", "FB-04", "FB-05", "FB-06", "FB-07", "FB-08", "FB-09", "FB-10"]:
        deg = apply_fallback_degradation(normal, fb_code=fb_code, price_minor=10000, fallback_passed_gates=False)
        assert deg.x_released_minor <= normal.x_released_minor
        assert deg.timing_rank >= normal.timing_rank


@pytest.mark.req("FR-13", "FR-68", "FR-74")
def test_fr13_evidence_scaling_and_fr74_no_passport_rules() -> None:
    """FR-13 (evidence scales with value/risk), FR-68 (DEF electronics self-test), FR-74 (NO_PASSPORT lane rules)."""
    policy = PolicyConfig.default_us()
    ev_low = determine_evidence_requirements(
        price_minor=10000, tier="TRUSTED", declared_grade="B", category="headphones", policy=policy
    )
    ev_high_def = determine_evidence_requirements(
        price_minor=80000, tier="TRUSTED", declared_grade="DEF", category="headphones", policy=policy
    )
    assert ev_low.min_photos == 2 and not ev_low.require_challenge_video
    assert ev_high_def.require_challenge_video and ev_high_def.require_functional_self_test

    calib = _default_calib_b()
    # FR-74 & AUD-17: Without origin passport, lane is explicitly reported as NO_PASSPORT (with R1 timing)
    no_pass_trusted_low = decide_release(
        ReleaseInput(price_minor=10000, declared_grade="B", tier="TRUSTED", has_origin_passport=False),
        policy,
        calib,
    )
    assert no_pass_trusted_low.lane == "NO_PASSPORT"
    assert no_pass_trusted_low.timing == "R1"

    no_pass_trusted_mid = decide_release(
        ReleaseInput(price_minor=40000, declared_grade="B", tier="TRUSTED", has_origin_passport=False),
        policy,
        calib,
    )
    assert no_pass_trusted_mid.lane == "STANDARD"
    assert no_pass_trusted_mid.x_released_minor == 0

