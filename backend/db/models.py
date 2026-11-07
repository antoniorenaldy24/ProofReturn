"""SQLModel Data Models for 22 Canonical Tables (Section 10.4, Section 30, DB-01..DB-10, AUD-06, AUD-42, RV-02, RV-08).

Implements typed models for merchants, orders, returns, passports, appeals, resale,
keep-offers, evidence, agent tokens, and audit logs with BigInteger monetary fields,
currency columns (DB-01), ON DELETE RESTRICT foreign keys (DB-02), and optimistic
locking version columns (DB-07).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, Column, ForeignKey, Integer, String
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_csprng_seed_hex() -> str:
    return secrets.token_hex(32)


class Merchant(SQLModel, table=True):
    __tablename__ = "merchants"

    merchant_id: str = Field(primary_key=True)
    name: str = Field(default="Demo Merchant")
    instant_exposure_cap_minor: int = Field(
        default=500000, sa_column=Column(BigInteger, nullable=False, default=500000)
    )
    outstanding_instant_exposure_minor: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, default=0)
    )
    currency: str = Field(default="USD", sa_column=Column(String(3), nullable=False, default="USD"))
    version: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    created_at: datetime = Field(default_factory=_utc_now)



class StaffUser(SQLModel, table=True):
    __tablename__ = "staff_users"

    staff_id: str = Field(primary_key=True)
    merchant_id: str = Field(
        sa_column=Column(String, ForeignKey("merchants.merchant_id", ondelete="RESTRICT"), nullable=False)
    )
    role: str = Field(default="REVIEWER")
    email_hash: str = Field(default="")
    created_at: datetime = Field(default_factory=_utc_now)


class ShopperAccount(SQLModel, table=True):
    __tablename__ = "shopper_accounts"

    account_id: str = Field(primary_key=True)
    identity_group_id: str = Field(default="id_grp_default")
    trust_tier: str = Field(default="NEW")
    cusum_score: float = Field(default=0.0)
    clean_Counter_verified_returns: int = Field(default=0)
    account_age_days: int = Field(default=30)
    version: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    created_at: datetime = Field(default_factory=_utc_now)



class IdentityLinkEvent(SQLModel, table=True):
    __tablename__ = "identity_link_events"

    link_event_id: str = Field(primary_key=True)
    account_id: str = Field(
        sa_column=Column(String, ForeignKey("shopper_accounts.account_id", ondelete="RESTRICT"), nullable=False)
    )
    identity_group_id: str
    signal_type: str
    signal_hmac: str
    created_at: datetime = Field(default_factory=_utc_now)


class Policy(SQLModel, table=True):
    __tablename__ = "policies"

    policy_version: str = Field(primary_key=True)
    merchant_id: str = Field(
        sa_column=Column(String, ForeignKey("merchants.merchant_id", ondelete="RESTRICT"), nullable=False)
    )
    jurisdiction: str = Field(default="US_CA")
    return_window_days: int = Field(default=30)
    is_active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False, default=True))
    config_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=_utc_now)


class Passport(SQLModel, table=True):
    __tablename__ = "passports"

    passport_id: str = Field(primary_key=True)
    merchant_id: str = Field(
        sa_column=Column(String, ForeignKey("merchants.merchant_id", ondelete="RESTRICT"), nullable=False)
    )
    sku: str = Field(default="PR-HP-XM5")
    tier: str = Field(default="FULL")  # Canonical enum: FULL | LITE | NONE (AUD-42)
    origin_grade: str = Field(default="A")
    serial_commitment: str | None = None
    head_hash: str = Field(default="0" * 64)
    signature: str = Field(default="")
    signing_key_id: str = Field(default="key_packer_origin_01")
    weight_g: int = Field(default=250)
    self_test_passed: bool = Field(default=False)
    current_owner_ref: str | None = None
    buyer_email: str | None = None
    version: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    created_at: datetime = Field(default_factory=_utc_now)



class PassportEvent(SQLModel, table=True):
    __tablename__ = "passport_events"

    event_id: str = Field(primary_key=True)
    passport_id: str = Field(
        sa_column=Column(String, ForeignKey("passports.passport_id", ondelete="RESTRICT"), nullable=False)
    )
    seq_no: int = Field(default=1)
    prev_hash: str = Field(default="0" * 64)
    event_hash: str = Field(default="0" * 64)
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    signature: str = Field(default="")
    created_at: datetime = Field(default_factory=_utc_now)


class SerialRegistry(SQLModel, table=True):
    __tablename__ = "serial_registry"

    serial_commitment: str = Field(primary_key=True)
    merchant_id: str = Field(
        sa_column=Column(String, ForeignKey("merchants.merchant_id", ondelete="RESTRICT"), nullable=False)
    )
    passport_id: str = Field(
        sa_column=Column(String, ForeignKey("passports.passport_id", ondelete="RESTRICT"), nullable=False)
    )
    order_id: str = Field(default="ord_demo_1")
    status: str = Field(default="ACTIVE")
    created_at: datetime = Field(default_factory=_utc_now)


class Order(SQLModel, table=True):
    __tablename__ = "orders"

    order_id: str = Field(primary_key=True)
    merchant_id: str = Field(
        sa_column=Column(String, ForeignKey("merchants.merchant_id", ondelete="RESTRICT"), nullable=False)
    )
    account_id: str = Field(
        sa_column=Column(String, ForeignKey("shopper_accounts.account_id", ondelete="RESTRICT"), nullable=False)
    )
    policy_version: str = Field(
        sa_column=Column(String, ForeignKey("policies.policy_version", ondelete="RESTRICT"), nullable=False)
    )
    paypal_order_id: str = Field(default="PP-ORD-01")
    capture_id: str = Field(default="CAP-01")
    capture_amount_minor: int = Field(
        default=38000, sa_column=Column(BigInteger, nullable=False, default=38000)
    )
    confirmed_refunded_minor: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, default=0)
    )
    pending_refunded_minor: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, default=0)
    )
    frozen_by_dispute: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, default=False)
    )
    frozen_at: datetime | None = Field(default=None)
    frozen_reason: str | None = Field(default=None)
    capture_reversed: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, default=False)
    )
    reversed_at: datetime | None = Field(default=None)
    currency: str = Field(default="USD", sa_column=Column(String(3), nullable=False, default="USD"))
    version: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    created_at: datetime = Field(default_factory=_utc_now)



class OrderItem(SQLModel, table=True):
    __tablename__ = "order_items"

    order_item_id: str = Field(primary_key=True)
    order_id: str = Field(
        sa_column=Column(String, ForeignKey("orders.order_id", ondelete="RESTRICT"), nullable=False)
    )
    passport_id: str | None = Field(
        default=None,
        sa_column=Column(String, ForeignKey("passports.passport_id", ondelete="RESTRICT"), nullable=True),
    )
    sku: str = Field(default="PR-HP-XM5")
    price_minor: int = Field(
        default=38000, sa_column=Column(BigInteger, nullable=False, default=38000)
    )
    currency: str = Field(default="USD", sa_column=Column(String(3), nullable=False, default="USD"))


class Return(SQLModel, table=True):
    __tablename__ = "returns"

    return_id: str = Field(primary_key=True)
    order_id: str = Field(
        sa_column=Column(String, ForeignKey("orders.order_id", ondelete="RESTRICT"), nullable=False)
    )
    order_item_id: str = Field(
        sa_column=Column(String, ForeignKey("order_items.order_item_id", ondelete="RESTRICT"), nullable=False)
    )
    merchant_id: str = Field(
        sa_column=Column(String, ForeignKey("merchants.merchant_id", ondelete="RESTRICT"), nullable=False)
    )
    shopper_id: str = Field(default="shopper_1")
    state: str = Field(default="REQUESTED")
    lane: str = Field(default="FAST")
    timing: str = Field(default="R0")
    declared_grade: str | None = Field(default=None)
    disputed: bool = Field(default=False)
    appeal_open: bool = Field(default=False)
    refiled: bool = Field(default=False)
    r0_tranche_minor: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, default=0)
    )
    currency: str = Field(default="USD", sa_column=Column(String(3), nullable=False, default="USD"))
    # Cryptographic nonces and CSPRNG audit seed (RV-02, FR-61, FR-95, INV-16)
    challenge_nonce: str = Field(default_factory=lambda: f"NONCE-{secrets.token_hex(8).upper()}")
    shopper_nonce: str | None = Field(default=None)
    audit_seed_hex: str = Field(default_factory=_new_csprng_seed_hex)
    audit_commitment: str = Field(default="")
    audit_probability: float = Field(default=0.08)
    # Declaration & Dropoff state
    reason_code: str = Field(default="CHANGED_MIND")
    reason_text: str = Field(default="")
    accessories_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    consent_recorded: bool = Field(default=False)
    seal_nonce_hash: str | None = Field(default=None)
    dropoff_photo_ref: str | None = Field(default=None)
    carrier_tracking_number: str | None = Field(default=None)
    retake_count: int = Field(default=0)
    version: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    created_at: datetime = Field(default_factory=_utc_now)


    def ensure_audit_commitment(self) -> str:
        """Compute and persist commitment c = SHA-256(seed_platform || '||' || return_id) from CSPRNG seed (RV-02)."""
        if not self.audit_seed_hex or len(self.audit_seed_hex) != 64:
            self.audit_seed_hex = secrets.token_hex(32)
        seed_bytes = bytes.fromhex(self.audit_seed_hex)
        self.audit_commitment = hashlib.sha256(
            seed_bytes + b"||" + self.return_id.encode("utf-8")
        ).hexdigest()
        return self.audit_commitment


class ReturnEvidence(SQLModel, table=True):
    __tablename__ = "return_evidence"

    evidence_id: str = Field(primary_key=True)
    return_id: str = Field(
        sa_column=Column(String, ForeignKey("returns.return_id", ondelete="RESTRICT"), nullable=False)
    )
    evidence_sha256: str = Field(default="a" * 64)
    nonce_return: str = Field(default="")
    encrypted_blob_uri: str | None = None
    shredded: bool = Field(default=False)
    challenge_step: int = Field(default=1)
    faces_detected: int = Field(default=0)
    client_blur_applied: bool = Field(default=False)
    blur_latency_ms: float = Field(default=15.0)
    created_at: datetime = Field(default_factory=_utc_now)


class Assessment(SQLModel, table=True):
    __tablename__ = "assessments"

    assessment_id: str = Field(primary_key=True)
    return_id: str = Field(
        sa_column=Column(String, ForeignKey("returns.return_id", ondelete="RESTRICT"), nullable=False)
    )
    predicted_grade: str = Field(default="B")
    conformal_set: list[str] = Field(default_factory=lambda: ["B"], sa_column=Column(JSON, nullable=False))
    replay_label: str = Field(default="LIVE")
    forensic_flags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=_utc_now)


class Decision(SQLModel, table=True):
    __tablename__ = "decisions"

    decision_id: str = Field(primary_key=True)
    return_id: str = Field(
        sa_column=Column(String, ForeignKey("returns.return_id", ondelete="RESTRICT"), nullable=False)
    )
    policy_version: str = Field(
        sa_column=Column(String, ForeignKey("policies.policy_version", ondelete="RESTRICT"), nullable=False)
    )
    lane: str = Field(default="FAST")
    timing: str = Field(default="R0")
    audit_probability: float = Field(default=0.08)
    x_minor: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, default=0)
    )
    checkin_minor: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, default=0)
    )
    holdback_minor: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, default=0)
    )
    currency: str = Field(default="USD", sa_column=Column(String(3), nullable=False, default="USD"))
    explanation_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    signature: str = Field(default="")
    created_at: datetime = Field(default_factory=_utc_now)


class KeepOffer(SQLModel, table=True):
    __tablename__ = "keep_offers"

    offer_id: str = Field(primary_key=True)
    return_id: str = Field(
        sa_column=Column(String, ForeignKey("returns.return_id", ondelete="RESTRICT"), unique=True, nullable=False)
    )
    amount_minor: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, default=0)
    )
    currency: str = Field(default="USD", sa_column=Column(String(3), nullable=False, default="USD"))
    status: str = Field(default="OFFERED")
    expires_at: datetime = Field(default_factory=_utc_now)
    version: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    created_at: datetime = Field(default_factory=_utc_now)



class RefundAction(SQLModel, table=True):
    __tablename__ = "refund_actions"

    request_id: str = Field(primary_key=True)
    merchant_id: str = Field(
        default="merch_a",
        sa_column=Column(String, ForeignKey("merchants.merchant_id", ondelete="RESTRICT"), nullable=False, default="merch_a"),
    )
    order_id: str = Field(
        sa_column=Column(String, ForeignKey("orders.order_id", ondelete="RESTRICT"), nullable=False)
    )
    return_id: str = Field(
        sa_column=Column(String, ForeignKey("returns.return_id", ondelete="RESTRICT"), nullable=False)
    )
    decision_id: str = Field(
        sa_column=Column(String, ForeignKey("decisions.decision_id", ondelete="RESTRICT"), nullable=False)
    )
    capture_id: str = Field(default="CAP-01")
    tranche: str = Field(default="R0")
    amount_minor: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, default=0)
    )
    currency: str = Field(default="USD", sa_column=Column(String(3), nullable=False, default="USD"))
    status: str = Field(default="PLANNED")
    status_detail: str | None = None
    paypal_refund_id: str | None = None
    paypal_debug_id: str | None = None
    attempt_count: int = Field(default=0, sa_column=Column(Integer, nullable=False, default=0))
    next_attempt_at: datetime | None = Field(default=None)
    version: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    created_at: datetime = Field(default_factory=_utc_now)



class CustodyEvent(SQLModel, table=True):
    __tablename__ = "custody_events"

    custody_event_id: str = Field(primary_key=True)
    passport_id: str = Field(
        sa_column=Column(String, ForeignKey("passports.passport_id", ondelete="RESTRICT"), nullable=False)
    )
    return_id: str | None = Field(
        default=None,
        sa_column=Column(String, ForeignKey("returns.return_id", ondelete="RESTRICT"), nullable=True),
    )
    interval_name: str = Field(default="CARRIER_TO_DOCK")
    grade_observed: str = Field(default="B")
    weight_g: int = Field(default=250)
    seal_intact: bool = Field(default=True)
    records_only: bool = Field(default=True)
    evidence_ref: str = Field(default="dock.jpg")
    created_at: datetime = Field(default_factory=_utc_now)


class WebhookEvent(SQLModel, table=True):
    __tablename__ = "webhook_events"

    event_id: str = Field(primary_key=True)
    event_type: str = Field(default="PAYMENT.CAPTURE.REFUNDED")
    payload_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    processed_at: datetime = Field(default_factory=_utc_now)


class Review(SQLModel, table=True):
    __tablename__ = "reviews"

    review_id: str = Field(primary_key=True)
    return_id: str = Field(
        sa_column=Column(String, ForeignKey("returns.return_id", ondelete="RESTRICT"), nullable=False)
    )
    reviewer_id: str = Field(
        sa_column=Column(String, ForeignKey("staff_users.staff_id", ondelete="RESTRICT"), nullable=False)
    )
    verified_grade: str = Field(default="B")
    outcome: str = Field(default="CONFIRMED")
    notes: str = Field(default="")
    created_at: datetime = Field(default_factory=_utc_now)


class Appeal(SQLModel, table=True):
    __tablename__ = "appeals"

    appeal_id: str = Field(primary_key=True)
    return_id: str = Field(
        sa_column=Column(String, ForeignKey("returns.return_id", ondelete="RESTRICT"), nullable=False)
    )
    original_reviewer_id: str = Field(
        sa_column=Column(String, ForeignKey("staff_users.staff_id", ondelete="RESTRICT"), nullable=False)
    )
    appeal_reviewer_id: str | None = Field(
        default=None,
        sa_column=Column(String, ForeignKey("staff_users.staff_id", ondelete="RESTRICT"), nullable=True),
    )
    status: str = Field(default="OPEN")
    subject: str = Field(default="")
    disputed_delta_minor: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, default=0)
    )
    topup_amount_minor: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, default=0)
    )
    currency: str = Field(default="USD", sa_column=Column(String(3), nullable=False, default="USD"))
    outcome: str | None = None
    version: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    created_at: datetime = Field(default_factory=_utc_now)



class ResaleListing(SQLModel, table=True):
    __tablename__ = "resale_listings"

    listing_id: str = Field(primary_key=True)
    passport_id: str = Field(
        sa_column=Column(String, ForeignKey("passports.passport_id", ondelete="RESTRICT"), nullable=False)
    )
    verified_grade: str = Field(default="B")
    price_minor: int = Field(
        default=31500, sa_column=Column(BigInteger, nullable=False, default=31500)
    )
    currency: str = Field(default="USD", sa_column=Column(String(3), nullable=False, default="USD"))
    status: str = Field(default="ACTIVE")
    resale_order_id: str | None = None
    version: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    created_at: datetime = Field(default_factory=_utc_now)



class AgentToken(SQLModel, table=True):
    __tablename__ = "agent_tokens"

    token_id: str = Field(primary_key=True)
    order_id: str = Field(
        sa_column=Column(String, ForeignKey("orders.order_id", ondelete="RESTRICT"), nullable=False)
    )
    merchant_id: str = Field(default="merch_a")
    agent_id: str = Field(default="agent_bot")
    scopes: str = Field(default="read_policy,declare")
    agent_label: str = Field(default="assistant")
    signature_hash: str = Field(default="")
    revoked: bool = Field(default=False)
    expires_at: int = Field(default=0)
    version: int = Field(default=1, sa_column=Column(Integer, nullable=False, default=1))
    created_at: datetime = Field(default_factory=_utc_now)


class SchedulerLease(SQLModel, table=True):
    __tablename__ = "scheduler_leases"

    lease_name: str = Field(primary_key=True)
    holder_id: str = Field(sa_column=Column(String, nullable=False))
    acquired_at: datetime = Field(default_factory=_utc_now)
    expires_at: datetime = Field(default_factory=_utc_now)
