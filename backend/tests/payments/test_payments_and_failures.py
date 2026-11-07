"""Tests for PayPal Payments Service, Outbox Pattern, Failure Modes FX-01..FX-20, and Reconciliation REC-01..04 (Section 24)."""

from __future__ import annotations

import pytest

from backend.payments.client import PayPalSandboxClient, validate_paypal_sandbox_url
from backend.payments.failures import simulate_failure_mode
from backend.payments.ledger import OverRefundError, RefundLedger
from backend.payments.reconciliation import run_reconciliation_suite
from backend.payments.webhooks import WebhookProcessor


@pytest.mark.req("INV-01", "INV-02", "INV-03", "INV-07", "NFR-03")
def test_refund_ledger_outbox_idempotency_and_sandbox_guard() -> None:
    """INV-01, INV-02, INV-03, INV-07, TM-16: Startup guard, deterministic request_id, and over-refund rejection."""
    # TM-16: Non-sandbox PayPal base URL must be rejected
    with pytest.raises(ValueError, match="Sandbox"):
        validate_paypal_sandbox_url("https://api-m.paypal.com")
    validate_paypal_sandbox_url("https://api-m.sandbox.paypal.com")

    # INV-07: Only allowed non-custodial operations exist on client
    client = PayPalSandboxClient(base_url="https://api-m.sandbox.paypal.com")
    assert not hasattr(client, "create_payout")

    ledger = RefundLedger()
    ledger.register_order(order_id="ord_1", merchant_id="merch_1", capture_id="cap_1", capture_amount_minor=38000)

    # INV-02: Wrong merchant or capture rejected
    with pytest.raises(ValueError, match="INV-02"):
        ledger.plan_refund_action(
            order_id="ord_1",
            merchant_id="merch_wrong",
            capture_id="cap_1",
            decision_id="dec_1",
            tranche="R0",
            amount_minor=10000,
        )

    # INV-03: Deterministic UUIDv5 request_id from (decision_id, tranche)
    act_r0 = ledger.plan_refund_action(
        order_id="ord_1",
        merchant_id="merch_1",
        capture_id="cap_1",
        decision_id="dec_1",
        tranche="R0",
        amount_minor=22157,
    )
    act_r0_dup = ledger.plan_refund_action(
        order_id="ord_1",
        merchant_id="merch_1",
        capture_id="cap_1",
        decision_id="dec_1",
        tranche="R0",
        amount_minor=22157,
    )
    assert act_r0.request_id == act_r0_dup.request_id
    assert act_r0.status == "PLANNED"

    act_checkin = ledger.plan_refund_action(
        order_id="ord_1",
        merchant_id="merch_1",
        capture_id="cap_1",
        decision_id="dec_2",
        tranche="CHECKIN",
        amount_minor=9843,
    )
    act_holdback = ledger.plan_refund_action(
        order_id="ord_1",
        merchant_id="merch_1",
        capture_id="cap_1",
        decision_id="dec_3",
        tranche="HOLDBACK",
        amount_minor=6000,
    )
    assert act_checkin.amount_minor + act_holdback.amount_minor + act_r0.amount_minor == 38000

    # INV-01: Any additional refund exceeding capture_amount_minor (38000) is rejected before calling PayPal
    with pytest.raises(OverRefundError):
        ledger.plan_refund_action(
            order_id="ord_1",
            merchant_id="merch_1",
            capture_id="cap_1",
            decision_id="dec_4",
            tranche="TOPUP",
            amount_minor=1,
        )


@pytest.mark.req("NFR-03", "NFR-04", "FR-75")
def test_all_20_financial_failure_modes_fx01_to_fx20() -> None:
    """Section 24.2: Verify handling of FX-01 through FX-20."""
    for i in range(1, 21):
        fx_id = f"FX-{i:02d}"
        res = simulate_failure_mode(fx_id)
        assert res["handled"] is True, f"{fx_id} failed: {res}"


@pytest.mark.req("NFR-04", "FR-75")
def test_webhook_deduplication_monotonicity_and_dispute_freeze() -> None:
    """NFR-04 & FR-75: Webhook verification, event_id deduplication, and dispute/reversal freeze."""
    ledger = RefundLedger()
    ledger.register_order(order_id="ord_w", merchant_id="merch_1", capture_id="cap_w", capture_amount_minor=40000)
    proc = WebhookProcessor(ledger=ledger)

    # FX-16: Invalid signature rejected
    res_bad = proc.process_webhook(event_id="ev_1", event_type="PAYMENT.CAPTURE.REFUNDED", signature_valid=False, payload={"order_id": "ord_w"})
    assert res_bad["status_code"] == 400

    # Valid dispute webhook pauses automatic tranches (FR-75)
    res_disp = proc.process_webhook(
        event_id="ev_disp_1",
        event_type="CUSTOMER.DISPUTE.CREATED",
        signature_valid=True,
        payload={"order_id": "ord_w", "dispute_id": "PP-DISP-01"},
    )
    assert res_disp["status_code"] == 200
    assert ledger.is_order_frozen("ord_w") is True

    # FX-05: Duplicate webhook delivery ignored idempotently
    res_dup = proc.process_webhook(
        event_id="ev_disp_1",
        event_type="CUSTOMER.DISPUTE.CREATED",
        signature_valid=True,
        payload={"order_id": "ord_w", "dispute_id": "PP-DISP-01"},
    )
    assert res_dup["duplicate"] is True

    # FX-19 / ST-13: Capture reversal sets remaining refundable to 0
    proc.process_webhook(
        event_id="ev_rev_1",
        event_type="PAYMENT.CAPTURE.REVERSED",
        signature_valid=True,
        payload={"order_id": "ord_w"},
    )
    assert ledger.remaining_refundable_minor("ord_w") == 0


