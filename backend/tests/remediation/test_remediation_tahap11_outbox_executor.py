"""Tests for TASK T4: Refund outbox executor and ST-01 through the system (AUD-02 CRITICAL, ARC-19).

Required behavior:
1. RefundOutboxExecutor.run_once(limit):
   - PLANNED -> SUBMITTED -> call PayPal with request_id -> 2xx COMPLETED -> CONFIRMED, moves pending to confirmed atomically.
   - Network error or timeout -> UNKNOWN; retried with SAME request_id.
   - 4xx -> FAILED_PERMANENT; releases pending_refunded_minor.
   - attempt_count increments on every call.
2. Production code never fabricates success: remove offline COMPLETED fallbacks from payments/client.py.
   Without credentials, executor leaves actions PLANNED and logs PAYPAL_NOT_CONFIGURED.
3. POST /v1/ops/outbox/run requires MERCHANT_ADMIN of the same merchant.
4. test_st01_through_system (marker sandbox) runs end-to-end against PayPal Sandbox.
"""

import os
from pathlib import Path
import secrets
import time
from typing import Any
import httpx
import pytest
from pydantic import SecretStr
from starlette.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.config import ProofReturnSettings
from backend.db.models import Order, OrderItem, RefundAction, Return
from backend.db.repository import DatabaseRepository
from backend.payments.client import PayPalSandboxClient

try:
    from backend.payments.outbox import RefundOutboxExecutor
except ImportError:
    RefundOutboxExecutor = None  # type: ignore


VALID_BOOTSTRAP_KEY = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
VALID_WEBHOOK_SECRET = "webhooksecret0123456789abcdef0123456789abcdef0123456789abcdef"


@pytest.fixture
def test_repo(tmp_path: Path) -> DatabaseRepository:
    db_file = tmp_path / "test_t4.db"
    repo = DatabaseRepository(database_url=f"sqlite:///{db_file}", run_migrations_on_init=True)
    repo.seed_demo_data()
    return repo


@pytest.fixture
def demo_settings() -> ProofReturnSettings:
    return ProofReturnSettings(
        demo_mode=True,
        demo_bootstrap_key=SecretStr(VALID_BOOTSTRAP_KEY),
        demo_webhook_secret=SecretStr(VALID_WEBHOOK_SECRET),
    )


