"""Jurisdiction caps on diminished value, misdeclaration cost, and settlement timelines (FR-10, FR-24, FR-84, INV-11)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
JURISDICTION_TABLE_PATH = ROOT / "config" / "jurisdiction_table.json"


@dataclass(frozen=True)
class ResolvedJurisdictionRules:
    jurisdiction: str
    curve_fractions: dict[str, Fraction]
    f_minor: int
    settlement_deadline_days: int
    escalated_deadline_hold_max_days: int
    escalated_deadline_rule: str


def load_jurisdiction_table() -> dict:
    if JURISDICTION_TABLE_PATH.exists():
        return json.loads(JURISDICTION_TABLE_PATH.read_text(encoding="utf-8"))
    return {
        "default_unknown_jurisdiction": "EU",
        "jurisdictions": {},
    }


def resolve_jurisdiction_rules(
    jurisdiction: str,
    price_minor: int,
    merchant_curve: dict[str, str],
    phi: Fraction = Fraction(5, 100),
    return_shipping_minor: int = 1200,
) -> ResolvedJurisdictionRules:
    """FR-10 & FR-84 & INV-11: Resolve curve and F from jurisdiction table; unknown defaults to protective EU row."""
    table = load_jurisdiction_table()
    j_map = table.get("jurisdictions", {})
    default_code = table.get("default_unknown_jurisdiction", "EU")
    j_code = jurisdiction if jurisdiction in j_map else default_code
    row = j_map.get(j_code, {})

    caps = row.get(
        "diminished_value_caps",
        {"A": "0.00", "B": "0.00", "C": "0.20", "D": "0.50", "DEF": "0.00"},
    )
    resolved_curve: dict[str, Fraction] = {}
    for grade, raw_frac in merchant_curve.items():
        merch_r = Fraction(raw_frac)
        max_deduction = Fraction(caps.get(grade, "0.50"))
        min_allowed_r = Fraction(1, 1) - max_deduction
        # INV-11: Deduction may never exceed the jurisdiction diminished-value cap
        resolved_curve[grade] = max(merch_r, min_allowed_r)

    if row.get("r_b_override") is not None:
        resolved_curve["B"] = Fraction(row["r_b_override"])

    if row.get("misdeclaration_cost_allowed", False):
        phi_cap = min(phi, Fraction(row.get("phi_max", "0.05")))
        s_ret = int(row.get("return_shipping_minor", return_shipping_minor))
        f_minor = max(s_ret, int(Fraction(price_minor) * phi_cap))
    else:
        f_minor = 0

    return ResolvedJurisdictionRules(
        jurisdiction=j_code,
        curve_fractions=resolved_curve,
        f_minor=f_minor,
        settlement_deadline_days=int(row.get("settlement_deadline_days", 14)),
        escalated_deadline_hold_max_days=int(row.get("escalated_deadline_hold_max_days", 14)),
        escalated_deadline_rule=str(
            row.get("escalated_deadline_rule", "RELEASE_FULL_AT_STATUTORY_DEADLINE")
        ),
    )
