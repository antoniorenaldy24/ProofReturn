"""Add status_detail column to refund_actions for PayPal PENDING status tracking (RV3-01).

Revision ID: 0004_refund_action_status_detail
Revises: 0003_order_dispute_and_reversal_freeze
Create Date: 2026-11-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_refund_action_status_detail"
down_revision = "0003_order_dispute_and_reversal_freeze"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("refund_actions")}
    if "status_detail" not in existing:
        op.add_column("refund_actions", sa.Column("status_detail", sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns("refund_actions")}
    if "status_detail" in existing:
        op.drop_column("refund_actions", "status_detail")
