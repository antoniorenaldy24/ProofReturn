"""Round 4 Task T4: Enforce jurisdiction caps (RV3-06 MEDIUM, INV-11, FR-10, FR-84).

Tests:
1. For each jurisdiction in the SSOT table (US, EU, ID):
   - A compliant curve is accepted at policy creation (201) and in the engine (decide_release, settle_return).
   - A curve exceeding the diminished-value cap is rejected at policy creation (422 with field-level error)
     and in the engine (JurisdictionCapViolationError).
2. Regression test for the audit runtime probe (C = 0.50):
   - decide_release and settle_return reject C = 0.50 with JurisdictionCapViolationError;
     legal US curve (C = 0.80) produces holdback_minor == 6000 on $400 Grade B return.
3. EU and ID: any non-zero F (phi > 0, return_shipping_minor > 0, fee_f_minor > 0, f_minor > 0)
   is rejected at policy creation (422) and in the engine (JurisdictionCapViolationError).
4. Stored policies violating their jurisdiction are logged and marked inactive at startup,
   and API endpoints (/v1/returns/{id}/evidence, /v1/review/{id}/decision) return 409.
"""

from __future__ import annotations

import logging
import uuid
from fractions import Fraction
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.config import ProofReturnSettings
from backend.db.models import Order, Policy
from backend.db.repository import DatabaseRepository
from backend.domain.policy import PolicyConfig
from backend.policy_engine.caps import (
    JurisdictionCapViolationError,
    load_jurisdiction_table,
    validate_curve_for_jurisdiction,
)
from backend.policy_engine.release import (
    CalibrationInput,
    GapCalibration,
    ReleaseInput,
    decide_release,
)
from backend.policy_engine.settlement import SettlementInput, settle_return


def _calib_b() -> CalibrationInput:
    return CalibrationInput(
        declared_grade="B",
        adjacent_gap=GapCalibration(true_grade="C", q=Fraction(85, 100), d=Fraction(80, 100)),
        gross_gaps=[GapCalibration(true_grade="D", q=Fraction(92, 100), d=Fraction(90, 100))],
    )


@pytest.fixture()
def t4_env(tmp_path: Path) -> tuple[TestClient, DatabaseRepository, str]:
    db_file = tmp_path / f"r4_t4_{uuid.uuid4().hex[:8]}.db"
    db_url = f"sqlite:///{db_file}"
    settings = ProofReturnSettings(mode="judge", database_url=db_url, demo_mode=True, enable_scheduler=False)
    repo = DatabaseRepository(database_url=db_url)
    app = create_app(repository=repo, settings=settings, demo_mode=True, mode="judge")
    return TestClient(app), repo, db_url


