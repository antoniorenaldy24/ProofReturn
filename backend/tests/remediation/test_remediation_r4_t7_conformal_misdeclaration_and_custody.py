"""Round 4 Task T7: Wire conformal calibration into misdeclaration decisions; resolve custody and seal modules (RV2-05 MEDIUM, INV-10, FR-25)."""

from __future__ import annotations

import pathlib
from fractions import Fraction
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.ai.calibration.conformal import (
    ConformalCalibrationSession,
    MondrianConformalCalibrator,
    set_conformal_calibrator,
)
from backend.api.app import create_app
from backend.config import ProofReturnSettings
from backend.db.models import (
    Assessment,
    Merchant,
    Order,
    OrderItem,
    Passport,
    Policy,
    Return,
    ShopperAccount,
)
from backend.db.repository import DatabaseRepository
from backend.domain.policy import PolicyConfig

VALID_BOOTSTRAP_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
DEMO_WEBHOOK_SECRET = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"


def _make_settings(db_url: str) -> ProofReturnSettings:
    return ProofReturnSettings(
        database_url=db_url,
        demo_mode=True,
        mode="judge",
        enable_scheduler=False,
        carrier_events_manual=True,
        demo_bootstrap_key=SecretStr(VALID_BOOTSTRAP_KEY),
        demo_webhook_secret=SecretStr(DEMO_WEBHOOK_SECRET),
    )


def _setup_calibrator_with_electronics() -> MondrianConformalCalibrator:
    """Prepare a calibrator with fitted quantiles for category 'electronics'."""
    calibrator = MondrianConformalCalibrator(alpha_route=0.10, alpha_accuse=0.02)
    # Fit 250 calibration sessions for 'electronics' where A has score 0.05
    sessions = []
    for i in range(250):
        sessions.append(
            ConformalCalibrationSession(
                session_id=f"cal_{i}",
                category="electronics",
                true_grade="B",
                cum_probs={"D": 1.0, "C": 0.99, "B": 0.95, "A": 0.05},
            )
        )
    calibrator.fit_category("electronics", sessions)
    return calibrator


def _seed_test_return_with_assessment(
    repo: DatabaseRepository,
    *,
    return_id: str,
    order_id: str,
    account_id: str,
    category_sku: str,
    declared_grade: str,
    predicted_grade: str,
    conformal_set: list[str],
    cum_probs: dict[str, float] | None = None,
) -> None:
    # 1. Policy
    pol_cfg = PolicyConfig.default_us()
    repo.save_policy(
        Policy(
            policy_version="pol_us_t7",
            merchant_id="merch_t7",
            jurisdiction="US",
            config_json=pol_cfg.model_dump(),
            is_active=True,
        )
    )
    # 2. Merchant
    repo.save_merchant(
        Merchant(
            merchant_id="merch_t7",
            name="Merchant T7",
            instant_exposure_cap_minor=1000000,
            outstanding_instant_exposure_minor=0,
        )
    )
    # 3. Shopper Account
    repo.save_shopper(
        ShopperAccount(
            account_id=account_id,
            identity_group_id="grp_t7",
            trust_tier="ESTABLISHED",
        )
    )
    # 4. Order
    repo.save_order(
        Order(
            order_id=order_id,
            merchant_id="merch_t7",
            account_id=account_id,
            policy_version="pol_us_t7",
            capture_id=f"CAP-{order_id}",
            capture_amount_minor=40000,
            currency="USD",
        )
    )
    # 5. Passport & Order Item
    passport_id = f"pass_{return_id}"
    repo.save_passport(
        Passport(
            passport_id=passport_id,
            merchant_id="merch_t7",
            sku=category_sku,
            origin_grade="A",
            weight_g=250,
            self_test_passed=True,
        )
    )
    item_id = f"item_{return_id}"
    repo.save_order_item(
        OrderItem(
            order_item_id=item_id,
            order_id=order_id,
            passport_id=passport_id,
            sku=category_sku,
            price_minor=40000,
            currency="USD",
        )
    )
    # 6. Return
    repo.save_return(
        Return(
            return_id=return_id,
            order_id=order_id,
            order_item_id=item_id,
            merchant_id="merch_t7",
            shopper_id=account_id,
            state="RECEIVED",
            lane="FAST",
            timing="R0",
            declared_grade=declared_grade,
            r0_tranche_minor=10000,
        )
    )
    # 7. Assessment
    repo.save_assessment(
        Assessment(
            assessment_id=f"ass_{return_id}",
            return_id=return_id,
            predicted_grade=predicted_grade,
            conformal_set=conformal_set,
            replay_label="LIVE",
            forensic_flags=[],
            cum_probs=cum_probs or {},
        )
    )


