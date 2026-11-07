"""Initial 20-table canonical schema migration (Section 10.4, Section 30, MG-01..MG-04).

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. merchants
    op.create_table(
        "merchants",
        sa.Column("merchant_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("instant_exposure_cap_minor", sa.BigInteger(), nullable=False),
        sa.Column("outstanding_instant_exposure_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("instant_exposure_cap_minor >= 0", name="chk_merchants_cap_nonneg"),
        sa.CheckConstraint("outstanding_instant_exposure_minor >= 0", name="chk_merchants_exposure_nonneg"),
    )

    # 2. staff_users
    op.create_table(
        "staff_users",
        sa.Column("staff_id", sa.String(), primary_key=True),
        sa.Column("merchant_id", sa.String(), sa.ForeignKey("merchants.merchant_id"), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("email_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 3. shopper_accounts
    op.create_table(
        "shopper_accounts",
        sa.Column("account_id", sa.String(), primary_key=True),
        sa.Column("identity_group_id", sa.String(), nullable=False),
        sa.Column("trust_tier", sa.String(), nullable=False, server_default="NEW"),
        sa.Column("cusum_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 4. identity_link_events
    op.create_table(
        "identity_link_events",
        sa.Column("link_event_id", sa.String(), primary_key=True),
        sa.Column("account_id", sa.String(), sa.ForeignKey("shopper_accounts.account_id"), nullable=False),
        sa.Column("identity_group_id", sa.String(), nullable=False),
        sa.Column("signal_type", sa.String(), nullable=False),
        sa.Column("signal_hmac", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 5. policies
    op.create_table(
        "policies",
        sa.Column("policy_version", sa.String(), primary_key=True),
        sa.Column("merchant_id", sa.String(), sa.ForeignKey("merchants.merchant_id"), nullable=False),
        sa.Column("jurisdiction", sa.String(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 6. passports
    op.create_table(
        "passports",
        sa.Column("passport_id", sa.String(), primary_key=True),
        sa.Column("merchant_id", sa.String(), sa.ForeignKey("merchants.merchant_id"), nullable=False),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("tier", sa.String(), nullable=False),
        sa.Column("origin_grade", sa.String(), nullable=False),
        sa.Column("serial_commitment", sa.String(), nullable=True),
        sa.Column("head_hash", sa.String(), nullable=False),
        sa.Column("signature", sa.String(), nullable=False),
        sa.Column("weight_g", sa.Integer(), nullable=False, server_default="250"),
        sa.Column("self_test_passed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("current_owner_ref", sa.String(), nullable=True),
        sa.Column("buyer_email", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 7. passport_events
    op.create_table(
        "passport_events",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("passport_id", sa.String(), sa.ForeignKey("passports.passport_id"), nullable=False),
        sa.Column("seq_no", sa.Integer(), nullable=False),
        sa.Column("prev_hash", sa.String(), nullable=False),
        sa.Column("event_hash", sa.String(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("signature", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("passport_id", "seq_no", name="uq_passport_seq"),
    )

    # 8. serial_registry
    op.create_table(
        "serial_registry",
        sa.Column("serial_commitment", sa.String(), primary_key=True),
        sa.Column("merchant_id", sa.String(), sa.ForeignKey("merchants.merchant_id"), nullable=False),
        sa.Column("passport_id", sa.String(), sa.ForeignKey("passports.passport_id"), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 9. orders
    op.create_table(
        "orders",
        sa.Column("order_id", sa.String(), primary_key=True),
        sa.Column("merchant_id", sa.String(), sa.ForeignKey("merchants.merchant_id"), nullable=False),
        sa.Column("account_id", sa.String(), sa.ForeignKey("shopper_accounts.account_id"), nullable=False),
        sa.Column("policy_version", sa.String(), sa.ForeignKey("policies.policy_version"), nullable=False),
        sa.Column("paypal_order_id", sa.String(), nullable=False),
        sa.Column("capture_id", sa.String(), nullable=False),
        sa.Column("capture_amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("confirmed_refunded_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("pending_refunded_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "confirmed_refunded_minor + pending_refunded_minor <= capture_amount_minor",
            name="chk_inv01_cumulative_refund",
        ),
    )

    # 10. order_items
    op.create_table(
        "order_items",
        sa.Column("order_item_id", sa.String(), primary_key=True),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.order_id"), nullable=False),
        sa.Column("passport_id", sa.String(), sa.ForeignKey("passports.passport_id"), nullable=True),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("price_minor", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("price_minor >= 0", name="chk_order_item_price_nonneg"),
    )

    # 11. returns
    op.create_table(
        "returns",
        sa.Column("return_id", sa.String(), primary_key=True),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.order_id"), nullable=False),
        sa.Column("order_item_id", sa.String(), sa.ForeignKey("order_items.order_item_id"), nullable=False),
        sa.Column("merchant_id", sa.String(), sa.ForeignKey("merchants.merchant_id"), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("lane", sa.String(), nullable=False),
        sa.Column("timing", sa.String(), nullable=False),
        sa.Column("declared_grade", sa.String(), nullable=True),
        sa.Column("disputed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("appeal_open", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("refiled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("r0_tranche_minor", sa.BigInteger(), nullable=False, server_default="22157"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_returns_one_active_per_order_item",
        "returns",
        ["order_item_id"],
        unique=True,
    )

    # 12. return_evidence
    op.create_table(
        "return_evidence",
        sa.Column("evidence_id", sa.String(), primary_key=True),
        sa.Column("return_id", sa.String(), sa.ForeignKey("returns.return_id"), nullable=False),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column("nonce_return", sa.String(), nullable=False),
        sa.Column("encrypted_blob_uri", sa.String(), nullable=True),
        sa.Column("shredded", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("challenge_step", sa.String(), nullable=False, server_default="STEP_1"),
        sa.Column("faces_detected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("client_blur_applied", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("blur_latency_ms", sa.Float(), nullable=False, server_default="15.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 13. assessments
    op.create_table(
        "assessments",
        sa.Column("assessment_id", sa.String(), primary_key=True),
        sa.Column("return_id", sa.String(), sa.ForeignKey("returns.return_id"), nullable=False),
        sa.Column("predicted_grade", sa.String(), nullable=False),
        sa.Column("conformal_set", sa.JSON(), nullable=False),
        sa.Column("replay_label", sa.String(), nullable=False),
        sa.Column("forensic_flags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 14. decisions
    op.create_table(
        "decisions",
        sa.Column("decision_id", sa.String(), primary_key=True),
        sa.Column("return_id", sa.String(), sa.ForeignKey("returns.return_id"), nullable=False),
        sa.Column("policy_version", sa.String(), sa.ForeignKey("policies.policy_version"), nullable=False),
        sa.Column("lane", sa.String(), nullable=False),
        sa.Column("timing", sa.String(), nullable=False),
        sa.Column("audit_probability", sa.Float(), nullable=False),
        sa.Column("x_minor", sa.BigInteger(), nullable=False),
        sa.Column("checkin_minor", sa.BigInteger(), nullable=False),
        sa.Column("holdback_minor", sa.BigInteger(), nullable=False),
        sa.Column("explanation_json", sa.JSON(), nullable=False),
        sa.Column("signature", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 15. keep_offers
    op.create_table(
        "keep_offers",
        sa.Column("offer_id", sa.String(), primary_key=True),
        sa.Column("return_id", sa.String(), sa.ForeignKey("returns.return_id"), unique=True, nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount_minor >= 0", name="chk_keep_amount_nonneg"),
    )

    # 16. refund_actions
    op.create_table(
        "refund_actions",
        sa.Column("request_id", sa.String(), primary_key=True),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.order_id"), nullable=False),
        sa.Column("return_id", sa.String(), sa.ForeignKey("returns.return_id"), nullable=False),
        sa.Column("decision_id", sa.String(), sa.ForeignKey("decisions.decision_id"), nullable=False),
        sa.Column("tranche", sa.String(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("paypal_refund_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("decision_id", "tranche", name="uq_decision_tranche"),
        sa.CheckConstraint("amount_minor >= 0", name="chk_refund_amount_nonneg"),
    )

    # 17. custody_events
    op.create_table(
        "custody_events",
        sa.Column("custody_event_id", sa.String(), primary_key=True),
        sa.Column("passport_id", sa.String(), sa.ForeignKey("passports.passport_id"), nullable=False),
        sa.Column("return_id", sa.String(), sa.ForeignKey("returns.return_id"), nullable=True),
        sa.Column("interval_name", sa.String(), nullable=False),
        sa.Column("grade_observed", sa.String(), nullable=False),
        sa.Column("weight_g", sa.Integer(), nullable=False),
        sa.Column("seal_intact", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 18. webhook_events
    op.create_table(
        "webhook_events",
        sa.Column("event_id", sa.String(), primary_key=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 19. reviews
    op.create_table(
        "reviews",
        sa.Column("review_id", sa.String(), primary_key=True),
        sa.Column("return_id", sa.String(), sa.ForeignKey("returns.return_id"), nullable=False),
        sa.Column("reviewer_id", sa.String(), sa.ForeignKey("staff_users.staff_id"), nullable=False),
        sa.Column("verified_grade", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 20. appeals
    op.create_table(
        "appeals",
        sa.Column("appeal_id", sa.String(), primary_key=True),
        sa.Column("return_id", sa.String(), sa.ForeignKey("returns.return_id"), nullable=False),
        sa.Column("original_reviewer_id", sa.String(), sa.ForeignKey("staff_users.staff_id"), nullable=False),
        sa.Column("appeal_reviewer_id", sa.String(), sa.ForeignKey("staff_users.staff_id"), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("topup_amount_minor", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "appeal_reviewer_id IS NULL OR appeal_reviewer_id <> original_reviewer_id",
            name="chk_appeal_different_reviewer",
        ),
    )


def downgrade() -> None:
    tables = [
        "appeals",
        "reviews",
        "webhook_events",
        "custody_events",
        "refund_actions",
        "keep_offers",
        "decisions",
        "assessments",
        "return_evidence",
        "returns",
        "order_items",
        "orders",
        "serial_registry",
        "passport_events",
        "passports",
        "policies",
        "identity_link_events",
        "shopper_accounts",
        "staff_users",
        "merchants",
    ]
    for table in tables:
        op.drop_table(table)