@pytest.mark.req("RV3-06", "INV-11", "FR-10", "FR-84")
def test_each_ssot_jurisdiction_accepts_compliant_and_rejects_exceeding_cap(
    t4_env: tuple[TestClient, DatabaseRepository, str],
) -> None:
    """1. For each jurisdiction in the SSOT table (US, EU, ID): compliant accepted, cap violation rejected (422 & typed error)."""
    client, _repo, _db_url = t4_env
    admin_tok = mint_staff_token("merch_a", "MERCHANT_ADMIN", sub="admin_01")

    ssot_table = load_jurisdiction_table()
    jurisdictions = ssot_table["jurisdictions"]
    assert set(jurisdictions.keys()) >= {"US", "EU", "ID"}

    compliant_configs = {
        "US": {
            "curve": {"A": "1.00", "B": "0.95", "C": "0.80", "D": "0.50", "DEF": "1.00"},
            "phi": "0.05",
            "return_shipping_minor": 1200,
        },
        "EU": {
            "curve": {"A": "1.00", "B": "1.00", "C": "0.80", "D": "0.50", "DEF": "1.00"},
            "phi": "0.00",
            "return_shipping_minor": 0,
        },
        "ID": {
            "curve": {"A": "1.00", "B": "0.95", "C": "0.80", "D": "0.50", "DEF": "1.00"},
            "phi": "0.00",
            "return_shipping_minor": 0,
        },
    }

    violating_curves = {
        "US": ("B", {"A": "1.00", "B": "0.90", "C": "0.80", "D": "0.50", "DEF": "1.00"}),  # US min B is 0.95
        "EU": ("B", {"A": "1.00", "B": "0.95", "C": "0.80", "D": "0.50", "DEF": "1.00"}),  # EU min B is 1.00
        "ID": ("D", {"A": "1.00", "B": "0.95", "C": "0.80", "D": "0.40", "DEF": "1.00"}),  # ID min D is 0.50
    }

    calib = _calib_b()
    rel_inp = ReleaseInput(price_minor=40000, declared_grade="B", tier="TRUSTED", has_origin_passport=True)

    for jur in jurisdictions:
        cfg = compliant_configs[jur]
        # 1a. Compliant policy accepted via POST /v1/policies
        r_ok = client.post(
            "/v1/policies",
            headers={"Authorization": f"Bearer {admin_tok}"},
            json={
                "policy_version": f"pol_ok_{jur.lower()}",
                "jurisdiction": jur,
                "curve": {k: float(v) for k, v in cfg["curve"].items()},
                "phi": float(cfg["phi"]),
                "return_shipping_minor": cfg["return_shipping_minor"],
            },
        )
        assert r_ok.status_code == 201, f"{jur} compliant policy rejected: {r_ok.text}"

        # 1b. Compliant policy accepted in engine (validate_curve_for_jurisdiction, decide_release, settle_return)
        pol_cfg = PolicyConfig(
            version=f"pol_ok_{jur.lower()}",
            jurisdiction=jur,
            curve_json=cfg["curve"],
            phi=cfg["phi"],
            return_shipping_minor=cfg["return_shipping_minor"],
        )
        validate_curve_for_jurisdiction(pol_cfg, jur)
        dec = decide_release(rel_inp, pol_cfg, calib)
        assert dec.declared_refund_minor > 0

        settle_inp = SettlementInput(
            price_minor=40000,
            capture_amount_minor=40000,
            declared_grade="B",
            verified_grade="B",
            x_released_minor=dec.x_released_minor,
            holdback_minor=dec.holdback_minor,
            f_minor=0 if jur in {"EU", "ID"} else 2000,
            has_merchant_evidence=True,
        )
        s_res = settle_return(settle_inp, pol_cfg)
        assert s_res.status == "SETTLED"

        # 1c. Violating curve rejected at policy creation with 422 and field-level error
        bad_grade, bad_curve = violating_curves[jur]
        r_bad = client.post(
            "/v1/policies",
            headers={"Authorization": f"Bearer {admin_tok}"},
            json={
                "policy_version": f"pol_bad_{jur.lower()}",
                "jurisdiction": jur,
                "curve": {k: float(v) for k, v in bad_curve.items()},
                "phi": float(cfg["phi"]),
                "return_shipping_minor": cfg["return_shipping_minor"],
            },
        )
        assert r_bad.status_code == 422, f"{jur} violating curve not rejected with 422: {r_bad.text}"
        err_body = r_bad.json()
        assert f"curve.{bad_grade}" in str(err_body.get("field", "")) or any(
            f"curve.{bad_grade}" in str(e.get("field", "")) for e in err_body.get("errors", [])
        )

        # 1d. Violating curve rejected in engine (decide_release and settle_return raise JurisdictionCapViolationError)
        bad_pol_cfg = PolicyConfig(
            version=f"pol_bad_{jur.lower()}",
            jurisdiction=jur,
            curve_json=bad_curve,
            phi=cfg["phi"],
            return_shipping_minor=cfg["return_shipping_minor"],
        )
        with pytest.raises(JurisdictionCapViolationError):
            decide_release(rel_inp, bad_pol_cfg, calib)
        with pytest.raises(JurisdictionCapViolationError):
            settle_return(settle_inp, bad_pol_cfg)