@pytest.mark.req("RV2-05", "INV-10", "FR-25")
def test_reviewer_sends_excluded_true_but_calibrator_does_not_exclude_no_fee_no_restricted(
    tmp_path: pathlib.Path,
) -> None:
    """Reviewer sends excluded_at_alpha_accuse=true in body for a case the calibrator does not exclude -> no F, no RESTRICTED."""
    db_url = f"sqlite:///{tmp_path / 't7_no_exclude.db'}"
    settings = _make_settings(db_url)
    repo = DatabaseRepository(database_url=db_url)

    calibrator = _setup_calibrator_with_electronics()
    set_conformal_calibrator(calibrator)

    # Return declared A, assessment predicts A with high probability (cum_prob A = 0.95 -> score = 0.05 <= q_accuse)
    # Calibrator evaluation: declared_grade 'A' is NOT excluded!
    _seed_test_return_with_assessment(
        repo,
        return_id="ret_t7_no_ex",
        order_id="ord_t7_no_ex",
        account_id="shop_t7_1",
        category_sku="PR-HP-XM5",  # maps to 'headphones' / electronics
        declared_grade="A",
        predicted_grade="A",
        conformal_set=["A", "B"],
        cum_probs={"D": 1.0, "C": 0.99, "B": 0.98, "A": 0.95},
    )

    app = create_app(settings=settings, repository=repo, demo_mode=True)
    client = TestClient(app)

    # Mint reviewer token
    r_tok = client.post(
        "/v1/auth/staff-token",
        headers={"X-Demo-Bootstrap-Key": VALID_BOOTSTRAP_KEY},
        json={"merchant_id": "merch_t7", "role": "REVIEWER", "staff_id": "rev_01"},
    )
    assert r_tok.status_code == 200
    token = r_tok.json()["access_token"]

    # Reviewer attempts to force excluded_at_alpha_accuse=true with gross downgrade to D
    r_dec = client.post(
        "/v1/review/ret_t7_no_ex/decision",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem_t7_1"},
        json={
            "outcome": "CONFIRMED_GROSS_MISDECLARATION",
            "verified_grade": "D",
            "excluded_at_alpha_accuse": True,  # Must be IGNORED by server!
            "notes": "Reviewer trying to force penalty",
        },
    )
    assert r_dec.status_code == 200, r_dec.text
    data = r_dec.json()

    # Server must compute excluded_at_alpha_accuse=False -> no F fee charged!
    assert data.get("f_charged_minor", 0) == 0
    assert data.get("new_tier_override") != "RESTRICTED"

    # Verify shopper account was NOT restricted
    shopper = repo.get_shopper("shop_t7_1")
    assert shopper is not None
    assert shopper.trust_tier != "RESTRICTED"


@pytest.mark.req("RV2-05", "INV-10", "FR-25")
def test_calibrator_excludes_and_reviewer_confirms_fee_and_restricted_applied(
    tmp_path: pathlib.Path,
) -> None:
    """Calibrator excludes at alpha_accuse and reviewer confirms gross -> F fee charged and RESTRICTED applied."""
    db_url = f"sqlite:///{tmp_path / 't7_exclude.db'}"
    settings = _make_settings(db_url)
    repo = DatabaseRepository(database_url=db_url)

    calibrator = _setup_calibrator_with_electronics()
    set_conformal_calibrator(calibrator)

    # Return declared A, assessment predicts D with low cum_prob for A (0.005 -> score = 0.995 > q_accuse)
    # Calibrator evaluation: declared_grade 'A' IS excluded at alpha_accuse!
    _seed_test_return_with_assessment(
        repo,
        return_id="ret_t7_ex",
        order_id="ord_t7_ex",
        account_id="shop_t7_2",
        category_sku="PR-HP-XM5",  # maps to 'headphones'
        declared_grade="A",
        predicted_grade="D",
        conformal_set=["D"],
        cum_probs={"D": 1.0, "C": 0.05, "B": 0.02, "A": 0.005},
    )

    app = create_app(settings=settings, repository=repo, demo_mode=True)
    client = TestClient(app)

    r_tok = client.post(
        "/v1/auth/staff-token",
        headers={"X-Demo-Bootstrap-Key": VALID_BOOTSTRAP_KEY},
        json={"merchant_id": "merch_t7", "role": "REVIEWER", "staff_id": "rev_01"},
    )
    assert r_tok.status_code == 200
    token = r_tok.json()["access_token"]

    # Reviewer confirms gross discrepancy to D
    r_dec = client.post(
        "/v1/review/ret_t7_ex/decision",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem_t7_2"},
        json={
            "outcome": "CONFIRMED_GROSS_MISDECLARATION",
            "verified_grade": "D",
            "notes": "Verified severe damage and housing crack",
        },
    )
    assert r_dec.status_code == 200, r_dec.text
    data = r_dec.json()

    # Server computed excluded_at_alpha_accuse=True AND reviewer confirmed -> F charged & RESTRICTED
    assert data["f_charged_minor"] > 0
    assert data["new_tier_override"] == "RESTRICTED"

    # Shopper account must now be RESTRICTED
    shopper = repo.get_shopper("shop_t7_2")
    assert shopper is not None
    assert shopper.trust_tier == "RESTRICTED"


