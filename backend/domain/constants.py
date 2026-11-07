"""Canonical Domain Constants and Single Source of Truth Enums (AUD-16, AUD-42, Section 8, Section 28).

Defines unified condition grades, trust tiers, supported jurisdictions, staff roles,
and return states shared across domain, policy engine, AI calibration, and REST API schemas.
"""

from __future__ import annotations

from enum import Enum


class ConditionGrade(str, Enum):
    """Condition grading scale from defective to pristine (Section 7.1)."""
    DEF = "DEF"
    D = "D"
    C = "C"
    B = "B"
    A = "A"


GRADES_ORDERED: tuple[str, ...] = ("DEF", "D", "C", "B", "A")
SALABLE_GRADES: tuple[str, ...] = ("D", "C", "B", "A")

GRADE_RANK: dict[str, int] = {
    "DEF": 0,
    "D": 1,
    "C": 2,
    "B": 3,
    "A": 4,
}

DEFAULT_GRADE_CURVE: dict[str, float] = {
    "A": 1.0,
    "B": 0.95,
    "C": 0.80,
    "D": 0.50,
    "DEF": 0.0,
}


class TrustTier(str, Enum):
    """Value-weighted shopper trust progression tiers (Section 8.7, FR-91)."""
    RESTRICTED = "RESTRICTED"
    NEW = "NEW"
    ESTABLISHED = "ESTABLISHED"
    TRUSTED = "TRUSTED"


TRUST_TIERS: tuple[str, ...] = ("RESTRICTED", "NEW", "ESTABLISHED", "TRUSTED")

TIER_RANK: dict[str, int] = {
    "RESTRICTED": 0,
    "NEW": 1,
    "ESTABLISHED": 2,
    "TRUSTED": 3,
}

TIER_CAPS_MINOR: dict[str, int] = {
    "RESTRICTED": 0,
    "NEW": 0,
    "ESTABLISHED": 25000,   # $250.00 (Section 8.7 & FR-92)
    "TRUSTED": 100000,      # $1,000.00 (Section 8.7 & FR-92)
}

COUNTER_VERIFIED_DROPOFF_CAP_MINOR: int = 10000  # $100.00 for NEW with counter-verified drop-off (FR-92)


class SupportedJurisdiction(str, Enum):
    """Supported legal return jurisdictions (Section 8.2)."""
    US = "US"
    EU = "EU"
    UK = "UK"


SUPPORTED_JURISDICTIONS: tuple[str, ...] = ("US", "EU", "UK")

FEE_PROHIBITED_JURISDICTIONS: frozenset[str] = frozenset({"EU", "ID"})

JURISDICTION_RETURN_WINDOWS_DAYS: dict[str, int] = {
    "US": 30,
    "EU": 14,
    "UK": 14,
}


class StaffRole(str, Enum):
    """Merchant staff role boundaries (Section 28.1 API-04, AUD-29)."""
    MERCHANT_ADMIN = "MERCHANT_ADMIN"
    MERCHANT_OPERATOR = "MERCHANT_OPERATOR"
    REVIEWER = "REVIEWER"
    PACKER = "PACKER"
    RECEIVER = "RECEIVER"


STAFF_ROLES: tuple[str, ...] = (
    "MERCHANT_ADMIN",
    "MERCHANT_OPERATOR",
    "REVIEWER",
    "PACKER",
    "RECEIVER",
)


class PassportTier(str, Enum):
    """Condition Passport coverage tiers (Section 6.1, AUD-42)."""
    FULL = "FULL"
    LITE = "LITE"
    NONE = "NONE"


PASSPORT_TIERS: tuple[str, ...] = ("FULL", "LITE", "NONE")


class ReturnState(str, Enum):
    """Canonical Return Lifecycle State Machine states (Section 26)."""
    REQUESTED = "REQUESTED"
    DECLARED = "DECLARED"
    ASSESSED = "ASSESSED"
    DROPPED_OFF = "DROPPED_OFF"
    IN_TRANSIT = "IN_TRANSIT"
    AT_WAREHOUSE = "AT_WAREHOUSE"
    INSPECTING = "INSPECTING"
    SETTLING = "SETTLING"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"
    CANCELLED = "CANCELLED"


RETURN_STATES: tuple[str, ...] = (
    "REQUESTED",
    "DECLARED",
    "ASSESSED",
    "DROPPED_OFF",
    "IN_TRANSIT",
    "AT_WAREHOUSE",
    "INSPECTING",
    "SETTLING",
    "COMPLETED",
    "ESCALATED",
    "CANCELLED",
)
