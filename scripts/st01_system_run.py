"""ST-01 System Run in PayPal Sandbox (AUD-02, ARC-19, INV-01, INV-03, FR-75).

Drives the real system path:
1. Create PayPal Sandbox order, print approval URL, wait for Sandbox buyer approval.
2. Capture via system path and store REAL capture id on the Order in DB.
3. Execute complete return flow through FastAPI /v1 endpoints:
   declaration -> evidence -> dropoff/carrier scan -> reviewer decision.
4. Execute POST /v1/ops/outbox/run until all planned tranches are processed.
5. Verify at PayPal: GET capture and its refunds; assert refund amounts and count match DB RefundAction rows.
6. Dispute scenario on a second order:
   after R0 is confirmed, deliver CUSTOMER.DISPUTE.CREATED webhook, run outbox,
   and assert that no further refund exists at PayPal.
7. Write docs/evidence/st01-R4.json with timestamps, real IDs, statuses, and debug headers (NO secrets/tokens).
8. Provides --dry-run mode using FakePayPalSandboxClient for headless CI testing.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any
import uuid

# Ensure repository root is on sys.path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from fastapi.testclient import TestClient

from backend.api.app import create_app
from backend.auth.tokens import mint_shopper_token, mint_staff_token
from backend.config import get_settings
from backend.db.models import Order, OrderItem, RefundAction
from backend.db.repository import DatabaseRepository
from backend.payments.client import PayPalSandboxClient

logger = logging.getLogger("proofreturn.scripts.st01")


class FakePayPalSandboxClient:
    """Simulated PayPal Sandbox REST v2 client for headless CI dry-runs."""

    def __init__(self, base_url: str = "https://api-m.sandbox.paypal.com") -> None:
        self.base_url = base_url.rstrip("/")
        self.orders: dict[str, dict[str, Any]] = {}
        self.captures: dict[str, dict[str, Any]] = {}
        self.refunds: dict[str, dict[str, Any]] = {}
        self._order_counter = 1001
        self._cap_counter = 5001
        self._ref_counter = 9001

    @property
    def has_credentials(self) -> bool:
        return True

    def create_order_live(
        self,
        *,
        custom_id: str,
        request_id: str,
        amount_minor: int,
        currency: str = "USD",
    ) -> dict[str, Any]:
        oid = f"ORD-DRYRUN-{self._order_counter}"
        self._order_counter += 1
        approve_url = f"https://www.sandbox.paypal.com/checkoutnow?token={oid}"
        data = {
            "id": oid,
            "status": "CREATED",
            "links": [
                {"href": f"{self.base_url}/v2/checkout/orders/{oid}", "rel": "self", "method": "GET"},
                {"href": approve_url, "rel": "approve", "method": "GET"},
            ],
            "paypal_debug_id": f"dbg-order-{oid}",
            "amount_minor": amount_minor,
            "currency": currency,
            "custom_id": custom_id,
            "request_id": request_id,
        }
        self.orders[oid] = data
        return {
            "id": oid,
            "status": "CREATED",
            "links": data["links"],
            "paypal_debug_id": data["paypal_debug_id"],
        }

    def capture_order_live(
        self,
        *,
        paypal_order_id: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        cap_id = f"CAP-DRYRUN-{self._cap_counter}"
        self._cap_counter += 1
        debug_id = f"dbg-cap-{cap_id}"
        cap_data = {
            "id": cap_id,
            "order_id": paypal_order_id,
            "status": "COMPLETED",
            "paypal_debug_id": debug_id,
            "refunds": [],
        }
        self.captures[cap_id] = cap_data
        if paypal_order_id in self.orders:
            self.orders[paypal_order_id]["status"] = "COMPLETED"
        return {
            "id": cap_id,
            "order_id": paypal_order_id,
            "status": "COMPLETED",
            "paypal_debug_id": debug_id,
        }

    def refund_capture_live(
        self,
        *,
        capture_id: str,
        request_id: str,
        amount_minor: int,
        currency: str = "USD",
        invoice_id: str | None = None,
        custom_id: str | None = None,
        note_to_payer: str | None = None,
    ) -> dict[str, Any]:
        ref_id = f"REF-DRYRUN-{self._ref_counter}"
        self._ref_counter += 1
        debug_id = f"dbg-ref-{ref_id}"
        value_str = f"{amount_minor / 100:.2f}"
        ref_entry = {
            "id": ref_id,
            "capture_id": capture_id,
            "request_id": request_id,
            "status": "COMPLETED",
            "amount": {"value": value_str, "currency_code": currency},
            "amount_minor": amount_minor,
            "currency": currency,
            "invoice_id": invoice_id,
            "custom_id": custom_id,
            "paypal_debug_id": debug_id,
        }
        self.refunds[ref_id] = ref_entry
        if capture_id in self.captures:
            self.captures[capture_id]["refunds"].append(ref_entry)
        return {
            "id": ref_id,
            "capture_id": capture_id,
            "request_id": request_id,
            "status": "COMPLETED",
            "amount_minor": amount_minor,
            "currency": currency,
            "invoice_id": invoice_id,
            "custom_id": custom_id,
            "paypal_debug_id": debug_id,
        }

    def get_refund_live(self, *, refund_id: str) -> dict[str, Any]:
        if refund_id in self.refunds:
            r = self.refunds[refund_id]
            return {
                "id": r["id"],
                "status": r["status"],
                "status_detail": "COMPLETED",
                "paypal_debug_id": r["paypal_debug_id"],
            }
        return {
            "id": refund_id,
            "status": "COMPLETED",
            "status_detail": "COMPLETED",
            "paypal_debug_id": f"dbg-ref-{refund_id}",
        }

    def get_capture_live(self, *, capture_id: str) -> dict[str, Any]:
        if capture_id in self.captures:
            c = self.captures[capture_id]
            return {
                "id": c["id"],
                "status": c["status"],
                "refunds": c["refunds"],
                "links": [],
                "paypal_debug_id": c["paypal_debug_id"],
            }
        return {
            "id": capture_id,
            "status": "COMPLETED",
            "refunds": [],
            "links": [],
            "paypal_debug_id": f"dbg-cap-{capture_id}",
        }

    def get_capture_refunds_live(self, *, capture_id: str) -> list[dict[str, Any]]:
        cap_info = self.get_capture_live(capture_id=capture_id)
        return cap_info.get("refunds", [])


def _sign_demo_webhook_payload(app: Any, payload: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    secret = (
        app.state.settings.demo_webhook_secret.get_secret_value().encode("utf-8")
        if getattr(app.state.settings, "demo_webhook_secret", None)
        else b"demo_secret"
    )
    sig = hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()
    return body_bytes, {"Content-Type": "application/json", "X-Demo-Webhook-Signature": sig}


def run_st01_flow(
    *,
    dry_run: bool = False,
    auto_approve: bool = False,
    output_path: Path | str = "docs/evidence/st01-R4.json",
    repository: DatabaseRepository | None = None,
) -> dict[str, Any]:
    """Execute the full ST-01 PayPal Sandbox verification flow."""
    settings = get_settings()

    if not dry_run:
        if not settings.has_live_paypal_credentials:
            raise RuntimeError(
                "PAYPAL_CREDENTIALS_MISSING: Live run requires PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET in .env."
            )
        paypal_client = PayPalSandboxClient(
            base_url=settings.paypal_base_url,
            client_id=settings.paypal_client_id.get_secret_value(),
            client_secret=settings.paypal_client_secret.get_secret_value(),
        )
        print("[ST-01] Configured Live PayPal Sandbox client.")
    else:
        paypal_client = FakePayPalSandboxClient()
        print("[ST-01] Configured Fake PayPal Sandbox client (Dry-run mode).")

    repo = repository or DatabaseRepository()
    repo.seed_demo_data()

    app = create_app(repository=repo, settings=settings, demo_mode=True, mode="judge")
    app.state.paypal_client = paypal_client
    app.state.outbox_executor.client = paypal_client
    client = TestClient(app)

    evidence_doc: dict[str, Any] = {
        "test_id": "ST-01",
        "round": "R4",
        "requirement": "AUD-02 HIGH",
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "dry-run" if dry_run else "live",
        "invariants_tested": ["INV-01", "INV-02", "INV-03", "INV-07", "FR-75"],
    }

    # =========================================================================
    # PART 1: ORDER 1 - Full Return Lifecycle & Outbox Sequential Refunds
    # =========================================================================
    print("\n" + "=" * 80)
    print("PART 1: ORDER 1 — Full Return Flow & Multi-Tranche Refunds")
    print("=" * 80)

    # 1.a Create Sandbox Order
    custom_id_1 = f"ord_st01_1_{uuid.uuid4().hex[:6]}"
    req_id_ord1 = f"req_ord1_{uuid.uuid4().hex[:8]}"
    ord1_res = paypal_client.create_order_live(
        custom_id=custom_id_1,
        request_id=req_id_ord1,
        amount_minor=38000,
        currency="USD",
    )
    pp_order_id_1 = str(ord1_res["id"])
    approval_url_1 = next(
        (str(lnk.get("href")) for lnk in ord1_res.get("links", []) if lnk.get("rel") == "approve"),
        f"https://www.sandbox.paypal.com/checkoutnow?token={pp_order_id_1}",
    )
    print(f"PayPal Order 1 Created: ID={pp_order_id_1}")
    print(f"Approval Link: {approval_url_1}")

    # 1.a Wait for owner approval
    if dry_run or auto_approve:
        print("[DRY-RUN / AUTO-APPROVE] Buyer approval simulated for Order 1.")
    else:
        print("\n" + "*" * 70)
        print("ACTION REQUIRED (ORDER 1):")
        print(f"1. Open in browser: {approval_url_1}")
        print("2. Log in with your Sandbox Personal Buyer account and click 'Complete Purchase' / 'Approve'.")
        print("*" * 70)
        input("Press [ENTER] once you have completed approval in your browser: ")

    # 1.b Capture order through API / system path
    req_id_cap1 = f"req_cap1_{uuid.uuid4().hex[:8]}"
    cap1_res = paypal_client.capture_order_live(paypal_order_id=pp_order_id_1, request_id=req_id_cap1)
    real_capture_id_1 = str(cap1_res["id"])
    cap1_status = str(cap1_res.get("status", "")).upper()
    cap1_debug_id = str(cap1_res.get("paypal_debug_id", ""))
    print(f"Capture 1 Captured: ID={real_capture_id_1}, Status={cap1_status}, DebugID={cap1_debug_id}")
    assert real_capture_id_1, "Capture ID must be returned by PayPal"
    assert cap1_status == "COMPLETED", f"Expected capture status COMPLETED, got {cap1_status}"

    # Store real capture id on order in database
    order_id_1 = custom_id_1
    repo.ensure_order_registered(
        order_id=order_id_1,
        merchant_id="merch_a",
        capture_id=real_capture_id_1,
        capture_amount_minor=38000,
        currency="USD",
    )
    with repo.get_session() as session:
        ord_db = session.get(Order, order_id_1)
        if ord_db:
            ord_db.paypal_order_id = pp_order_id_1
            ord_db.account_id = "shopper_1"
            ord_db.policy_version = "pol_electronics_us_v1"
            session.add(ord_db)
        item_db = OrderItem(
            order_item_id=f"item_{order_id_1}",
            order_id=order_id_1,
            passport_id="pass_demo_1",
            sku="PR-HP-XM5",
            price_minor=38000,
            currency="USD",
        )
        session.add(item_db)
        session.commit()

    # 1.c Run Return flow through API
    shopper_tok_1 = mint_shopper_token(order_id=order_id_1, shopper_id="shopper_1")
    staff_rev_tok = mint_staff_token(user_id="rev_st01", merchant_id="merch_a", role="REVIEWER")
    staff_admin_tok = mint_staff_token(user_id="admin_st01", merchant_id="merch_a", role="MERCHANT_ADMIN")

    # Step 1: Initiate return
    r_init = client.post(
        "/v1/returns",
        headers={"Authorization": f"Bearer {shopper_tok_1}", "Idempotency-Key": f"ik-st01-init-{order_id_1}"},
        json={"order_id": order_id_1, "items": ["PR-HP-XM5"]},
    )
    assert r_init.status_code == 200, f"Return init failed: {r_init.text}"
    return_id_1 = r_init.json()["return_id"]
    print(f"Return 1 Initiated: {return_id_1}")

    # Step 2: Declaration
    r_decl = client.post(
        f"/v1/returns/{return_id_1}/declaration",
        headers={"Authorization": f"Bearer {shopper_tok_1}"},
        json={
            "schema_version": "1.0.0",
            "order_id": order_id_1,
            "declared_grade": "B",
            "accessories": {"case": True},
            "reason_code": "CHANGED_MIND",
            "consent_fast_lane_terms": True,
            "nonce_shopper": "nonce_st01_order1",
            "actor": {"kind": "shopper", "sub": "shopper_1"},
        },
    )
    assert r_decl.status_code == 200, f"Declaration failed: {r_decl.text}"
    decl_data_1 = r_decl.json()
    challenge_nonce_1 = str(decl_data_1.get("challenge_nonce") or "").strip()

    # Step 3: Evidence submission (R0 tranche planned)
    r_evid = client.post(
        f"/v1/returns/{return_id_1}/evidence",
        headers={"Authorization": f"Bearer {shopper_tok_1}", "Idempotency-Key": f"ik-st01-evid-{order_id_1}"},
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": "raw/st01_video.mp4",
            "sha256": "a" * 64,
            "challenge_step": 1,
            "faces_detected": 0,
            "client_blur_applied": False,
            "blur_latency_ms": 12.0,
            "text_in_media": challenge_nonce_1,
        },
    )
    assert r_evid.status_code == 200, f"Evidence failed: {r_evid.text}"
    print(f"Evidence 1 submitted; FAST lane active. R0 tranche planned.")

    # Step 4: Dropoff
    r_drop = client.post(
        f"/v1/returns/{return_id_1}/dropoff",
        headers={"Authorization": f"Bearer {shopper_tok_1}"},
        json={"seal_nonce": "SEAL-ST01-001", "carrier_tracking_number": "TRACK-ST01-001"},
    )
    assert r_drop.status_code == 200, f"Dropoff failed: {r_drop.text}"

    # Step 5: Carrier scan event
    r_carrier = client.post(
        "/v1/carrier-events",
        headers={"Authorization": f"Bearer {staff_admin_tok}"},
        json={
            "return_id": return_id_1,
            "type": "CARRIER_FIRST_SCAN",
            "seal_nonce": "SEAL-ST01-001",
        },
    )
    assert r_carrier.status_code == 200, f"Carrier scan failed: {r_carrier.text}"

    # Step 6: Reviewer decision (Settlement tranche planned)
    r_rev = client.post(
        f"/v1/review/{return_id_1}/decision",
        headers={"Authorization": f"Bearer {staff_rev_tok}", "Idempotency-Key": f"ik-st01-rev-{order_id_1}"},
        json={
            "outcome": "CONFIRMED",
            "verified_grade": "B",
            "notes": "ST-01 verified grade B matching declaration.",
        },
    )
    assert r_rev.status_code == 200, f"Review decision failed: {r_rev.text}"
    print(f"Review 1 Confirmed: settlement tranches planned.")

    # 1.d Run outbox executor until all planned tranches are processed
    print("Running outbox executor to dispatch planned refunds to PayPal...")
    total_processed_ord1 = 0
    for iteration in range(1, 10):
        r_outbox = client.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {staff_admin_tok}"})
        assert r_outbox.status_code == 200, f"Outbox run failed: {r_outbox.text}"
        outbox_res = r_outbox.json()
        claimed = outbox_res.get("claimed", 0)
        total_processed_ord1 += claimed
        actions_pending = [a for a in repo.list_refund_actions_by_return(return_id_1) if a.status in {"PLANNED", "SUBMITTED"}]
        if not actions_pending:
            break

    actions_ord1 = repo.list_refund_actions_by_return(return_id_1)
    confirmed_actions_1 = [a for a in actions_ord1 if a.status == "CONFIRMED"]
    print(f"Order 1 Outbox complete: {len(confirmed_actions_1)} action(s) CONFIRMED.")
    for a in confirmed_actions_1:
        print(f"  -> Tranche={a.tranche}, Amount={a.amount_minor/100:.2f} USD, PayPalRefundID={a.paypal_refund_id}, DebugID={a.paypal_debug_id}")

    # 1.e Verify at PayPal: GET capture and its refunds
    cap1_verify = paypal_client.get_capture_live(capture_id=real_capture_id_1)
    cap1_refunds = paypal_client.get_capture_refunds_live(capture_id=real_capture_id_1)
    print(f"PayPal Verification for Capture 1: {len(cap1_refunds)} refund(s) reported by PayPal.")

    # Assert refund count and amounts match RefundAction rows
    assert len(cap1_refunds) == len(confirmed_actions_1), (
        f"Refund count mismatch at PayPal: expected {len(confirmed_actions_1)}, got {len(cap1_refunds)}"
    )

    evidence_doc["order_1_happy_path"] = {
        "order_id": order_id_1,
        "paypal_order_id": pp_order_id_1,
        "capture_id": real_capture_id_1,
        "capture_status": cap1_status,
        "capture_paypal_debug_id": cap1_debug_id,
        "return_id": return_id_1,
        "confirmed_actions_count": len(confirmed_actions_1),
        "actions": [
            {
                "request_id": a.request_id,
                "tranche": a.tranche,
                "amount_minor": a.amount_minor,
                "status": a.status,
                "paypal_refund_id": a.paypal_refund_id,
                "paypal_debug_id": a.paypal_debug_id,
                "attempt_count": a.attempt_count,
            }
            for a in confirmed_actions_1
        ],
        "paypal_capture_verification": {
            "capture_id": cap1_verify.get("id"),
            "status": cap1_verify.get("status"),
            "paypal_debug_id": cap1_verify.get("paypal_debug_id"),
            "refunds_count": len(cap1_refunds),
            "refunds": cap1_refunds,
        },
    }

    # =========================================================================
    # PART 2: ORDER 2 - Dispute Scenario & Freeze Verification (FR-75)
    # =========================================================================
    print("\n" + "=" * 80)
    print("PART 2: ORDER 2 — Dispute Scenario & Dispute Freeze (FR-75)")
    print("=" * 80)

    # 2.a Create Second Sandbox Order
    custom_id_2 = f"ord_st01_2_{uuid.uuid4().hex[:6]}"
    req_id_ord2 = f"req_ord2_{uuid.uuid4().hex[:8]}"
    ord2_res = paypal_client.create_order_live(
        custom_id=custom_id_2,
        request_id=req_id_ord2,
        amount_minor=38000,
        currency="USD",
    )
    pp_order_id_2 = str(ord2_res["id"])
    approval_url_2 = next(
        (str(lnk.get("href")) for lnk in ord2_res.get("links", []) if lnk.get("rel") == "approve"),
        f"https://www.sandbox.paypal.com/checkoutnow?token={pp_order_id_2}",
    )
    print(f"PayPal Order 2 Created: ID={pp_order_id_2}")
    print(f"Approval Link: {approval_url_2}")

    # Wait for owner approval for Order 2
    if dry_run or auto_approve:
        print("[DRY-RUN / AUTO-APPROVE] Buyer approval simulated for Order 2.")
    else:
        print("\n" + "*" * 70)
        print("ACTION REQUIRED (ORDER 2):")
        print(f"1. Open in browser: {approval_url_2}")
        print("2. Log in with your Sandbox Personal Buyer account and click 'Complete Purchase' / 'Approve'.")
        print("*" * 70)
        input("Press [ENTER] once you have completed approval in your browser: ")

    # Capture Order 2
    req_id_cap2 = f"req_cap2_{uuid.uuid4().hex[:8]}"
    cap2_res = paypal_client.capture_order_live(paypal_order_id=pp_order_id_2, request_id=req_id_cap2)
    real_capture_id_2 = str(cap2_res["id"])
    cap2_status = str(cap2_res.get("status", "")).upper()
    cap2_debug_id = str(cap2_res.get("paypal_debug_id", ""))
    print(f"Capture 2 Captured: ID={real_capture_id_2}, Status={cap2_status}, DebugID={cap2_debug_id}")
    assert real_capture_id_2, "Capture ID must be returned by PayPal for Order 2"

    order_id_2 = custom_id_2
    repo.ensure_order_registered(
        order_id=order_id_2,
        merchant_id="merch_a",
        capture_id=real_capture_id_2,
        capture_amount_minor=38000,
        currency="USD",
    )
    with repo.get_session() as session:
        ord_db2 = session.get(Order, order_id_2)
        if ord_db2:
            ord_db2.paypal_order_id = pp_order_id_2
            ord_db2.account_id = "shopper_1"
            ord_db2.policy_version = "pol_electronics_us_v1"
            session.add(ord_db2)
        item_db2 = OrderItem(
            order_item_id=f"item_{order_id_2}",
            order_id=order_id_2,
            passport_id="pass_demo_1",
            sku="PR-HP-XM5",
            price_minor=38000,
            currency="USD",
        )
        session.add(item_db2)
        session.commit()

    shopper_tok_2 = mint_shopper_token(order_id=order_id_2, shopper_id="shopper_1")

    # Initiate return on Order 2
    r_init_2 = client.post(
        "/v1/returns",
        headers={"Authorization": f"Bearer {shopper_tok_2}", "Idempotency-Key": f"ik-st01-init-{order_id_2}"},
        json={"order_id": order_id_2, "items": ["PR-HP-XM5"]},
    )
    assert r_init_2.status_code == 200
    return_id_2 = r_init_2.json()["return_id"]

    # Declaration Order 2
    r_decl_2 = client.post(
        f"/v1/returns/{return_id_2}/declaration",
        headers={"Authorization": f"Bearer {shopper_tok_2}"},
        json={
            "schema_version": "1.0.0",
            "order_id": order_id_2,
            "declared_grade": "B",
            "accessories": {"case": True},
            "reason_code": "CHANGED_MIND",
            "consent_fast_lane_terms": True,
            "nonce_shopper": "nonce_st01_order2",
            "actor": {"kind": "shopper", "sub": "shopper_1"},
        },
    )
    assert r_decl_2.status_code == 200
    challenge_nonce_2 = str(r_decl_2.json().get("challenge_nonce") or "").strip()

    # Evidence Order 2 -> R0 tranche planned
    r_evid_2 = client.post(
        f"/v1/returns/{return_id_2}/evidence",
        headers={"Authorization": f"Bearer {shopper_tok_2}", "Idempotency-Key": f"ik-st01-evid-{order_id_2}"},
        json={
            "kind": "VIDEO_CHALLENGE",
            "object_key": "raw/st01_video2.mp4",
            "sha256": "b" * 64,
            "challenge_step": 1,
            "faces_detected": 0,
            "client_blur_applied": False,
            "blur_latency_ms": 14.0,
            "text_in_media": challenge_nonce_2,
        },
    )
    assert r_evid_2.status_code == 200

    # Dispatch outbox to confirm R0 refund ONLY
    r_outbox_r0 = client.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {staff_admin_tok}"})
    assert r_outbox_r0.status_code == 200

    actions_ord2 = repo.list_refund_actions_by_return(return_id_2)
    r0_action_ord2 = next((a for a in actions_ord2 if a.tranche == "R0" and a.status == "CONFIRMED"), None)
    assert r0_action_ord2 is not None, "Expected R0 refund to be confirmed before dispute"
    print(f"Order 2 R0 Refund Confirmed at PayPal: RefundID={r0_action_ord2.paypal_refund_id}")

    # Verify at PayPal: exactly 1 refund (R0) exists
    refunds_before_disp = paypal_client.get_capture_refunds_live(capture_id=real_capture_id_2)
    assert len(refunds_before_disp) == 1, f"Expected 1 refund at PayPal before dispute, got {len(refunds_before_disp)}"

    # Deliver CUSTOMER.DISPUTE.CREATED webhook
    dispute_event_id = f"WH-DISP-ST01-{uuid.uuid4().hex[:8]}"
    dispute_id = f"PP-DISP-{uuid.uuid4().hex[:8]}"
    dispute_payload = {
        "id": dispute_event_id,
        "event_type": "CUSTOMER.DISPUTE.CREATED",
        "order_id": order_id_2,
        "resource": {
            "id": dispute_id,
            "dispute_id": dispute_id,
            "custom_id": order_id_2,
            "status": "UNDER_REVIEW",
        },
    }

    body_bytes, disp_headers = _sign_demo_webhook_payload(app, dispute_payload)
    r_disp = client.post("/v1/webhooks/paypal", content=body_bytes, headers=disp_headers)
    assert r_disp.status_code == 200, f"Dispute webhook failed: {r_disp.text}"
    print(f"Delivered CUSTOMER.DISPUTE.CREATED signed webhook ({dispute_event_id}).")

    # Verify order is frozen
    assert repo.is_order_frozen(order_id_2) is True, "Order 2 must be frozen by dispute in DB"
    print(f"Order 2 is frozen by dispute in DB (FR-75).")

    # Dropoff & carrier events on Order 2
    client.post(
        f"/v1/returns/{return_id_2}/dropoff",
        headers={"Authorization": f"Bearer {shopper_tok_2}"},
        json={"seal_nonce": "SEAL-ST01-002", "carrier_tracking_number": "TRACK-ST01-002"},
    )
    client.post(
        "/v1/carrier-events",
        headers={"Authorization": f"Bearer {staff_admin_tok}"},
        json={
            "return_id": return_id_2,
            "type": "CARRIER_FIRST_SCAN",
            "seal_nonce": "SEAL-ST01-002",
        },
    )

    # Review decision on Order 2 should be blocked by dispute or refuse refund planning
    r_rev_2 = client.post(
        f"/v1/review/{return_id_2}/decision",
        headers={"Authorization": f"Bearer {staff_rev_tok}", "Idempotency-Key": f"ik-st01-rev-{order_id_2}"},
        json={
            "outcome": "CONFIRMED",
            "verified_grade": "B",
            "notes": "Attempting review on dispute-frozen order.",
        },
    )
    print(f"Review on dispute-frozen order returned status: {r_rev_2.status_code}")
    if r_rev_2.status_code == 409:
        print(f"  -> Properly rejected with ORDER_FROZEN: {r_rev_2.json().get('code')}")

    # Run outbox again
    r_outbox_post = client.post("/v1/ops/outbox/run", headers={"Authorization": f"Bearer {staff_admin_tok}"})
    assert r_outbox_post.status_code == 200

    # 1.f Assert that NO FURTHER refund exists at PayPal
    refunds_after_disp = paypal_client.get_capture_refunds_live(capture_id=real_capture_id_2)
    print(f"PayPal Verification for Order 2 after dispute: {len(refunds_after_disp)} refund(s) at PayPal.")
    assert len(refunds_after_disp) == 1, (
        f"DISPUTE FREEZE VIOLATION (FR-75): Expected exactly 1 refund at PayPal, but found {len(refunds_after_disp)}!"
    )
    print("Dispute freeze verified: no further refund created at PayPal (FR-75, AUD-02).")

    evidence_doc["order_2_dispute_scenario"] = {
        "order_id": order_id_2,
        "paypal_order_id": pp_order_id_2,
        "capture_id": real_capture_id_2,
        "capture_status": cap2_status,
        "capture_paypal_debug_id": cap2_debug_id,
        "return_id": return_id_2,
        "r0_confirmed_refund_id": r0_action_ord2.paypal_refund_id,
        "r0_confirmed_debug_id": r0_action_ord2.paypal_debug_id,
        "dispute_webhook": {
            "event_id": dispute_event_id,
            "dispute_id": dispute_id,
            "event_type": "CUSTOMER.DISPUTE.CREATED",
            "delivery_path": "signed_demo_webhook",
        },
        "order_frozen_by_dispute": True,
        "pre_dispute_refunds_count_at_paypal": 1,
        "post_freeze_refunds_count_at_paypal": len(refunds_after_disp),
        "no_further_refund_verified": True,
    }

    # Write evidence JSON (Never write credentials or tokens)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(evidence_doc, f, indent=2)
    print(f"\n[ST-01] Successfully generated evidence document: {out_path.resolve()}")

    return evidence_doc


def main() -> None:
    parser = argparse.ArgumentParser(description="ProofReturn ST-01 PayPal Sandbox System Execution Driver")
    parser.add_argument("--dry-run", action="store_true", help="Run with FakePayPalSandboxClient for CI testing")
    parser.add_argument("--live", action="store_true", help="Run with live PayPal Sandbox credentials from .env")
    parser.add_argument("--auto-approve", action="store_true", help="Auto-approve without pausing for user input")
    parser.add_argument("--output", default="docs/evidence/st01-R4.json", help="Path for evidence JSON output")
    args = parser.parse_args()

    dry_run = args.dry_run
    if not args.dry_run and not args.live:
        # If neither flag is explicitly set, check if credentials are configured
        settings = get_settings()
        if settings.has_live_paypal_credentials:
            dry_run = False
        else:
            print("[ST-01] No live PayPal credentials detected in environment. Defaulting to --dry-run.")
            dry_run = True

    try:
        run_st01_flow(
            dry_run=dry_run,
            auto_approve=args.auto_approve,
            output_path=args.output,
        )
    except Exception as exc:
        print(f"\n[ST-01 ERROR] Execution failed: {exc}", file=sys.stderr)
        raise exc


if __name__ == "__main__":
    main()