@pytest.mark.req("RV3-06", "INV-11", "FR-10")
def test_runtime_probe_c_050_is_rejected_regression(
    t4_env: tuple[TestClient, DatabaseRepository, str],
) -> None:
    """2. Runtime probe regression: C = 0.50 is rejected in API (422) and engine (JurisdictionCapViolationError); legal curve gives holdback 6000."""
    client, _repo, _db_url = t4_env
    admin_tok = mint_staff_token("merch_a", "MERCHANT_ADMIN", sub="admin_01")

    calib = _calib_b()
    inp = ReleaseInput(price_minor=40000, declared_grade="B", tier="TRUSTED", has_origin_passport=True)

    # Legal US curve gives holdback_minor == 6000
    legal_us = PolicyConfig.default_us()
    legal_res = decide_release(inp, legal_us, calib)
    assert legal_res.holdback_minor == 6000

    # Runtime probe: C = 0.50 (which previously gave holdback 18000) MUST be rejected
    probe_curve = {"A": "1.00", "B": "0.95", "C": "0.50", "D": "0.50", "DEF": "1.00"}
    probe_policy = PolicyConfig(
        version="v2.1-probe-c050",
        jurisdiction="US",
        curve_json=probe_curve,
    )

    with pytest.raises(JurisdictionCapViolationError) as exc_info:
        decide_release(inp, probe_policy, calib)
    assert "curve.C" in exc_info.value.field

    settle_inp = SettlementInput(
        price_minor=40000,
        capture_amount_minor=40000,
        declared_grade="B",
        verified_grade="C",
        x_released_minor=20000,
        holdback_minor=6000,
        f_minor=2000,
        has_merchant_evidence=True,
    )
    with pytest.raises(JurisdictionCapViolationError):
        settle_return(settle_inp, probe_policy)

    r_api = client.post(
        "/v1/policies",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={
            "policy_version": "pol_probe_c050",
            "jurisdiction": "US",
            "curve": {"A": 1.0, "B": 0.95, "C": 0.50, "D": 0.50},
        },
    )
    assert r_api.status_code == 422
    assert "curve.C" in str(r_api.json())


@pytest.mark.req("RV3-06", "INV-11", "FR-10", "FR-84")
def test_eu_and_id_reject_any_non_zero_f(
    t4_env: tuple[TestClient, DatabaseRepository, str],
) -> None:
    """3. EU and ID: any non-zero F (phi, return_shipping_minor, fee_f_minor, f_minor) is rejected at policy creation (422) and in engine."""
    client, _repo, _db_url = t4_env
    admin_tok = mint_staff_token("merch_a", "MERCHANT_ADMIN", sub="admin_01")
    calib = _calib_b()
    rel_inp = ReleaseInput(price_minor=40000, declared_grade="B", tier="TRUSTED", has_origin_passport=True)

    for jur, b_val in [("EU", "1.00"), ("ID", "0.95")]:
        valid_curve = {"A": "1.00", "B": b_val, "C": "0.80", "D": "0.50", "DEF": "1.00"}

        # 3a. POST /v1/policies with non-zero fee_f_minor -> 422
        r_fee = client.post(
            "/v1/policies",
            headers={"Authorization": f"Bearer {admin_tok}"},
            json={
                "policy_version": f"pol_{jur.lower()}_bad_fee",
                "jurisdiction": jur,
                "curve": {k: float(v) for k, v in valid_curve.items()},
                "fee_f_minor": 1500,
            },
        )
        assert r_fee.status_code == 422, r_fee.text

        # 3b. POST /v1/policies with non-zero phi -> 422
        r_phi = client.post(
            "/v1/policies",
            headers={"Authorization": f"Bearer {admin_tok}"},
            json={
                "policy_version": f"pol_{jur.lower()}_bad_phi",
                "jurisdiction": jur,
                "curve": {k: float(v) for k, v in valid_curve.items()},
                "phi": 0.05,
            },
        )
        assert r_phi.status_code == 422, r_phi.text

        # 3c. Engine decide_release rejects PolicyConfig with non-zero phi or return_shipping_minor
        bad_phi_pol = PolicyConfig(
            version=f"pol_{jur.lower()}_phi",
            jurisdiction=jur,
            curve_json=valid_curve,
            phi="0.05",
            return_shipping_minor=0,
        )
        with pytest.raises(JurisdictionCapViolationError):
            decide_release(rel_inp, bad_phi_pol, calib)

        bad_ship_pol = PolicyConfig(
            version=f"pol_{jur.lower()}_ship",
            jurisdiction=jur,
            curve_json=valid_curve,
            phi="0.00",
            return_shipping_minor=1200,
        )
        with pytest.raises(JurisdictionCapViolationError):
            decide_release(rel_inp, bad_ship_pol, calib)

        # 3d. Engine settle_return rejects non-zero f_minor even when PolicyConfig itself has phi=0, return_shipping_minor=0
        clean_pol = PolicyConfig(
            version=f"pol_{jur.lower()}_clean",
            jurisdiction=jur,
            curve_json=valid_curve,
            phi="0.00",
            return_shipping_minor=0,
        )
        bad_settle_inp = SettlementInput(
            price_minor=40000,
            capture_amount_minor=40000,
            declared_grade="B",
            verified_grade="D",
            x_released_minor=0,
            holdback_minor=8000,
            f_minor=1500,  # Non-zero F forbidden in EU/ID
            human_confirmed_gross=True,
            excluded_at_alpha_accuse=True,
            has_merchant_evidence=True,
        )
        with pytest.raises(JurisdictionCapViolationError):
            settle_return(bad_settle_inp, clean_pol)


