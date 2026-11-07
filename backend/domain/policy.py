"""Typed, versioned Policy configuration model (Section 8.2/8.3, Section 10.4, FR-90, XR-09)."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.domain.constants import FEE_PROHIBITED_JURISDICTIONS

ROOT = Path(__file__).resolve().parent.parent.parent


class PolicyConfig(BaseModel):
    """Typed mechanism v2.1 policy fields matching Section 10.4 `policies` table (FR-90, XR-09)."""

    version: str = "v2.1-default-us"
    jurisdiction: str = "US"
    curve_json: dict[str, str] = Field(
        default_factory=lambda: {"A": "1.00", "B": "0.95", "C": "0.80", "D": "0.50", "DEF": "1.00"}
    )
    phi: str = "0.05"
    return_shipping_minor: int = 1200
    mu: str = "0.05"
    p_min: str = "0.05"
    p_max: str = "0.25"
    p_std: str = "0.25"
    rho_stress: str = "0.30"
    beta_leak: str = "0.02"
    alpha_route: str = "0.10"
    alpha_accuse: str = "0.02"
    value_bands_json: dict[str, int] = Field(
        default_factory=lambda: {"LOW_MAX_MINOR": 15000, "MID_MAX_MINOR": 60000}
    )
    timing_matrix_json: dict[str, dict[str, str]] = Field(
        default_factory=lambda: {
            "TRUSTED": {"LOW": "R0", "MID": "R0", "HIGH": "R1"},
            "ESTABLISHED": {"LOW": "R0", "MID": "R1", "HIGH": "R2"},
            "NEW": {"LOW": "R2", "MID": "R2", "HIGH": "R2"},
            "RESTRICTED": {"LOW": "STANDARD", "MID": "STANDARD", "HIGH": "STANDARD"},
        }
    )
    tier_L_json: dict[str, int] = Field(
        default_factory=lambda: {"NEW": 0, "ESTABLISHED": 2000, "TRUSTED": 4000, "RESTRICTED": 0}
    )
    tier_caps_json: dict[str, int] = Field(
        default_factory=lambda: {
            "NEW": 0,
            "NEW_COUNTER_VERIFIED": 10000,
            "ESTABLISHED": 25000,
            "TRUSTED": 100000,
            "RESTRICTED": 0,
        }
    )
    kappa: str = "1.50"
    aggregate_cap_minor: int = 500000
    velocity_json: dict[str, int] = Field(
        default_factory=lambda: {
            "max_open_pre_checkin_per_group": 2,
            "max_accounts_per_address_30d_fast": 3,
        }
    )
    theta_h: str = "0.30"
    promotion_rules_json: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def default_us(cls) -> PolicyConfig:
        cfg_path = ROOT / "config" / "policy_defaults.json"
        if cfg_path.exists():
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
            return cls(**data)
        return cls()

    @classmethod
    def default_eu(cls) -> PolicyConfig:
        """FR-84 & Section 12.4: EU forces r(B) = 1.00 and F = 0."""
        base = cls.default_us()
        curve = dict(base.curve_json)
        curve["B"] = "1.00"
        return base.model_copy(
            update={
                "version": "v2.1-default-eu",
                "jurisdiction": "EU",
                "curve_json": curve,
                "phi": "0.00",
                "return_shipping_minor": 0,
            }
        )

    def grade_fraction(self, grade: str) -> Fraction:
        return Fraction(self.curve_json[grade])

    def mu_fraction(self) -> Fraction:
        return Fraction(self.mu)

    def p_min_fraction(self) -> Fraction:
        return Fraction(self.p_min)

    def p_max_fraction(self) -> Fraction:
        return Fraction(self.p_max)

    def p_std_fraction(self) -> Fraction:
        return Fraction(self.p_std)

    def rho_stress_fraction(self) -> Fraction:
        return Fraction(self.rho_stress)

    def beta_leak_fraction(self) -> Fraction:
        return Fraction(self.beta_leak)

    def theta_h_fraction(self) -> Fraction:
        return Fraction(self.theta_h)

    def kappa_fraction(self) -> Fraction:
        return Fraction(self.kappa)

    def compute_f_minor(self, price_minor: int) -> int:
        """FR-59 & FR-84: F = max(S_return, phi * P), or 0 where prohibited (EU/ID)."""
        # ASSUMPTION(A-26): Disclosed misdeclaration cost max($12, 5% of P) permissible in US demo
        if self.jurisdiction in FEE_PROHIBITED_JURISDICTIONS:
            return 0
        phi_frac = Fraction(self.phi)
        prop_minor = int(Fraction(price_minor) * phi_frac)
        return max(self.return_shipping_minor, prop_minor)

    def value_band(self, price_minor: int) -> str:
        """D-10: LOW < $150 (15000), MID $150-$600 (15000..60000), HIGH > $600 (>60000)."""
        low_max = self.value_bands_json.get("LOW_MAX_MINOR", 15000)
        mid_max = self.value_bands_json.get("MID_MAX_MINOR", 60000)
        if price_minor < low_max:
            return "LOW"
        if price_minor <= mid_max:
            return "MID"
        return "HIGH"

    def tier_l_minor(self, tier: str) -> int:
        """ASSUMPTION(A-08) & ASSUMPTION(A-20): Tier trust values L_i (0 / 20 / 40 USD)."""
        return int(self.tier_L_json.get(tier, 0))

    def select_timing(self, tier: str, price_minor: int, drop_off_verified: bool = False) -> str:
        """Section 8.3 & FR-96: Default timing matrix; NEW x LOW allows R1 only with counter-verified drop-off."""
        band = self.value_band(price_minor)
        if tier == "NEW" and band == "LOW" and drop_off_verified:
            return "R1"
        return self.timing_matrix_json.get(tier, {}).get(band, "STANDARD")
