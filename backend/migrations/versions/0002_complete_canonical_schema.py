"""Complete 22-table canonical schema alignment (RV-08, ARC-15, AUD-42, DB-01..DB-10).

Adds resale_listings and agent_tokens tables, BigInteger monetary fields, currency columns,
optimistic locking version columns, RefundAction metadata, and Return cryptographic nonces/seeds.

Revision ID: 0002_complete_canonical_schema
Revises: 0001_initial_schema
Create Date: 2026-11-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_complete_canonical_schema"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def _add_col_if_missing(inspector: sa.Inspector, table: str, column: sa.Column) -> None:
    existing = {c["name"] for c in inspector.get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 21. resale_listings
    if "resale_listings" not in existing_tables:
        op.create_table(
            "resale_listings",
            sa.Column("listing_id", sa.String(), primary_key=True),
            sa.Column("passport_id", sa.String(), sa.ForeignKey("passports.passport_id", ondelete="RESTRICT"), nullable=False),
            sa.Column("verified_grade", sa.String(), nullable=False, server_default="B"),
            sa.Column("price_minor", sa.BigInteger(), nullable=False, server_default="31500"),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
            sa.Column("status", sa.String(), nullable=False, server_default="ACTIVE"),
            sa.Column("resale_order_id", sa.String(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("price_minor >= 0", name="chk_resale_price_nonneg"),
        )
    else:
        _add_col_if_missing(inspector, "resale_listings", sa.Column("currency", sa.String(3), nullable=False, server_default="USD"))
        _add_col_if_missing(inspector, "resale_listings", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    # 22. agent_tokens
    if "agent_tokens" not in existing_tables:
        op.create_table(
            "agent_tokens",
            sa.Column("token_id", sa.String(), primary_key=True),
            sa.Column("order_id", sa.String(), sa.ForeignKey("orders.order_id", ondelete="RESTRICT"), nullable=False),
            sa.Column("merchant_id", sa.String(), nullable=False, server_default="merch_a"),
            sa.Column("agent_id", sa.String(), nullable=False, server_default="agent_bot"),
            sa.Column("scopes", sa.String(), nullable=False, server_default="read_policy,declare"),
            sa.Column("agent_label", sa.String(), nullable=False, server_default="assistant"),
            sa.Column("signature_hash", sa.String(), nullable=False, server_default=""),
            sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("expires_at", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    else:
        _add_col_if_missing(inspector, "agent_tokens", sa.Column("signature_hash", sa.String(), nullable=False, server_default=""))
        _add_col_if_missing(inspector, "agent_tokens", sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()))
        _add_col_if_missing(inspector, "agent_tokens", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    # 23. scheduler_leases (RV2-02)
    if "scheduler_leases" not in existing_tables:
        op.create_table(
            "scheduler_leases",
            sa.Column("lease_name", sa.String(), primary_key=True),
            sa.Column("holder_id", sa.String(), nullable=False),
            sa.Column("acquired_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # Align columns on existing 20 tables
    _add_col_if_missing(inspector, "merchants", sa.Column("currency", sa.String(3), nullable=False, server_default="USD"))
    _add_col_if_missing(inspector, "merchants", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    _add_col_if_missing(inspector, "shopper_accounts", sa.Column("clean_Counter_verified_returns", sa.Integer(), nullable=False, server_default="0"))
    _add_col_if_missing(inspector, "shopper_accounts", sa.Column("account_age_days", sa.Integer(), nullable=False, server_default="30"))
    _add_col_if_missing(inspector, "shopper_accounts", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    _add_col_if_missing(inspector, "policies", sa.Column("return_window_days", sa.Integer(), nullable=False, server_default="30"))

    _add_col_if_missing(inspector, "passports", sa.Column("signing_key_id", sa.String(), nullable=False, server_default="key_packer_origin_01"))
    _add_col_if_missing(inspector, "passports", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    _add_col_if_missing(inspector, "orders", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    _add_col_if_missing(inspector, "order_items", sa.Column("currency", sa.String(3), nullable=False, server_default="USD"))

    _add_col_if_missing(inspector, "returns", sa.Column("shopper_id", sa.String(), nullable=False, server_default="shopper_1"))
    _add_col_if_missing(inspector, "returns", sa.Column("currency", sa.String(3), nullable=False, server_default="USD"))
    _add_col_if_missing(inspector, "returns", sa.Column("challenge_nonce", sa.String(), nullable=False, server_default=""))
    _add_col_if_missing(inspector, "returns", sa.Column("shopper_nonce", sa.String(), nullable=True))
    _add_col_if_missing(inspector, "returns", sa.Column("audit_seed_hex", sa.String(), nullable=False, server_default=""))
    _add_col_if_missing(inspector, "returns", sa.Column("audit_commitment", sa.String(), nullable=False, server_default=""))
    _add_col_if_missing(inspector, "returns", sa.Column("audit_probability", sa.Float(), nullable=False, server_default="0.08"))
    _add_col_if_missing(inspector, "returns", sa.Column("reason_code", sa.String(), nullable=False, server_default="CHANGED_MIND"))
    _add_col_if_missing(inspector, "returns", sa.Column("reason_text", sa.String(), nullable=False, server_default=""))
    _add_col_if_missing(inspector, "returns", sa.Column("accessories_json", sa.JSON(), nullable=False, server_default="{}"))
    _add_col_if_missing(inspector, "returns", sa.Column("consent_recorded", sa.Boolean(), nullable=False, server_default=sa.false()))
    _add_col_if_missing(inspector, "returns", sa.Column("seal_nonce_hash", sa.String(), nullable=True))
    _add_col_if_missing(inspector, "returns", sa.Column("dropoff_photo_ref", sa.String(), nullable=True))
    _add_col_if_missing(inspector, "returns", sa.Column("carrier_tracking_number", sa.String(), nullable=True))
    _add_col_if_missing(inspector, "returns", sa.Column("retake_count", sa.Integer(), nullable=False, server_default="0"))
    _add_col_if_missing(inspector, "returns", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    _add_col_if_missing(inspector, "decisions", sa.Column("currency", sa.String(3), nullable=False, server_default="USD"))

    _add_col_if_missing(inspector, "keep_offers", sa.Column("currency", sa.String(3), nullable=False, server_default="USD"))
    _add_col_if_missing(inspector, "keep_offers", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    _add_col_if_missing(inspector, "refund_actions", sa.Column("merchant_id", sa.String(), nullable=False, server_default="merch_a"))
    _add_col_if_missing(inspector, "refund_actions", sa.Column("capture_id", sa.String(), nullable=False, server_default="CAP-01"))
    _add_col_if_missing(inspector, "refund_actions", sa.Column("currency", sa.String(3), nullable=False, server_default="USD"))
    _add_col_if_missing(inspector, "refund_actions", sa.Column("paypal_debug_id", sa.String(), nullable=True))
    _add_col_if_missing(inspector, "refund_actions", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"))
    _add_col_if_missing(inspector, "refund_actions", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    _add_col_if_missing(inspector, "custody_events", sa.Column("records_only", sa.Boolean(), nullable=False, server_default=sa.true()))
    _add_col_if_missing(inspector, "custody_events", sa.Column("evidence_ref", sa.String(), nullable=False, server_default="dock.jpg"))

    _add_col_if_missing(inspector, "appeals", sa.Column("subject", sa.String(), nullable=False, server_default=""))
    _add_col_if_missing(inspector, "appeals", sa.Column("disputed_delta_minor", sa.BigInteger(), nullable=False, server_default="0"))
    _add_col_if_missing(inspector, "appeals", sa.Column("topup_amount_minor", sa.BigInteger(), nullable=False, server_default="0"))
    _add_col_if_missing(inspector, "appeals", sa.Column("currency", sa.String(3), nullable=False, server_default="USD"))
    _add_col_if_missing(inspector, "appeals", sa.Column("outcome", sa.String(), nullable=True))
    _add_col_if_missing(inspector, "appeals", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_table("scheduler_leases")
    op.drop_table("agent_tokens")
    op.drop_table("resale_listings")
