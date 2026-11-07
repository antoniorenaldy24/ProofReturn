"""Unit economics and Merchant ROI model with tier mix and labeled assumptions (Section 11.6, FR-79, FR-101)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RoiAssumptions:
    """Section 11.6: All parameters are explicitly labeled assumptions ('model, not measured')."""

    monthly_orders: int = 4000
    monthly_returns: int = 800
    average_order_value_usd: float = 250.0
    tier_mix_new: float = 0.80
    tier_mix_established: float = 0.15
    tier_mix_trusted: float = 0.05
    packer_wage_per_hour_usd: float = 20.0
    dock_wage_per_hour_usd: float = 22.0
    auditor_wage_per_hour_usd: float = 28.0
    avg_pack_seconds: float = 22.0
    avg_checkin_seconds: float = 30.0
    avg_audit_seconds: float = 240.0
    avg_audit_rate_p: float = 0.08
    media_storage_per_order_usd: float = 0.02
    inference_cost_per_return_usd: float = 0.09
    # ASSUMPTION(A-19): Configurable refund fee on PayPal refunds
    paypal_refund_fee_usd: float = 0.30
    appeal_handling_per_return_usd: float = 0.05
    fraud_loss_avoided_per_return_usd: float = 4.20
    recovery_uplift_per_return_usd: float = 3.50
    logistics_avoided_per_return_usd: float = 1.40
    support_contacts_avoided_per_return_usd: float = 0.90


def compute_merchant_roi(assumptions: RoiAssumptions | None = None) -> dict[str, Any]:
    """Section 11.6 formula for Cost per order, Cost per return, Benefit per return, Net benefit, and ROI."""
    a = assumptions or RoiAssumptions()

    cost_per_order = (a.avg_pack_seconds / 3600.0) * a.packer_wage_per_hour_usd + a.media_storage_per_order_usd
    cost_per_return = (
        a.inference_cost_per_return_usd
        + (a.avg_checkin_seconds / 3600.0) * a.dock_wage_per_hour_usd
        + a.avg_audit_rate_p * (a.avg_audit_seconds / 3600.0) * a.auditor_wage_per_hour_usd
        + a.paypal_refund_fee_usd
        + a.appeal_handling_per_return_usd
    )
    benefit_per_return = (
        a.fraud_loss_avoided_per_return_usd
        + a.recovery_uplift_per_return_usd
        + a.logistics_avoided_per_return_usd
        + a.support_contacts_avoided_per_return_usd
    )

    total_monthly_cost = a.monthly_orders * cost_per_order + a.monthly_returns * cost_per_return
    net_benefit_month = a.monthly_returns * (benefit_per_return - cost_per_return) - a.monthly_orders * cost_per_order
    roi_ratio = net_benefit_month / total_monthly_cost if total_monthly_cost > 0 else 0.0

    return {
        "label": "MODEL, NOT MEASURED (SIMULATED assumptions)",
        "cost_per_order_usd": round(cost_per_order, 4),
        "cost_per_return_usd": round(cost_per_return, 4),
        "benefit_per_return_usd": round(benefit_per_return, 4),
        "net_benefit_per_month_usd": round(net_benefit_month, 2),
        "roi_ratio": round(roi_ratio, 4),
        "tier_mix": {
            "NEW": a.tier_mix_new,
            "ESTABLISHED": a.tier_mix_established,
            "TRUSTED": a.tier_mix_trusted,
        },
        "assumptions": a.__dict__,
    }


if __name__ == "__main__":
    res = compute_merchant_roi()
    print("=== Merchant ROI View [MODEL, NOT MEASURED] ===")
    print(f"  Cost per order:        ${res['cost_per_order_usd']:.2f}")
    print(f"  Cost per return:       ${res['cost_per_return_usd']:.2f}")
    print(f"  Benefit per return:    ${res['benefit_per_return_usd']:.2f}")
    print(f"  Net benefit / month:   ${res['net_benefit_per_month_usd']:.2f}")
    print(f"  ROI:                   {res['roi_ratio'] * 100:.1f}%")
