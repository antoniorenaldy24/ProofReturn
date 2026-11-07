"""Round 4 Task T2: Map PayPal refund and capture statuses; never fabricate provider ids (RV3-01 MEDIUM, RV3-02 LOW)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import pathlib
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.config import ProofReturnSettings
from backend.db.models import Order
from backend.db.repository import DatabaseRepository


class ConfigurableFakePayPalClient:
    """Fake PayPal client inside backend/tests only for testing refund/capture status mapping."""

    has_credentials = True

    def __init__(self) -> None:
        self.refund_calls: list[dict[str, Any]] = []
        self.get_refund_calls: list[str] = []
        self.capture_calls: list[str] = []
        self.next_refund_response: dict[str, Any] = {
            "id": "PP-REF-DEFAULT",
            "status": "COMPLETED",
            "paypal_debug_id": "dbg_default",
        }
        self.next_get_refund_response: dict[str, Any] = {
            "id": "PP-REF-DEFAULT",
            "status": "COMPLETED",
            "paypal_debug_id": "dbg_get_default",
        }
        self.next_capture_response: dict[str, Any] = {
            "id": "PP-CAP-DEFAULT",
            "status": "COMPLETED",
            "paypal_debug_id": "dbg_cap_default",
        }

    def refund_capture_live(
        self,
        *,
        capture_id: str,
        request_id: str,
        amount_minor: int,
        currency: str = "USD",
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.refund_calls.append(
            {
                "capture_id": capture_id,
                "request_id": request_id,
                "amount_minor": amount_minor,
                "currency": currency,
            }
        )
        return dict(self.next_refund_response)

    def get_refund_live(self, *, refund_id: str) -> dict[str, Any]:
        self.get_refund_calls.append(refund_id)
        return dict(self.next_get_refund_response)

    def capture_order(
        self,
        *,
        paypal_order_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        self.capture_calls.append(paypal_order_id)
        return dict(self.next_capture_response)


def _make_settings(db_url: str, secret: str = "r4_t2_webhook_secret_key_32bytes!") -> ProofReturnSettings:
    return ProofReturnSettings(
        database_url=db_url,
        demo_mode=True,
        mode="judge",
        enable_scheduler=False,
        demo_webhook_secret=secret,
    )


def _sign_webhook(secret: str, payload: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return raw, {
        "Content-Type": "application/json",
        "X-Demo-Webhook-Signature": sig,
    }


def _plan_r0_via_api(client: TestClient, repo: DatabaseRepository, return_id: str = "ret_demo_1") -> int:
    shopper_token = mint_shopper_token(order_id="ord_demo_1", shopper_id="shopper_1")
    ret = repo.get_return(return_id)
    assert ret is not None
    nonce = ret.challenge_nonce

    client.post(
        f"/v1/returns/{return_id}/declaration",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "declared_grade": "B",
            "fast_lane_terms_accepted": True,
            "shopper_nonce": "nonce_r4_t2",
        },
    )
    r_ev = client.post(
        f"/v1/returns/{return_id}/evidence",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "sha256": "c" * 64,
            "text_in_media": nonce,
            "faces_detected": 0,
            "client_blur_applied": True,
        },
    )
    assert r_ev.status_code == 200, r_ev.text
    return int(r_ev.json()["r0_tranche_minor"])


@pytest.mark.req("RV3-01", "FR-75", "FX-07", "FX-18")
def test_pending_refund_not_confirmed_then_completed_via_get_or_webhook_confirms_once(
    tmp_path: pathlib.Path,
) -> None:
    """PENDING refund is not confirmed; a later COMPLETED from GET or webhook confirms it exactly once."""
    # Scenario A: PENDING -> reconciled via GET /v2/payments/refunds/{id} -> duplicate webhook does not double-confirm
    db_url_a = f"sqlite:///{tmp_path / 't2_pending_get.db'}"
    settings_a = _make_settings(db_url_a)
    repo_a = DatabaseRepository(database_url=db_url_a)
    fake_pp_a = ConfigurableFakePayPalClient()
    app_a = create_app(settings=settings_a, repository=repo_a, demo_mode=True, paypal_client=fake_pp_a)
    client_a = TestClient(app_a)
    admin_tok = mint_staff_token(merchant_id="merch_a", role="MERCHANT_ADMIN", sub="admin_01")

    r0_minor = _plan_r0_via_api(client_a, repo_a)
    fake_pp_a.next_refund_response = {
        "id": "PP-REF-PEND-01",
        "status": "PENDING",
        "status_details": {"reason": "ECHECK"},
        "paypal_debug_id": "dbg_pend_01",
    }

    # Outbox Run #1: POST refund returns PENDING -> stays SUBMITTED with status_detail, NOT confirmed
    r_out1 = client_a.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {admin_tok}"})
    assert r_out1.status_code == 200
    assert len(fake_pp_a.refund_calls) == 1
    assert len(fake_pp_a.get_refund_calls) == 0

    acts_a1 = repo_a.list_refund_actions_by_order("ord_demo_1")
    assert len(acts_a1) == 1
    assert acts_a1[0].status == "SUBMITTED"
    assert acts_a1[0].paypal_refund_id == "PP-REF-PEND-01"
    assert acts_a1[0].status_detail == "ECHECK"

    ord_a1 = repo_a.get_order("ord_demo_1")
    assert ord_a1 is not None
    assert ord_a1.confirmed_refunded_minor == 0
    assert ord_a1.pending_refunded_minor == r0_minor

    # Outbox Run #2: GET /v2/payments/refunds/{id} returns COMPLETED -> confirms once
    fake_pp_a.next_get_refund_response = {
        "id": "PP-REF-PEND-01",
        "status": "COMPLETED",
        "paypal_debug_id": "dbg_get_comp_01",
    }
    r_out2 = client_a.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {admin_tok}"})
    assert r_out2.status_code == 200
    assert len(fake_pp_a.refund_calls) == 1  # No second POST refund
    assert fake_pp_a.get_refund_calls == ["PP-REF-PEND-01"]

    acts_a2 = repo_a.list_refund_actions_by_order("ord_demo_1")
    assert acts_a2[0].status == "CONFIRMED"
    ord_a2 = repo_a.get_order("ord_demo_1")
    assert ord_a2 is not None
    assert ord_a2.confirmed_refunded_minor == r0_minor
    assert ord_a2.pending_refunded_minor == 0

    # Later PAYMENT.CAPTURE.REFUNDED webhook arrives for the same refund -> must NOT double-confirm
    raw_wh_a, hdr_wh_a = _sign_webhook(
        settings_a.demo_webhook_secret.get_secret_value(),
        {
            "id": "WH-REF-COMP-A",
            "event_type": "PAYMENT.CAPTURE.REFUNDED",
            "resource": {"id": "PP-REF-PEND-01", "custom_id": "ord_demo_1", "status": "COMPLETED"},
        },
    )
    assert client_a.post("/v1/webhooks/paypal", content=raw_wh_a, headers=hdr_wh_a).status_code == 200
    ord_a3 = repo_a.get_order("ord_demo_1")
    assert ord_a3 is not None
    assert ord_a3.confirmed_refunded_minor == r0_minor
    assert ord_a3.pending_refunded_minor == 0

    # Scenario B: PENDING -> confirmed by PAYMENT.CAPTURE.REFUNDED webhook -> subsequent outbox run does not double-confirm
    db_url_b = f"sqlite:///{tmp_path / 't2_pending_wh.db'}"
    settings_b = _make_settings(db_url_b)
    repo_b = DatabaseRepository(database_url=db_url_b)
    fake_pp_b = ConfigurableFakePayPalClient()
    app_b = create_app(settings=settings_b, repository=repo_b, demo_mode=True, paypal_client=fake_pp_b)
    client_b = TestClient(app_b)

    r0_minor_b = _plan_r0_via_api(client_b, repo_b)
    fake_pp_b.next_refund_response = {
        "id": "PP-REF-PEND-02",
        "status": "PENDING",
        "status_detail": "PENDING_REVIEW",
    }
    assert client_b.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {admin_tok}"}).status_code == 200
    assert repo_b.get_order("ord_demo_1").confirmed_refunded_minor == 0

    raw_wh_b, hdr_wh_b = _sign_webhook(
        settings_b.demo_webhook_secret.get_secret_value(),
        {
            "id": "WH-REF-COMP-B",
            "event_type": "PAYMENT.CAPTURE.REFUNDED",
            "resource": {"id": "PP-REF-PEND-02", "custom_id": "ord_demo_1", "status": "COMPLETED"},
        },
    )
    assert client_b.post("/v1/webhooks/paypal", content=raw_wh_b, headers=hdr_wh_b).status_code == 200

    ord_b_after_wh = repo_b.get_order("ord_demo_1")
    assert ord_b_after_wh is not None
    assert ord_b_after_wh.confirmed_refunded_minor == r0_minor_b
    assert ord_b_after_wh.pending_refunded_minor == 0
    assert repo_b.list_refund_actions_by_order("ord_demo_1")[0].status == "CONFIRMED"

    # Subsequent outbox run does not call GET or POST or double-confirm
    assert client_b.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {admin_tok}"}).status_code == 200
    assert len(fake_pp_b.get_refund_calls) == 0
    assert repo_b.get_order("ord_demo_1").confirmed_refunded_minor == r0_minor_b


@pytest.mark.req("RV3-01", "FX-04")
@pytest.mark.parametrize("terminal_status", ["FAILED", "CANCELLED"])
def test_failed_and_cancelled_release_pending_and_never_sent_again(
    tmp_path: pathlib.Path,
    terminal_status: str,
) -> None:
    """FAILED and CANCELLED release pending; refund is never sent again."""
    db_url = f"sqlite:///{tmp_path / f't2_{terminal_status.lower()}.db'}"
    settings = _make_settings(db_url)
    repo = DatabaseRepository(database_url=db_url)
    fake_pp = ConfigurableFakePayPalClient()
    app = create_app(settings=settings, repository=repo, demo_mode=True, paypal_client=fake_pp)
    client = TestClient(app)
    admin_tok = mint_staff_token(merchant_id="merch_a", role="MERCHANT_ADMIN", sub="admin_01")

    r0_minor = _plan_r0_via_api(client, repo)
    assert repo.get_order("ord_demo_1").pending_refunded_minor == r0_minor

    fake_pp.next_refund_response = {
        "id": f"PP-REF-{terminal_status}-01",
        "status": terminal_status,
        "paypal_debug_id": f"dbg_{terminal_status.lower()}",
    }

    # Outbox Run #1 -> marks FAILED_PERMANENT and releases pending_refunded_minor
    r_out1 = client.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {admin_tok}"})
    assert r_out1.status_code == 200
    assert len(fake_pp.refund_calls) == 1

    acts = repo.list_refund_actions_by_order("ord_demo_1")
    assert len(acts) == 1
    assert acts[0].status == "FAILED_PERMANENT"

    ord_row = repo.get_order("ord_demo_1")
    assert ord_row is not None
    assert ord_row.pending_refunded_minor == 0
    assert ord_row.confirmed_refunded_minor == 0

    # Outbox Run #2 -> never sent again
    r_out2 = client.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {admin_tok}"})
    assert r_out2.status_code == 200
    assert len(fake_pp.refund_calls) == 1
    assert len(fake_pp.get_refund_calls) == 0


@pytest.mark.req("RV3-01", "RV3-02")
def test_2xx_without_id_marks_unknown_and_confirmed_balance_unchanged(
    tmp_path: pathlib.Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """2xx without id -> UNKNOWN, confirmed balance unchanged, logs REFUND_ID_MISSING."""
    db_url = f"sqlite:///{tmp_path / 't2_noid.db'}"
    settings = _make_settings(db_url)
    repo = DatabaseRepository(database_url=db_url)
    fake_pp = ConfigurableFakePayPalClient()
    app = create_app(settings=settings, repository=repo, demo_mode=True, paypal_client=fake_pp)
    client = TestClient(app)
    admin_tok = mint_staff_token(merchant_id="merch_a", role="MERCHANT_ADMIN", sub="admin_01")

    r0_minor = _plan_r0_via_api(client, repo)
    fake_pp.next_refund_response = {
        "status": "COMPLETED",
        "paypal_debug_id": "dbg_missing_id",
    }

    with caplog.at_level(logging.WARNING, logger="proofreturn.payments.outbox"):
        r_out = client.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {admin_tok}"})
    assert r_out.status_code == 200
    assert "REFUND_ID_MISSING" in caplog.text

    acts = repo.list_refund_actions_by_order("ord_demo_1")
    assert len(acts) == 1
    assert acts[0].status == "UNKNOWN"
    assert acts[0].paypal_refund_id is None

    ord_row = repo.get_order("ord_demo_1")
    assert ord_row is not None
    assert ord_row.confirmed_refunded_minor == 0
    assert ord_row.pending_refunded_minor == r0_minor


@pytest.mark.req("RV3-01", "RV3-02", "AUD-22")
def test_resale_capture_response_without_id_returns_409_and_ownership_unchanged(
    tmp_path: pathlib.Path,
) -> None:
    """Resale capture response without id -> 409 CAPTURE_FAILED, ownership unchanged."""
    db_url = f"sqlite:///{tmp_path / 't2_resale_noid.db'}"
    settings = _make_settings(db_url)
    repo = DatabaseRepository(database_url=db_url)
    fake_pp = ConfigurableFakePayPalClient()
    fake_pp.next_capture_response = {
        "status": "COMPLETED",  # Missing 'id'!
    }
    app = create_app(settings=settings, repository=repo, demo_mode=True, paypal_client=fake_pp)
    client = TestClient(app)

    admin_tok = mint_staff_token(merchant_id="merch_a", role="MERCHANT_ADMIN", sub="admin_01")
    r_list = client.post(
        "/v1/resale/listings",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"passport_id": "pass_demo_1", "verified_grade": "A", "price_minor": 31500},
    )
    assert r_list.status_code == 201
    listing_id = r_list.json()["listing_id"]

    # Create an order for shopper_2 that has a paypal_order_id but no capture_id yet
    repo.save_order(
        Order(
            order_id="ord_resale_uncaptured",
            merchant_id="merch_a",
            account_id="shopper_2",
            policy_version="pol_v1_us_ca",
            paypal_order_id="PP-ORD-UNC-01",
            capture_id="",
            capture_amount_minor=31500,
            currency="USD",
        )
    )

    shopper_tok = mint_shopper_token(order_id="ord_resale_uncaptured", shopper_id="shopper_2")
    r_buy = client.post(
        f"/v1/resale/listings/{listing_id}/order",
        headers={"Authorization": f"Bearer {shopper_tok}"},
        json={},
    )
    assert r_buy.status_code == 409, r_buy.text
    assert r_buy.json()["code"] == "CAPTURE_FAILED"

    # Capture id was NOT fabricated or stored
    ord_after = repo.get_order("ord_resale_uncaptured")
    assert ord_after is not None
    assert not ord_after.capture_id

    # Listing remains ACTIVE and passport ownership remains shopper_1
    listing_after = repo.get_resale_listing(listing_id)
    assert listing_after is not None
    assert listing_after.status == "ACTIVE"

    passport_after = repo.get_passport("pass_demo_1")
    assert passport_after is not None
    assert passport_after.current_owner_ref == "shopper_1"
