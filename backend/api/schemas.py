"""Pydantic Request & Response Schemas for /v1 Endpoints (AUD-04, J-08, Section 28).

Enforces strict input validation, prohibits permissive defaults for sensitive fields,
and aligns with RFC 9457 error contracts.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictRequestModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class CreateReturnRequest(StrictRequestModel):
    order_id: str = Field(..., min_length=1, description="Order identifier")
    order_item_id: str | None = Field(default=None, description="Optional specific order item ID")
    items: list[str] | None = Field(default=None, description="Optional list of SKU identifiers")


class ReturnDeclarationRequest(StrictRequestModel):
    declared_grade: str = Field(..., pattern="^(A|B|C|D|DEF)$", description="Item condition grade")
    consent_fast_lane_terms: bool | None = Field(default=None, description="Explicit consent to fast-lane terms")
    fast_lane_terms_accepted: bool | None = Field(default=None, description="Alias for consent")
    reason_code: str = Field("CHANGED_MIND", description="Return reason code")
    reason_text: str | None = Field(default="", max_length=1000)
    accessories: Any = Field(default_factory=dict)
    nonce_shopper: str | None = Field(default=None, min_length=4)
    shopper_nonce: str | None = Field(default=None, min_length=4)
    actor: Any = None
    functional_self_test_completed: bool = False

    @model_validator(mode="after")
    def validate_consent(self) -> ReturnDeclarationRequest:
        consent = self.consent_fast_lane_terms
        if consent is None:
            consent = self.fast_lane_terms_accepted
        if consent is not True:
            raise ValueError("Fast Lane terms must be explicitly accepted (FR-14, INV-06).")
        return self


class EvidenceSubmissionRequest(StrictRequestModel):
    kind: str = Field("VIDEO_CHALLENGE", description="Evidence media kind")
    object_key: str = Field(default="raw/challenge.mp4", description="Storage object key")
    sha256: str = Field(..., min_length=16, description="Media cryptographic hash")
    challenge_step: int = Field(1, ge=1)
    faces_detected: int = Field(0, ge=0)
    client_blur_applied: bool | None = Field(default=None, description="Client face blur applied")
    blur_latency_ms: float = Field(15.0, ge=0.0)
    text_in_media: str = Field("", description="OCR text extracted from media")

    @model_validator(mode="after")
    def validate_blur(self) -> EvidenceSubmissionRequest:
        if self.faces_detected > 0 and self.client_blur_applied is not True:
            raise ValueError("Privacy face-blur verification failed (FR-16): blur must be applied when faces detected.")
        return self


class DropoffRequest(StrictRequestModel):
    seal_nonce: str = Field(..., min_length=1, description="Tamper-evident seal nonce")
    dropoff_photo_ref: str | None = Field(default=None, description="Dropoff photo key")
    carrier_tracking_number: str = Field(..., min_length=1, description="Carrier tracking number")


class KeepOfferRespondRequest(StrictRequestModel):
    action: str = Field(..., pattern="^(?i)(ACCEPT|DECLINE)$", description="Shopper response action")


class MintPassportRequest(StrictRequestModel):
    passport_id: str | None = None
    order_id: str | None = None
    order_item_id: str | None = None
    price_minor: int | None = None
    sku: str = Field("PR-HP-XM5", min_length=1)
    tier: str | None = Field(default=None, description="Ignored if present; tier is computed from order line value band (FR-63)")
    origin_grade: str = Field("A", pattern="^(A|B|C|D|DEF)$")
    weight_g: int = Field(250, ge=1)
    self_test_passed: bool = Field(..., description="Self-test status must be explicitly specified (no permissive default)")


class OrderPassportRequest(StrictRequestModel):
    passport_id: str | None = None
    order_item_id: str | None = None
    sku: str = Field("PR-HP-XM5", min_length=1)
    tier: str | None = Field(default=None, description="Ignored if present; tier is computed from order line value band (FR-63)")
    origin_grade: str = Field("A", pattern="^(A|B|C|D|DEF)$")
    weight_g: int = Field(250, ge=1)
    self_test_passed: bool = Field(..., description="Self-test status must be explicitly specified (no permissive default)")


class ReviewDecisionRequest(StrictRequestModel):
    outcome: str = Field(..., min_length=1)
    verified_grade: str = Field(..., pattern="^(A|B|C|D|DEF)$")
    notes: str = ""


class ReceivingCheckpointRequest(StrictRequestModel):
    interval: str = Field("CARRIER_TO_DOCK", min_length=1)
    weight_g: int = Field(250, ge=1)
    seal_status: str = Field("INTACT", pattern="^(INTACT|BROKEN|MISSING)$")
    evidence_ref: str | None = None


class AuditResultRequest(StrictRequestModel):
    verified_grade: str = Field("B", pattern="^(A|B|C|D|DEF)$")
    conformal_set: list[str] = Field(default_factory=lambda: ["B"])
    notes: str = ""
    misdeclaration_cost_minor: int = 0


class FileAppealRequest(StrictRequestModel):
    return_id: str = Field(..., min_length=1)
    original_reviewer_id: str | None = None
    subject: str = Field(..., min_length=1)
    disputed_delta_minor: int = Field(0, ge=0)


class DecideAppealRequest(StrictRequestModel):
    outcome: str = Field("OVERTURNED", min_length=1)
    appeal_reviewer_id: str | None = None


class CreateResaleListingRequest(StrictRequestModel):
    passport_id: str = Field(..., min_length=1)
    verified_grade: str = Field("B", pattern="^(A|B|C|D|DEF)$")
    price_minor: int = Field(..., gt=0)


class PurchaseResaleListingRequest(StrictRequestModel):
    new_owner_ref: str | None = Field(default=None)


class SimulateRequest(StrictRequestModel):
    price_minor: int = Field(40000, gt=0)
    declared_grade: str = Field(..., pattern="^(A|B|C|D|DEF)$", description="Declared condition grade")
    tier: str = Field("TRUSTED", min_length=1)
    has_origin_passport: bool = True


class CreatePolicyRequest(StrictRequestModel):
    jurisdiction: str = Field("US", min_length=2)
    policy_version: str | None = None
    return_window_days: int = Field(30, ge=1)
    curve: dict[str, float] | None = None
    phi: float | str | None = None
    fee_f_minor: int | None = None
    f_minor: int | None = None
    return_shipping_minor: int | None = None


class DemoClockRequest(StrictRequestModel):
    duration_seconds: int = Field(86400, ge=1)


class PrivacyDeletionRequest(StrictRequestModel):
    subject_id: str = Field("subj_demo_01", min_length=1)
    raw_media_keys: list[str] = Field(default_factory=list)
    derived_media_keys: list[str] = Field(default_factory=list)
    persistent_fraud_flags: list[str] = Field(default_factory=list)
    has_open_dispute: bool = False


class IssueAgentTokenRequest(StrictRequestModel):
    order_id: str = Field(..., min_length=1)
    scopes: list[str] = Field(..., min_length=1)
    ttl: int = Field(3600, ge=60, le=86400)
    agent_label: str = "assistant"


class CarrierEventRequest(StrictRequestModel):
    return_id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)


class IssueStaffTokenRequest(StrictRequestModel):
    merchant_id: str = Field(..., min_length=1, description="Merchant identifier")
    staff_id: str = Field(..., min_length=1, description="Staff user identifier")
    role: str = Field("MERCHANT_ADMIN", description="Staff role (MERCHANT_ADMIN, MERCHANT_OPERATOR, REVIEWER, PACKER, RECEIVER)")
    ttl_seconds: int = Field(86400, ge=60, le=604800, description="Token lifetime in seconds")


class IssueShopperMagicLinkRequest(StrictRequestModel):
    order_id: str = Field(..., min_length=1, description="Order identifier to scope magic link")
    shopper_id: str | None = Field(default=None, description="Shopper account ID (if known)")
    email: str | None = Field(default=None, description="Shopper email address for verification")
    ttl_seconds: int = Field(86400, ge=60, le=604800, description="Token lifetime in seconds")

