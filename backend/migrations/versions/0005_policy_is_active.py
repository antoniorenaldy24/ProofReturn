"""Add is_active to policies table (Round 4 Task T4: RV3-06, INV-11, FR-10).

Revision ID: 0005_policy_is_active
Revises: 0004_refund_action_status_detail
Create Date: 2026-11-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_policy_is_active"
down_revision = "0004_refund_action_status_detail"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("policies")}
    if "is_active" not in cols:
        op.add_column(
            "policies",
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("policies")}
    if "is_active" in cols:
        op.drop_column("policies", "is_active")