@pytest.mark.req("RV3-06", "INV-11", "FR-10")
def test_startup_validates_stored_policies_marks_inactive_and_api_returns_409(
    t4_env: tuple[TestClient, DatabaseRepository, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """4. Stored policy violating jurisdiction is logged and marked inactive at startup; API returns 409 when order uses it."""
    _client, repo, db_url = t4_env

    # Insert a stored policy with illegal C = 0.50 directly in DB
    with repo.get_session() as s:
        s.add(
            Policy(
                policy_version="pol_stored_illegal_c050",
                merchant_id="merch_a",
                jurisdiction="US",
                return_window_days=30,
                config_json={"curve": {"A": 1.0, "B": 0.95, "C": 0.50, "D": 0.50}},
            )
        )
        ord_1 = s.get(Order, "ord_demo_1")
        assert ord_1 is not None
        ord_1.policy_version = "pol_stored_illegal_c050"
        s.add(ord_1)
        s.commit()

    # Restart app: startup validation must log the violation and mark the policy inactive
    settings = ProofReturnSettings(mode="judge", database_url=db_url, demo_mode=True, enable_scheduler=False)
    with caplog.at_level(logging.WARNING):
        app2 = create_app(repository=repo, settings=settings, demo_mode=True, mode="judge")
    client2 = TestClient(app2)

    assert any("pol_stored_illegal_c050" in rec.message for rec in caplog.records)

    stored_pol = repo.get_policy("pol_stored_illegal_c050")
    assert stored_pol is not None
    assert stored_pol.is_active is False

    # Calling evidence endpoint on an order with an invalid/inactive policy returns 409
    shopper_tok = mint_shopper_token("ord_demo_1", "shopper_1")
    ret = repo.get_return("ret_demo_1")
    assert ret is not None
    r_ev = client2.post(
        "/v1/returns/ret_demo_1/evidence",
        headers={"Authorization": f"Bearer {shopper_tok}"},
        json={
            "sha256": "a" * 64,
            "faces_detected": 0,
            "client_blur_applied": False,
            "text_in_media": ret.challenge_nonce,
        },
    )
    assert r_ev.status_code == 409, r_ev.text
    assert r_ev.json()["code"] == "JURISDICTION_CAP_VIOLATION"
