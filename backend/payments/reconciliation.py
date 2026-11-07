"""Reconciliation Jobs REC-01..REC-04 (Section 24.4, NFR-14)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.payments.ledger import RefundLedger


def run_reconciliation_suite(
    ledger: RefundLedger | None = None,
    *,
    webhooks: list[dict[str, Any]] | None = None,
    external_reported_totals: dict[str, int] | None = None,
) -> dict[str, dict[str, Any]]:
    """Run all 4 reconciliation checks (REC-01..REC-04) against live/provided ledger state."""
    # REC-01: Stuck Refund Action Sweeper (Section 24.4: SUBMITTED/UNKNOWN/IN_FLIGHT)
    stuck_actions_count = 0
    if ledger is not None:
        for action in ledger._actions_by_request_id.values():
            if action.status in {"SUBMITTED", "UNKNOWN", "IN_FLIGHT"}:
                stuck_actions_count += 1
    rec01_passed = stuck_actions_count == 0

    # REC-02: Order-Level Refund Total Audit (Section 24.4: sum of CONFIRMED <= capture, INV-01)
    invariant_violations = 0
    if ledger is not None:
        for order in ledger._orders.values():
            actions = ledger._actions_by_order.get(order.order_id, [])
            confirmed_sum = sum(
                a.amount_minor for a in actions if a.status == "CONFIRMED"
            )
            if confirmed_sum > order.capture_amount_minor:
                invariant_violations += 1
    rec02_passed = invariant_violations == 0

    # REC-03: Webhook Delivery Gap Detector (Section 24.4: CONFIRMED actions have matching webhooks)
    missing_webhooks_count = 0
    if ledger is not None and webhooks is not None:
        received_refund_ids = set()
        for wh in webhooks:
            if not wh.get("signature_valid", True):
                continue
            payload = wh.get("payload", {})
            r_id = payload.get("refund_id") or payload.get("id") or wh.get("resource", {}).get("id")
            if r_id:
                received_refund_ids.add(r_id)

        for action in ledger._actions_by_request_id.values():
            if action.status == "CONFIRMED" and action.paypal_refund_id:
                if action.paypal_refund_id not in received_refund_ids:
                    missing_webhooks_count += 1
    rec03_passed = missing_webhooks_count == 0

    # REC-04: Daily Settlement & Holdback Report (Section 24.4)
    discrepancy_minor = 0
    if ledger is not None and external_reported_totals is not None:
        ledger_totals_by_merchant: dict[str, int] = {}
        for action in ledger._actions_by_request_id.values():
            if action.status == "CONFIRMED":
                ledger_totals_by_merchant[action.merchant_id] = (
                    ledger_totals_by_merchant.get(action.merchant_id, 0) + action.amount_minor
                )
        for merch_id, ext_total in external_reported_totals.items():
            ledg_total = ledger_totals_by_merchant.get(merch_id, 0)
            diff = abs(ledg_total - ext_total)
            discrepancy_minor += diff
    rec04_passed = discrepancy_minor == 0

    return {
        "REC-01": {
            "job": "Stuck Refund Action Sweeper",
            "cadence": "Every 2 minutes",
            "stuck_actions_found": stuck_actions_count,
            "passed": rec01_passed,
        },
        "REC-02": {
            "job": "Order-Level Refund Total Audit",
            "cadence": "Every 10 minutes",
            "invariant_violations": invariant_violations,
            "passed": rec02_passed,
        },
        "REC-03": {
            "job": "Webhook Delivery Gap Detector",
            "cadence": "Hourly",
            "missing_webhooks_reconciled": missing_webhooks_count,
            "passed": rec03_passed,
        },
        "REC-04": {
            "job": "Daily Settlement & Holdback Report",
            "cadence": "Daily / on-demand via CLI",
            "discrepancy_minor": discrepancy_minor,
            "passed": rec04_passed,
        },
    }