@pytest.mark.req("NFR-14")
def test_reconciliation_jobs_rec01_to_rec04() -> None:
    """Section 24.4 & NFR-14: Verify REC-01, REC-02, REC-03, and REC-04 reconciliation checks on clean and dirty states."""
    # 1. Clean report
    clean_report = run_reconciliation_suite()
    assert clean_report["REC-01"]["passed"] is True
    assert clean_report["REC-02"]["passed"] is True
    assert clean_report["REC-03"]["passed"] is True
    assert clean_report["REC-04"]["passed"] is True

    # 2. Dirty ledger: stuck action triggers REC-01 failure
    dirty_ledger = RefundLedger()
    dirty_ledger.register_order(
        order_id="ord_rec",
        merchant_id="m_rec",
        capture_id="cap_rec",
        capture_amount_minor=10000,
    )
    act = dirty_ledger.plan_refund_action(
        order_id="ord_rec",
        merchant_id="m_rec",
        capture_id="cap_rec",
        decision_id="dec_rec",
        tranche="R0",
        amount_minor=3000,
    )
    act.status = "SUBMITTED"  # Stuck submitted action
    dirty_report = run_reconciliation_suite(dirty_ledger)
    assert dirty_report["REC-01"]["passed"] is False
    assert dirty_report["REC-01"]["stuck_actions_found"] == 1
    assert dirty_report["REC-02"]["passed"] is True


@pytest.mark.req("INV-01", "NFR-04", "FR-75")
def test_concurrency_race_condition_prevention_aud11_aud12() -> None:
    """AUD-11 & AUD-12: Concurrency lock prevents over-refund race conditions and webhook retry works after unknown order."""
    import concurrent.futures

    # 1. AUD-11: Two threads race to plan 30,000 on a 40,000 capture
    ledger = RefundLedger()
    ledger.register_order(
        order_id="ord_race",
        merchant_id="merch_1",
        capture_id="cap_race",
        capture_amount_minor=40000,
    )

    results: list[str] = []
    errors: list[Exception] = []

    def plan_refund(decision_id: str) -> None:
        try:
            act = ledger.plan_refund_action(
                order_id="ord_race",
                merchant_id="merch_1",
                capture_id="cap_race",
                decision_id=decision_id,
                tranche="R0",
                amount_minor=30000,
            )
            results.append(act.request_id)
        except Exception as exc:
            errors.append(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(plan_refund, "dec_thread_1")
        f2 = executor.submit(plan_refund, "dec_thread_2")
        f1.result()
        f2.result()

    # Exactly one succeeded and one raised OverRefundError (INV-01)
    assert len(results) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], OverRefundError)
    assert ledger.remaining_refundable_minor("ord_race") == 10000

    # 2. AUD-12: Webhook with unknown order returns 404, does NOT record event_id as seen
    proc = WebhookProcessor(ledger=ledger)
    res_unknown = proc.process_webhook(
        event_id="ev_unknown_1",
        event_type="CUSTOMER.DISPUTE.CREATED",
        signature_valid=True,
        payload={"order_id": "ord_late_registered"},
    )
    assert res_unknown["status_code"] == 404
    assert res_unknown["code"] == "ORDER_NOT_FOUND"

    # Now register the order and retry with the exact same event_id
    ledger.register_order(
        order_id="ord_late_registered",
        merchant_id="merch_1",
        capture_id="cap_late",
        capture_amount_minor=50000,
    )
    res_retry = proc.process_webhook(
        event_id="ev_unknown_1",
        event_type="CUSTOMER.DISPUTE.CREATED",
        signature_valid=True,
        payload={"order_id": "ord_late_registered"},
    )
    assert res_retry["status_code"] == 200
    assert res_retry["duplicate"] is False
    assert ledger.is_order_frozen("ord_late_registered") is True


@pytest.mark.sandbox
@pytest.mark.req("NFR-03", "INV-03", "INV-07")
def test_paypal_sandbox_live_oauth_and_idempotent_order() -> None:
    """ST-09 & NFR-03: Verify live PayPal Sandbox OAuth and idempotent Order v2 creation via PayPal-Request-Id."""
    from backend.config import ProofReturnSettings
    from backend.payments.ledger import compute_deterministic_request_id

    settings = ProofReturnSettings()
    if not settings.has_live_paypal_credentials:
        pytest.skip("Live PayPal Sandbox credentials not configured; skipping live call.")

    client = PayPalSandboxClient(
        base_url=settings.paypal_base_url,
        client_id=settings.paypal_client_id.get_secret_value(),
        client_secret=settings.paypal_client_secret.get_secret_value(),
    )
    tok = client.fetch_oauth_token()
    assert tok["access_token_present"] is True

    req_id = compute_deterministic_request_id("dec_sandbox_st09", "ORDER_CREATE")
    ord_1 = client.create_order_live(
        custom_id="ord_st09_demo",
        request_id=req_id,
        amount_minor=38000,
    )
    ord_2 = client.create_order_live(
        custom_id="ord_st09_demo",
        request_id=req_id,
        amount_minor=38000,
    )
    assert ord_1["status"] == "CREATED"
    assert ord_1["id"] == ord_2["id"]

