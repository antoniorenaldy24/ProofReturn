"""Jurisdiction caps on diminished value, misdeclaration cost, and settlement timelines (FR-10, FR-24, FR-84, INV-11, RV3-06)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
JURISDICTION_TABLE_PATH = ROOT / "config" / "jurisdiction_table.json"


class JurisdictionCapViolationError(ValueError):
    """Typed error raised when a policy curve or fee violates SSOT jurisdiction caps (RV3-06, INV-11, FR-10)."""

    def __init__(self, message: str, *, field: str = "curve", jurisdiction: str = "") -> None:
        super().__init__(message)
        self.field = field
        self.jurisdiction = jurisdiction
        self.errors: list[dict[str, str]] = [{"field": field, "message": message}]


@dataclass(frozen=True)
class ResolvedJurisdictionRules:
    jurisdiction: str
    curve_fractions: dict[str, Fraction]
    f_minor: int
    settlement_deadline_days: int
    escalated_deadline_hold_max_days: int
    escalated_deadline_rule: str


def load_jurisdiction_table() -> dict[str, Any]:
    if JURISDICTION_TABLE_PATH.exists():
        return json.loads(JURISDICTION_TABLE_PATH.read_text(encoding="utf-8"))
    return {
        "default_unknown_jurisdiction": "EU",
        "jurisdictions": {},
    }


def normalize_jurisdiction_code(jurisdiction: str, table: dict[str, Any] | None = None) -> str:
    """Resolve regional sub-codes (e.g. US_CA, US_NY -> US) against the SSOT jurisdiction table."""
    tbl = table or load_jurisdiction_table()
    j_map = tbl.get("jurisdictions", {})
    default_code = str(tbl.get("default_unknown_jurisdiction", "EU"))
    raw = (jurisdiction or "").strip().upper()
    if raw in j_map:
        return raw
    if raw.startswith("US_"):
        return "US" if "US" in j_map else default_code
    if raw.startswith("EU_"):
        return "EU" if "EU" in j_map else default_code
    if raw.startswith("ID_"):
        return "ID" if "ID" in j_map else default_code
    return default_code


def validate_curve_for_jurisdiction(
    policy: Any,
    jurisdiction: str | None = None,
    *,
    settlement_f_minor: int | None = None,
) -> None:
    """Validate a policy's grade payout curve and misdeclaration fee parameters against the SSOT jurisdiction table.

    Raises JurisdictionCapViolationError if:
    - Any grade payout fraction r(g) falls below 1 - diminished_value_caps[g] (or r_b_min / r_b_override),
      or lies outside [0, 1], or violates monotonicity r(A) >= r(B) >= r(C) >= r(D).
    - The jurisdiction forbids misdeclaration fees (misdeclaration_cost_allowed == False, e.g. EU, ID)
      and any of phi, return_shipping_minor, fee_f_minor, or settlement_f_minor is > 0.
    - The jurisdiction allows misdeclaration fees and phi > phi_max.
    """
    table = load_jurisdiction_table()
    j_map = table.get("jurisdictions", {})
    raw_jur = jurisdiction or getattr(policy, "jurisdiction", None) or (
        policy.get("jurisdiction") if isinstance(policy, dict) else "US"
    )
    j_code = normalize_jurisdiction_code(str(raw_jur or "US"), table)
    row = j_map.get(j_code, {})

    # Extract curve and fee fields from PolicyConfig, SQLModel Policy, or dict
    curve_raw: dict[str, Any] | None = None
    phi_val: Any = None
    return_shipping_val: Any = None
    fee_f_val: Any = None

    if hasattr(policy, "curve_json"):
        curve_raw = dict(policy.curve_json)
        phi_val = getattr(policy, "phi", None)
        return_shipping_val = getattr(policy, "return_shipping_minor", None)
    elif hasattr(policy, "config_json"):
        cfg = getattr(policy, "config_json", None) or {}
        curve_raw = cfg.get("curve") or cfg.get("curve_json")
        phi_val = cfg.get("phi")
        return_shipping_val = cfg.get("return_shipping_minor")
        fee_f_val = cfg.get("fee_f_minor", cfg.get("f_minor"))
    elif isinstance(policy, dict):
        if "curve" in policy or "curve_json" in policy:
            curve_raw = policy.get("curve") or policy.get("curve_json")
            phi_val = policy.get("phi")
            return_shipping_val = policy.get("return_shipping_minor")
            fee_f_val = policy.get("fee_f_minor", policy.get("f_minor"))
        else:
            curve_raw = policy

    if not isinstance(curve_raw, dict) or not curve_raw:
        raise JurisdictionCapViolationError(
            f"Missing or empty refund curve for jurisdiction {j_code}.",
            field="curve",
            jurisdiction=j_code,
        )

    caps = row.get(
        "diminished_value_caps",
        {"A": "0.00", "B": "0.00", "C": "0.20", "D": "0.50", "DEF": "0.00"},
    )

    required_grades = ("A", "B", "C", "D")
    parsed_r: dict[str, Fraction] = {}
    for grade in required_grades:
        if grade not in curve_raw:
            raise JurisdictionCapViolationError(
                f"Curve is missing required grade '{grade}' for jurisdiction {j_code}.",
                field=f"curve.{grade}",
                jurisdiction=j_code,
            )

    for grade, raw_val in curve_raw.items():
        try:
            r_g = Fraction(str(raw_val))
        except Exception as exc:
            raise JurisdictionCapViolationError(
                f"Invalid fraction '{raw_val}' for grade {grade}.",
                field=f"curve.{grade}",
                jurisdiction=j_code,
            ) from exc

        if r_g < Fraction(0) or r_g > Fraction(1, 1):
            raise JurisdictionCapViolationError(
                f"Grade {grade} payout fraction {r_g} must be in [0, 1].",
                field=f"curve.{grade}",
                jurisdiction=j_code,
            )

        max_deduction = Fraction(str(caps.get(grade, "0.50")))
        min_allowed_r = Fraction(1, 1) - max_deduction
        if grade == "B":
            if row.get("r_b_min") is not None:
                min_allowed_r = max(min_allowed_r, Fraction(str(row["r_b_min"])))
            if row.get("r_b_override") is not None:
                min_allowed_r = max(min_allowed_r, Fraction(str(row["r_b_override"])))

        if r_g < min_allowed_r:
            raise JurisdictionCapViolationError(
                f"Grade {grade} payout {r_g} (deduction {Fraction(1, 1) - r_g}) violates {j_code} "
                f"diminished-value cap (minimum allowed r({grade})={min_allowed_r}, max deduction={max_deduction}).",
                field=f"curve.{grade}",
                jurisdiction=j_code,
            )
        parsed_r[grade] = r_g

    if not (parsed_r["A"] >= parsed_r["B"] >= parsed_r["C"] >= parsed_r["D"]):
        raise JurisdictionCapViolationError(
            f"Curve must be monotone non-increasing across grades A >= B >= C >= D in {j_code}.",
            field="curve",
            jurisdiction=j_code,
        )

    # Misdeclaration fee / F validation
    f_allowed = bool(row.get("misdeclaration_cost_allowed", False))
    if not f_allowed:
        if phi_val is not None and Fraction(str(phi_val)) > Fraction(0):
            raise JurisdictionCapViolationError(
                f"Jurisdiction {j_code} requires F = 0 (phi must be 0, got {phi_val}).",
                field="phi",
                jurisdiction=j_code,
            )
        if return_shipping_minor_val := return_shipping_val:
            if int(return_shipping_minor_val) > 0:
                raise JurisdictionCapViolationError(
                    f"Jurisdiction {j_code} requires F = 0 (return_shipping_minor must be 0, got {return_shipping_minor_val}).",
                    field="return_shipping_minor",
                    jurisdiction=j_code,
                )
        if fee_f_val is not None and int(fee_f_val) > 0:
            raise JurisdictionCapViolationError(
                f"Jurisdiction {j_code} requires F = 0 (fee_f_minor must be 0, got {fee_f_val}).",
                field="fee_f_minor",
                jurisdiction=j_code,
            )
        if settlement_f_minor is not None and int(settlement_f_minor) > 0:
            raise JurisdictionCapViolationError(
                f"Jurisdiction {j_code} requires F = 0 (settlement f_minor must be 0, got {settlement_f_minor}).",
                field="f_minor",
                jurisdiction=j_code,
            )
    else:
        phi_max = Fraction(str(row.get("phi_max", "0.05")))
        if phi_val is not None and Fraction(str(phi_val)) > phi_max:
            raise JurisdictionCapViolationError(
                f"phi={phi_val} exceeds {j_code} maximum phi_max={phi_max}.",
                field="phi",
                jurisdiction=j_code,
            )


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
    j_code = normalize_jurisdiction_code(jurisdiction, table)
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