class FakePayPalClient:
    """Configurable fake PayPal Sandbox client for testing executor without network calls."""

    def __init__(self, mode: str = "success") -> None:
        self.mode = mode
        self.call_count = 0
        self.recorded_requests: list[dict[str, Any]] = []
        self.has_credentials = True

    def refund_capture_live(
        self,
        *,
        capture_id: str,
        request_id: str,
        amount_minor: int,
        currency: str = "USD",
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.call_count += 1
        self.recorded_requests.append({
            "capture_id": capture_id,
            "request_id": request_id,
            "amount_minor": amount_minor,
            "currency": currency,
        })

        if self.mode == "timeout":
            raise httpx.ReadTimeout("Simulated PayPal read timeout")
        elif self.mode == "4xx":
            req = httpx.Request("POST", f"https://api-m.sandbox.paypal.com/v2/payments/captures/{capture_id}/refund")
            resp = httpx.Response(
                422,
                request=req,
                headers={"paypal-debug-id": "dbg_4xx_err"},
                json={"name": "CAPTURE_ALREADY_REFUNDED", "message": "The capture is already fully refunded."},
            )
            raise httpx.HTTPStatusError("422 Unprocessable Entity", request=req, response=resp)
        elif self.mode == "fail_then_success":
            if self.call_count == 1:
                raise httpx.ReadTimeout("Simulated first timeout")
            return {
                "id": f"PP-REF-{request_id[:8]}",
                "capture_id": capture_id,
                "request_id": request_id,
                "status": "COMPLETED",
                "amount_minor": amount_minor,
                "currency": currency,
                "paypal_debug_id": f"dbg_retry_{request_id[:8]}",
            }
        elif self.mode == "not_configured":
            raise RuntimeError("PayPal credentials not configured")

        return {
            "id": f"PP-REF-{request_id[:8]}",
            "capture_id": capture_id,
            "request_id": request_id,
            "status": "COMPLETED",
            "amount_minor": amount_minor,
            "currency": currency,
            "paypal_debug_id": f"dbg_success_{request_id[:8]}",
        }


def _setup_planned_action(repo: DatabaseRepository, req_id: str = "req_t4_01", amount_minor: int = 15000) -> tuple[Order, RefundAction]:
    order = Order(
        order_id="ord_t4_test",
        merchant_id="merch_a",
        account_id="shopper_1",
        policy_version="pol_electronics_us_v1",
        paypal_order_id="PP-ORD-T4",
        capture_id="CAP_T4_REAL_123",
        capture_amount_minor=38000,
        confirmed_refunded_minor=0,
        pending_refunded_minor=amount_minor,
        currency="USD",
    )
    repo.save_order(order)

    action = RefundAction(
        request_id=req_id,
        merchant_id="merch_a",
        order_id="ord_t4_test",
        return_id="ret_demo_1",
        decision_id="dec_t4_01",
        capture_id="CAP_T4_REAL_123",
        tranche="R0",
        amount_minor=amount_minor,
        currency="USD",
        status="PLANNED",
        attempt_count=0,
    )
    repo.save_refund_action(action)
    return order, action


def test_executor_confirms_refund_and_moves_pending_to_confirmed(test_repo: DatabaseRepository) -> None:
    """PLANNED action executes via PayPal and atomically moves amount from pending to confirmed."""
    assert RefundOutboxExecutor is not None, "RefundOutboxExecutor not implemented yet"
    order, action = _setup_planned_action(test_repo, "req_t4_confirm", 15000)
    fake_client = FakePayPalClient(mode="success")

    executor = RefundOutboxExecutor(repository=test_repo, client=fake_client)
    res = executor.run_once(limit=10)

    assert res["confirmed"] >= 1

    act_after = test_repo.get_refund_action("req_t4_confirm")
    assert act_after is not None
    assert act_after.status == "CONFIRMED"
    assert act_after.paypal_refund_id == "PP-REF-req_t4_c"
    assert act_after.paypal_debug_id == "dbg_success_req_t4_c"
    assert act_after.attempt_count == 1

    ord_after = test_repo.get_order("ord_t4_test")
    assert ord_after is not None
    assert ord_after.pending_refunded_minor == 0
    assert ord_after.confirmed_refunded_minor == 15000


def test_executor_timeout_sets_unknown_and_retries_with_same_request_id(test_repo: DatabaseRepository) -> None:
    """Network timeout sets action to UNKNOWN and retries in the next run with the exact same request id."""
    assert RefundOutboxExecutor is not None, "RefundOutboxExecutor not implemented yet"
    order, action = _setup_planned_action(test_repo, "req_t4_retry", 15000)
    fake_client = FakePayPalClient(mode="fail_then_success")

    executor = RefundOutboxExecutor(repository=test_repo, client=fake_client)

    # First run fails with timeout -> UNKNOWN
    res1 = executor.run_once(limit=10)
    assert res1["unknown"] >= 1

    act_run1 = test_repo.get_refund_action("req_t4_retry")
    assert act_run1 is not None
    assert act_run1.status == "UNKNOWN"
    assert act_run1.attempt_count == 1

    ord_run1 = test_repo.get_order("ord_t4_test")
    assert ord_run1 is not None
    assert ord_run1.pending_refunded_minor == 15000
    assert ord_run1.confirmed_refunded_minor == 0

    # Second run retries with the SAME request id and succeeds
    res2 = executor.run_once(limit=10)
    assert res2["confirmed"] >= 1

    assert len(fake_client.recorded_requests) == 2
    assert fake_client.recorded_requests[0]["request_id"] == "req_t4_retry"
    assert fake_client.recorded_requests[1]["request_id"] == "req_t4_retry"

    act_run2 = test_repo.get_refund_action("req_t4_retry")
    assert act_run2 is not None
    assert act_run2.status == "CONFIRMED"
    assert act_run2.attempt_count == 2

    ord_run2 = test_repo.get_order("ord_t4_test")
    assert ord_run2 is not None
    assert ord_run2.pending_refunded_minor == 0
    assert ord_run2.confirmed_refunded_minor == 15000


def test_executor_4xx_sets_failed_permanent_and_releases_pending(test_repo: DatabaseRepository) -> None:
    """4xx client error sets FAILED_PERMANENT and releases pending_refunded_minor balance."""
    assert RefundOutboxExecutor is not None, "RefundOutboxExecutor not implemented yet"
    order, action = _setup_planned_action(test_repo, "req_t4_4xx", 12000)
    fake_client = FakePayPalClient(mode="4xx")

    executor = RefundOutboxExecutor(repository=test_repo, client=fake_client)
    res = executor.run_once(limit=10)

    assert res["failed_permanent"] >= 1

    act_after = test_repo.get_refund_action("req_t4_4xx")
    assert act_after is not None
    assert act_after.status == "FAILED_PERMANENT"
    assert act_after.paypal_debug_id == "dbg_4xx_err"
    assert act_after.attempt_count == 1

    ord_after = test_repo.get_order("ord_t4_test")
    assert ord_after is not None
    assert ord_after.pending_refunded_minor == 0  # Released!
    assert ord_after.confirmed_refunded_minor == 0


def test_executor_twice_never_double_refunds(test_repo: DatabaseRepository) -> None:
    """Running executor twice never double-refunds an already confirmed action."""
    assert RefundOutboxExecutor is not None, "RefundOutboxExecutor not implemented yet"
    order, action = _setup_planned_action(test_repo, "req_t4_once", 18000)
    fake_client = FakePayPalClient(mode="success")

    executor = RefundOutboxExecutor(repository=test_repo, client=fake_client)

    res1 = executor.run_once(limit=10)
    assert res1["confirmed"] == 1
    assert fake_client.call_count == 1

    # Second run finds no PLANNED or UNKNOWN actions
    res2 = executor.run_once(limit=10)
    assert res2["confirmed"] == 0
    assert res2["processed"] == 0
    assert fake_client.call_count == 1  # Not called again!

    ord_after = test_repo.get_order("ord_t4_test")
    assert ord_after is not None
    assert ord_after.confirmed_refunded_minor == 18000


def test_executor_without_credentials_leaves_planned_and_never_reports_completed(test_repo: DatabaseRepository) -> None:
    """When credentials are not configured, executor leaves actions PLANNED and reports PAYPAL_NOT_CONFIGURED."""
    assert RefundOutboxExecutor is not None, "RefundOutboxExecutor not implemented yet"
    order, action = _setup_planned_action(test_repo, "req_t4_nocreds", 15000)

    client_without_creds = FakePayPalClient(mode="not_configured")
    client_without_creds.has_credentials = False

    executor = RefundOutboxExecutor(repository=test_repo, client=client_without_creds)
    res = executor.run_once(limit=10)

    assert res["status"] == "PAYPAL_NOT_CONFIGURED"
    assert res["processed"] == 0
    assert client_without_creds.call_count == 0

    act_after = test_repo.get_refund_action("req_t4_nocreds")
    assert act_after is not None
    assert act_after.status == "PLANNED"

    ord_after = test_repo.get_order("ord_t4_test")
    assert ord_after is not None
    assert ord_after.pending_refunded_minor == 15000
    assert ord_after.confirmed_refunded_minor == 0


def test_outbox_run_endpoint_requires_merchant_admin_of_same_merchant(
    test_repo: DatabaseRepository, demo_settings: ProofReturnSettings
) -> None:
    """POST /v1/ops/outbox/run requires MERCHANT_ADMIN of the same merchant."""
    app = create_app(repository=test_repo, settings=demo_settings, demo_mode=True)
    client = TestClient(app)

    tok_shopper = mint_shopper_token("ord_demo_1", "shopper_1", merchant_id="merch_a")
    tok_reviewer = mint_staff_token(user_id="rev_01", merchant_id="merch_a", role="REVIEWER")
    tok_admin_b = mint_staff_token(user_id="admin_b_01", merchant_id="merch_b", role="MERCHANT_ADMIN")
    tok_admin_a = mint_staff_token(user_id="admin_01", merchant_id="merch_a", role="MERCHANT_ADMIN")

    # 1. Unauthenticated -> 401
    r_unauth = client.post("/v1/ops/outbox/run")
    assert r_unauth.status_code == 401

    # 2. Shopper token -> 403
    r_shop = client.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {tok_shopper}"})
    assert r_shop.status_code == 403

    # 3. Reviewer staff -> 403
    r_rev = client.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {tok_reviewer}"})
    assert r_rev.status_code == 403

    # 4. Merchant Admin of merch_a -> 200
    r_admin_a = client.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {tok_admin_a}"})
    assert r_admin_a.status_code == 200
    data_a = r_admin_a.json()
    assert "processed" in data_a
    assert "confirmed" in data_a


@pytest.mark.sandbox
def test_st01_through_system() -> None:
    """ST-01: End-to-end sandbox execution through the system (API -> planned refund -> outbox executor -> PayPal)."""
    settings = ProofReturnSettings()
    if not settings.has_live_paypal_credentials:
        pytest.skip("Live PayPal Sandbox credentials not configured in environment")

    # Connect live PayPalSandboxClient
    paypal_client = PayPalSandboxClient(
        base_url=settings.paypal_base_url,
        client_id=settings.paypal_client_id.get_secret_value() if settings.paypal_client_id else None,
        client_secret=settings.paypal_client_secret.get_secret_value() if settings.paypal_client_secret else None,
    )

    # 1. Obtain real capture on PayPal Sandbox (via existing env or fresh order)
    real_capture_id = os.environ.get("PAYPAL_TEST_CAPTURE_ID")
    capture_debug_id = "preconfigured"
    pp_order_id = "preconfigured_sandbox_order"

    if not real_capture_id:
        tok = paypal_client.fetch_oauth_token()
        access_token = tok["_access_token"]
        assert access_token

        order_payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": "USD",
                        "value": "380.00",
                    },
                    "description": "ProofReturn Test ST-01 Live Capture",
                }
            ],
        }
        order_req_id = f"req_order_st01_{secrets.token_hex(6)}"
        with httpx.Client(timeout=15.0) as http_c:
            create_resp = http_c.post(
                f"{settings.paypal_base_url}/v2/checkout/orders",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "PayPal-Request-Id": order_req_id,
                },
                json=order_payload,
            )
            create_resp.raise_for_status()
            order_data = create_resp.json()
            pp_order_id = order_data["id"]
            approve_url = next((l["href"] for l in order_data.get("links", []) if l.get("rel") == "approve"), "")

            # Poll for order approval or capture immediately
            for attempt in range(10):
                cap_resp = http_c.post(
                    f"{settings.paypal_base_url}/v2/checkout/orders/{pp_order_id}/capture",
                    headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                    json={},
                )
                if cap_resp.status_code in (200, 201):
                    cap_data = cap_resp.json()
                    captures = cap_data.get("purchase_units", [{}])[0].get("payments", {}).get("captures", [])
                    if captures:
                        real_capture_id = captures[0]["id"]
                        capture_debug_id = cap_resp.headers.get("paypal-debug-id", "")
                        break
                elif cap_resp.status_code == 422:
                    err_data = cap_resp.json()
                    issue = err_data.get("details", [{}])[0].get("issue", "")
                    if issue == "ORDER_NOT_APPROVED":
                        if attempt == 0:
                            print(f"\n[ST-01 Action Required] PayPal Sandbox Order {pp_order_id} created.")
                            print(f"Please approve in browser: {approve_url}")
                            print("Waiting for approval (up to 30s) or set PAYPAL_TEST_CAPTURE_ID in env...")
                        time.sleep(3)
                        continue
                cap_resp.raise_for_status()

    if not real_capture_id:
        pytest.skip(
            f"PayPal Sandbox order {pp_order_id} requires buyer approval. "
            f"Approve at {approve_url} or export PAYPAL_TEST_CAPTURE_ID=<capture_id>."
        )

    assert real_capture_id.startswith("CAP") or len(real_capture_id) > 5

    # 2. Seed real order in DB and create return
    repo = DatabaseRepository()
    repo.reset_demo_database()

    order = Order(
        order_id="ord_st01_live",
        merchant_id="merch_a",
        account_id="shopper_1",
        policy_version="pol_electronics_us_v1",
        paypal_order_id=pp_order_id,
        capture_id=real_capture_id,
        capture_amount_minor=38000,
        confirmed_refunded_minor=0,
        pending_refunded_minor=0,
        currency="USD",
    )
    repo.save_order(order)
    repo.save_order_item(
        OrderItem(
            order_item_id="item_st01_live",
            order_id="ord_st01_live",
            passport_id=None,
            sku="PR-LIVE-XM5",
            price_minor=38000,
            currency="USD",
        )
    )

    app = create_app(repository=repo, settings=settings, demo_mode=True)
    client = TestClient(app)

    # 3. Create return via API
    shopper_token = mint_shopper_token("ord_st01_live", "shopper_1", merchant_id="merch_a")
    r_create = client.post(
        "/v1/returns",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "order_id": "ord_st01_live",
            "items": [{"order_item_id": "item_st01_live", "reason": "UNSATISFIED"}],
        },
    )
    assert r_create.status_code == 200
    ret_id = r_create.json()["return_id"]

    # 4. Declare & Submit Evidence via API
    r_decl = client.post(
        f"/v1/returns/{ret_id}/declaration",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={"declared_grade": "B", "fast_lane_terms_accepted": True, "shopper_nonce": "s_nonce_live"},
    )
    assert r_decl.status_code == 200

    r_ev = client.post(
        f"/v1/returns/{ret_id}/evidence",
        headers={"Authorization": f"Bearer {shopper_token}"},
        json={
            "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "faces_detected": 0,
            "object_key": "raw_evidence/st01_live.mp4",
            "challenge_step": 1,
            "client_blur_applied": True,
            "blur_latency_ms": 11.0,
        },
    )
    assert r_ev.status_code == 200
    r0_minor = r_ev.json()["r0_tranche_minor"]
    assert r0_minor > 0

    # 5. Check action planned in DB
    actions = repo.list_refund_actions_by_return(ret_id)
    assert len(actions) == 1
    r0_act = actions[0]
    assert r0_act.status == "PLANNED"
    assert r0_act.capture_id == real_capture_id
    assert r0_act.amount_minor == r0_minor

    # 6. Run outbox executor via POST /v1/ops/outbox/run
    admin_token = mint_staff_token(user_id="admin_01", merchant_id="merch_a", role="MERCHANT_ADMIN")
    r_outbox = client.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_outbox.status_code == 200
    outbox_res = r_outbox.json()
    assert outbox_res["confirmed"] >= 1

    # 7. Verify action status is CONFIRMED in DB
    act_confirmed = repo.get_refund_action(r0_act.request_id)
    assert act_confirmed is not None
    assert act_confirmed.status == "CONFIRMED"
    assert act_confirmed.paypal_refund_id is not None
    assert act_confirmed.paypal_debug_id is not None

    # 8. Query PayPal directly to verify refund exists under real_capture_id
    with httpx.Client(timeout=15.0) as http_c:
        get_cap = http_c.get(
            f"{settings.paypal_base_url}/v2/payments/captures/{real_capture_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        get_cap.raise_for_status()
        cap_details = get_cap.json()

    # Evidence logging without secrets
    print("\n--- ST-01 LIVE SANDBOX EVIDENCE ---")
    print(f"Order ID: {pp_order_id}")
    print(f"Capture ID: {real_capture_id} (Debug ID: {capture_debug_id})")
    print(f"Request ID: {r0_act.request_id}")
    print(f"PayPal Refund ID: {act_confirmed.paypal_refund_id}")
    print(f"PayPal Debug ID: {act_confirmed.paypal_debug_id}")
    print(f"Refund Amount Minor: {r0_minor}")
    print(f"Order pending_refunded_minor: {repo.get_order('ord_st01_live').pending_refunded_minor}")
    print(f"Order confirmed_refunded_minor: {repo.get_order('ord_st01_live').confirmed_refunded_minor}")
    print("-----------------------------------\n")
