"""Add next_attempt_at to refund_actions table (Round 4 Task T5: RV3-12).

Revision ID: 0006_refund_action_next_attempt_at
Revises: 0005_policy_is_active
Create Date: 2026-11-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_refund_action_next_attempt_at"
down_revision = "0005_policy_is_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("refund_actions")}
    if "next_attempt_at" not in cols:
        op.add_column(
            "refund_actions",
            sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("refund_actions")}
    if "next_attempt_at" in cols:
        op.drop_column("refund_actions", "next_attempt_at")