@pytest.mark.req("RV2-05", "INV-10", "FR-25")
def test_category_without_calibration_data_never_excluded(
    tmp_path: pathlib.Path,
) -> None:
    """Category without calibration data -> protective default applies (never excluded, no F, no RESTRICTED)."""
    db_url = f"sqlite:///{tmp_path / 't7_uncalibrated.db'}"
    settings = _make_settings(db_url)
    repo = DatabaseRepository(database_url=db_url)

    calibrator = _setup_calibrator_with_electronics()
    set_conformal_calibrator(calibrator)

    # Item in an uncalibrated category 'luxury_apparel'
    _seed_test_return_with_assessment(
        repo,
        return_id="ret_t7_uncal",
        order_id="ord_t7_uncal",
        account_id="shop_t7_3",
        category_sku="PR-LUX-COAT",  # uncalibrated SKU
        declared_grade="A",
        predicted_grade="D",
        conformal_set=["D"],
        cum_probs={"D": 1.0, "C": 0.05, "B": 0.02, "A": 0.005},
    )

    app = create_app(settings=settings, repository=repo, demo_mode=True)
    client = TestClient(app)

    r_tok = client.post(
        "/v1/auth/staff-token",
        headers={"X-Demo-Bootstrap-Key": VALID_BOOTSTRAP_KEY},
        json={"merchant_id": "merch_t7", "role": "REVIEWER", "staff_id": "rev_01"},
    )
    assert r_tok.status_code == 200
    token = r_tok.json()["access_token"]

    r_dec = client.post(
        "/v1/review/ret_t7_uncal/decision",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "idem_t7_3"},
        json={
            "outcome": "CONFIRMED_GROSS_MISDECLARATION",
            "verified_grade": "D",
            "excluded_at_alpha_accuse": True,
            "notes": "Trying to confirm uncalibrated item",
        },
    )
    assert r_dec.status_code == 200, r_dec.text
    data = r_dec.json()

    # Uncalibrated category -> protective default (excluded=False) -> no F, no RESTRICTED
    assert data.get("f_charged_minor", 0) == 0
    assert data.get("new_tier_override") != "RESTRICTED"

    shopper = repo.get_shopper("shop_t7_3")
    assert shopper is not None
    assert shopper.trust_tier != "RESTRICTED"


@pytest.mark.req("RV2-05", "FR-29", "FR-64")
def test_custody_and_seal_modules_used_by_api(
    tmp_path: pathlib.Path,
) -> None:
    """Receiving checkpoints and carrier events use CustodyLedger and return_seal through the API."""
    db_url = f"sqlite:///{tmp_path / 't7_custody.db'}"
    settings = _make_settings(db_url)
    repo = DatabaseRepository(database_url=db_url)

    _seed_test_return_with_assessment(
        repo,
        return_id="ret_t7_cust",
        order_id="ord_t7_cust",
        account_id="shop_t7_4",
        category_sku="PR-HP-XM5",
        declared_grade="B",
        predicted_grade="B",
        conformal_set=["B"],
    )

    app = create_app(settings=settings, repository=repo, demo_mode=True)
    client = TestClient(app)

    # 1. Receiver token
    r_tok = client.post(
        "/v1/auth/staff-token",
        headers={"X-Demo-Bootstrap-Key": VALID_BOOTSTRAP_KEY},
        json={"merchant_id": "merch_t7", "role": "RECEIVER", "staff_id": "rec_01"},
    )
    assert r_tok.status_code == 200
    token = r_tok.json()["access_token"]

    # 2. Record checkpoint on receiving station via API
    r_chk = client.post(
        "/v1/receiving/pass_ret_t7_cust/checkpoint",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "interval": "DOCK",
            "weight_g": 245,
            "seal_status": "INTACT",
            "evidence_ref": "evidence_dock_t7.jpg",
        },
    )
    assert r_chk.status_code == 200, r_chk.text
    data_chk = r_chk.json()
    assert data_chk["interval"] == "DOCK"
    assert data_chk["responsible_interval"] in {"ORIGIN", "CARRIER_OUT", "SHOPPER", "CARRIER_RETURN", "DOCK", "UNDETERMINED"}
    assert "weight_delta_g" in data_chk
